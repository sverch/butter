"""
Butter Service on AWS

This is the AWS implmentation for the service API, a high level interface to manage groups of
instances.
"""
import boto3
import butter.providers.aws.impl.service



class ServiceClient:
    """
    Client object to manage instances.
    """

    def __init__(self, credentials):
        self.service = butter.providers.aws.impl.service.ServiceClient(boto3, credentials,
                                                                       mock=False)

    # pylint: disable=too-many-arguments
    def create(self, network, service_name, blueprint,
               template_vars=None, count=3):
        """
        Create a group of instances in "network" named "service_name" with blueprint file at
        "blueprint".
        """
        return self.service.create(network, service_name, blueprint, template_vars, count)

    def list(self):
        """
        List all instance groups.
        """
        return self.service.list()

    # pylint: disable=no-self-use
    def get(self, network, service_name):
        """
        Discover a service in "network" named "service_name".
        """
        return self.service.get(network, service_name)

    def destroy(self, service):
        """
        Destroy a group of instances described by "service".
        """
        return self.service.destroy(service)

    def node_types(self):
        """
        Get a list of node sizes to use for matching resource requirements to
        instance type.
        """
        return self.service.node_types()
