"""
Butter Service on GCE

This is the GCE implmentation for the service API, a high level interface to manage services.
"""
import ipaddress
import itertools
import re

from butter.providers.gce.driver import get_gce_driver

from butter.util.blueprint import ServiceBlueprint
from butter.util.instance_fitter import get_fitting_instance
from butter.util.exceptions import (DisallowedOperationException,
                                    BadEnvironmentStateException)
from butter.providers.gce.impl import subnetwork
from butter.providers.gce.network import NetworkClient
from butter.providers.gce.impl.firewalls import Firewalls
from butter.providers.gce.log import logger
from butter.providers.gce.schemas import (canonicalize_instance_info,
                                          canonicalize_node_size)
from butter.types.common import Service

DEFAULT_REGION = "us-east1"


class ServiceClient:
    """
    Client object to manage services.
    """

    def __init__(self, credentials):
        self.credentials = credentials
        self.driver = get_gce_driver(credentials)
        self.subnetwork = subnetwork.SubnetworkClient(credentials)
        self.network = NetworkClient(credentials)
        self.firewalls = Firewalls(self.driver)

    # pylint: disable=too-many-arguments, too-many-locals
    def create(self, network, service_name, blueprint, template_vars, count):
        """
        Create a service in "network" named "service_name" with blueprint file at "blueprint".
        """
        logger.info('Creating service %s, %s with blueprint %s and ' 'template_vars %s',
                    network.name, service_name, blueprint, template_vars)
        self.subnetwork.create(network.name, service_name,
                               blueprint=blueprint)
        instances_blueprint = ServiceBlueprint(blueprint, template_vars)
        az_count = instances_blueprint.availability_zone_count()
        availability_zones = list(itertools.islice(self._get_availability_zones(), az_count))
        if len(availability_zones) < az_count:
            raise DisallowedOperationException("Do not have %s availability zones: %s" % (
                az_count, availability_zones))
        instance_count = az_count
        if count:
            instance_count = count

        def get_image(image_specifier):
            images = [image for image in self.driver.list_images() if re.match(image_specifier,
                                                                               image.name)]
            if not images:
                raise DisallowedOperationException("Could not find image named %s"
                                                   % image_specifier)
            if len(images) > 1:
                raise DisallowedOperationException("Found multiple images for specifier %s: %s"
                                                   % (image_specifier, images))
            return images[0]

        image = get_image(instances_blueprint.image())
        instance_type = get_fitting_instance(self, blueprint)
        for availability_zone, instance_num in zip(itertools.cycle(availability_zones),
                                                   range(0, instance_count - 1)):
            full_subnetwork_name = "%s-%s" % (network.name, service_name)
            instance_name = "%s-%s" % (full_subnetwork_name, instance_num)
            metadata = [
                {"key": "startup-script", "value":
                 instances_blueprint.runtime_scripts()},
                {"key": "network", "value": network.name},
                {"key": "subnetwork", "value": service_name}
            ]
            logger.info('Creating instance %s in zone %s', instance_name, availability_zone)
            self.driver.create_node(instance_name, instance_type, image, location=availability_zone,
                                    ex_network=network.name, ex_subnetwork=full_subnetwork_name,
                                    external_ip="ephemeral", ex_metadata=metadata,
                                    ex_tags=[full_subnetwork_name])
        return self.get(network, service_name)

    def get(self, network, service_name):
        """
        Get a service in "network" named "service_name".
        """
        logger.info('Discovering service %s, %s', network.name, service_name)

        # 1. Get list of instances
        instances = []
        node_name = "%s-%s" % (network.name, service_name)
        for node in self.driver.list_nodes():
            if node.name.startswith(node_name):
                instances.append(canonicalize_instance_info(node))

        # 2. Get List Of Subnets
        subnetworks = self.subnetwork.get(network, service_name)

        # 3. Group Services By Subnet
        for subnet_info in subnetworks:
            for instance in instances:
                if (ipaddress.IPv4Network(subnet_info.cidr_block).overlaps(
                        ipaddress.IPv4Network(instance.private_ip))):
                    subnet_info.instances.append(instance)

        return Service(network=network, name=service_name, subnetworks=subnetworks)

    def destroy(self, service):
        """
        Destroy a service described by "service".
        """
        logger.info('Destroying service: %s', service)
        destroy_results = []
        for node in self.driver.list_nodes():
            metadata = node.extra.get("metadata", {}).get("items", [])
            node_network_name = None
            node_subnetwork_name = None
            for item in metadata:
                logger.debug("Found metadata item %s for node %s", item, node)
                if item["key"] == "network":
                    node_network_name = item["value"]
                if item["key"] == "subnetwork":
                    node_subnetwork_name = item["value"]
            if (service.network.name == node_network_name and
                    service.name == node_subnetwork_name):
                logger.info('Destroying instance: %s', node.name)
                destroy_results.append(self.driver.destroy_node(node))
        subnetwork_destroy = self.subnetwork.destroy(service.network.name,
                                                     service.name)
        self.firewalls.delete_firewall(service.network.name, service.name)
        return {"Subnetwork": subnetwork_destroy,
                "Instances": destroy_results}

    def list(self):
        """
        List all instance groups.
        """
        logger.debug('Listing services')
        instances_info = {}
        for node in self.driver.list_nodes():
            logger.debug("Node metadata: %s", node.extra["metadata"])
            metadata = node.extra["metadata"]["items"]
            network_names = [item["value"] for item in metadata
                             if item["key"] == "network"]
            if len(network_names) != 1:
                raise BadEnvironmentStateException(
                    "Found node with no network in metadata: %s" % metadata)
            subnetwork_names = [item["value"] for item in metadata
                                if item["key"] == "subnetwork"]
            if len(subnetwork_names) != 1:
                raise BadEnvironmentStateException(
                    "Found node with no subnetwork in metadata: %s" % metadata)
            instance_group_name = "%s-%s" % (network_names[0],
                                             subnetwork_names[0])
            if instance_group_name not in instances_info:
                instances_info[instance_group_name] = {}
                instances_info[instance_group_name]["Nodes"] = []
                instances_info[instance_group_name]["Network"] = self.network.get(network_names[0])
                instances_info[instance_group_name]["Id"] = subnetwork_names[0]
            instances_info[instance_group_name]["Nodes"].append(node)
        return [self.get(group_info["Network"], group_info["Id"])
                for group_info in instances_info.values()]

    def _get_availability_zones(self):
        zones = self.driver.ex_list_zones()
        return [zone for zone in zones if zone.name.startswith(DEFAULT_REGION)]

    def node_types(self):
        """
        Get a list of node sizes to use for matching resource requirements to
        instance type.
        """
        # Need to do this because the "list_sizes" function doesn't seem to work
        # with region strings.
        zones = self.driver.ex_list_zones()
        for zone in zones:
            if zone.name.startswith(DEFAULT_REGION):
                node_sizes = self.driver.list_sizes(location=zone)
                return [canonicalize_node_size(node_size) for node_size in node_sizes]
        raise DisallowedOperationException("Could not find zone in region: %s" %
                                           DEFAULT_REGION)
