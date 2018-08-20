#!/usr/bin/env python
"""
Utilities to deal with blueprint files.  All here so that I can keep them as a
standard format.
"""

import os
import yaml
import jinja2

from butter.util.log import logger
from butter.util.exceptions import BlueprintException
from butter.util.storage_size_parser import parse_storage_size


# pylint: disable=too-few-public-methods
class Blueprint:
    """
    Base blueprint object
    """

    def __init__(self, blueprint_file):
        with open(blueprint_file, 'r') as stream:
            try:
                self.blueprint = yaml.load(stream)
            except yaml.YAMLError as exc:
                logger.error("Error parsing blueprint: %s", exc)
                raise exc
        self.blueprint_path = os.path.dirname(blueprint_file)
        self.blueprint_filename = blueprint_file


class NetworkBlueprint(Blueprint):
    """
    Blueprint for top level network.
    """
    def get_prefix(self):
        """
        Get the number of bits of prefix for the CIDR block.  A network of size 0 would give a
        prefix of 32 meaning the network has 1 address in it (so effectively nothing since that's
        usually disallowed or filled by internal services.
        """
        return 32 - self.blueprint["network"]["legacy_network_size_bits"]

    def get_allowed_private_cidr(self):
        """
        Get the CIDR block in which we can allocate our networks.
        """
        return self.blueprint["network"].get("allowed_private_cidr", "10.0.0.0/8")

class ServiceBlueprint(Blueprint):
    """
    Blueprint for services.
    """
    def __init__(self, blueprint_file, template_vars=None):
        super(ServiceBlueprint, self).__init__(blueprint_file)
        self.template_vars = template_vars
        if not self.template_vars:
            self.template_vars = {}

    def max_count(self):
        """
        Returns the maximum number of instances expected.  Used to compute subnet sizes.
        """
        return self.blueprint["network"]["subnetwork_max_instance_count"]

    def availability_zone_count(self):
        """
        Number of availability zones.  Used to determine how redundant the services should be.
        """
        return self.blueprint["placement"].get("availability_zones", 3)

    def image(self):
        """
        The human readable name of the image to use.  This will be used internally to look up the
        image ID to deploy with.
        """
        return self.blueprint["image"]["name"]

    def runtime_scripts(self):
        """
        Returns the contents of the provided runtime scripts.  Currently only supports a list with
        one script.
        """
        if len(self.blueprint["initialization"]) > 1:
            raise NotImplementedError("Only one initialization script currently supported")
        def handle_initialization_block(script):
            """
            Handles a single initialization block.  Factored out in case I
            want to support multiple startup scripts.
            """
            full_path = os.path.join(self.blueprint_path,
                                     script["path"])
            with open(full_path) as startup_script_file:
                startup_script = startup_script_file.read()
            template = jinja2.Template(startup_script)
            if "vars" in script:
                for name, opts in script["vars"].items():
                    if opts["required"] and name not in self.template_vars:
                        raise BlueprintException(
                            "Template Variable: \"%s\" must be set." %
                            (name))
            return template.render(self.template_vars)
        all_template_vars = [
            name
            for initialization in self.blueprint["initialization"]
            if "vars" in initialization
            for name in initialization["vars"]]
        for template_var in self.template_vars:
            if template_var not in all_template_vars:
                raise BlueprintException(
                    "Unrecognized Template Variable: \"%s\"." %
                    (template_var))
        return handle_initialization_block(self.blueprint["initialization"][0])

    def public_ip(self):
        """
        Returns whether a public IP should be added to the instances.
        """
        return self.blueprint["instance"].get("public_ip", False)

    def cpus(self):
        """
        Returns the cpus to allocate for the instance.  This is required.
        """
        return float(self.blueprint["instance"]["cpus"])

    def gpus(self):
        """
        Whether to allocate a GPU.
        """
        return self.blueprint["instance"].get("gpus", False)

    def memory(self):
        """
        Returns the memory to allocate for the instance.  This is required.
        """
        return parse_storage_size(self.blueprint["instance"]["memory"])

    def disks(self):
        """
        Returns the disks to allocate for the instance.  This is required.
        """
        return self.blueprint["instance"]["disks"]
