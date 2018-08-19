"""
Butter Instances

This component should allow for intuitive and transparent control over groups of instances, which
must be provisioned within a subnetwork.
"""
from butter.log import logger
from butter.providers import get_provider


class InstancesClient:
    """
    Butter Instances Client Object

    This is the object through which all instance related calls are made.

    Usage:

        import butter
        client = butter.Client(provider, credentials)
        mynetwork = client.network.create("network", blueprint="tests/blueprints/network.yml")
        client.instances.create(mynetwork, "public",
                                 blueprint="tests/blueprints/service.yml")
        myservice = client.instances.get(mynetwork, "public")
        client.instances.list()
        client.instances.destroy(myservice)

    The above commands will create and destroy a group of instances named "public" in the network
    "network".
    """
    def __init__(self, provider, credentials):
        self.instances = get_provider(provider).instances.InstancesClient(
            credentials)

    def create(self, network, subnetwork_name, blueprint,
               template_vars=None):
        """
        Create a group of instances in "network" named "subnetwork_name" with blueprint file at
        "blueprint".

        "template_vars" are passed to the initialization scripts as jinja2
        variables.
        """
        logger.info('Creating instances %s in network %s with blueprint %s and '
                    'template_vars %s', subnetwork_name, network, blueprint, template_vars)
        return self.instances.create(network, subnetwork_name, blueprint, template_vars)

    def get(self, network, service_name):
        """
        Get a service in "network" named "service_name".
        """
        logger.info('Discovering instances %s in network %s', service_name, network)
        return self.instances.get(network, service_name)

    def destroy(self, service):
        """
        Destroy a service described by the "service" object.
        """
        logger.info('Destroying service %s', service)
        return self.instances.destroy(service)

    def list(self):
        """
        List all instance groups.
        """
        logger.info('Listing instances')
        return self.instances.list()

    def node_types(self):
        """
        Get mapping of node types to the resources.
        """
        logger.info('Listing node types')
        return self.instances.node_types()
