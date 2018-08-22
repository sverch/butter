"""
Butter Mock AWS Service
"""
import boto3
import butter.providers.aws.impl.service


class ServiceClient:
    """
    Butter Service Client Object for Mock AWS
    """
    def __init__(self, credentials):
        self.service = butter.providers.aws.impl.service.ServiceClient(boto3, credentials,
                                                                       mock=True)

    def create(self, network, service_name, blueprint, template_vars=None):
        """
        Create a service in "network" named "service_name" with blueprint file at "blueprint".

        "template_vars" are passed to the initialization scripts as jinja2
        variables.
        """
        return self.service.create(network, service_name, blueprint, template_vars)

    def get(self, network, service_name):
        """
        Get a service in "network" named "service_name".
        """
        return self.service.get(network, service_name)

    def destroy(self, service):
        """
        Destroy a service described by the "service" object.
        """
        return self.service.destroy(service)

    def list(self):
        """
        List all services.
        """
        return self.service.list()

    def node_types(self):
        """
        Get mapping of node types to the resources.
        """
        return self.service.node_types()