"""
Butter Network

This component should allow for intuitive and transparent control over networks, which are the top
level containers for services.
"""
from butter.log import logger
from butter.providers import get_provider


class NetworkClient:
    """
    Butter Network Client Object

    This is the object through which all network related calls are made.

    Usage:

        import butter
        client = butter.Client(provider, credentials)
        client.network.create("network", blueprint="tests/blueprints/network.yml")
        client.network.get("network")
        client.network.list()
        client.network.destroy(client.network.get("network"))

    The above commands will create and destroy a network named "network".
    """
    def __init__(self, provider, credentials):
        self.network = get_provider(provider).network.NetworkClient(
            credentials)

    def create(self, name, blueprint):
        """
        Create new network named "name" with blueprint file at "blueprint".

        Example:

            client.network.create("mynetwork", "network-blueprint.yml")

        """
        logger.info('Creating network %s with blueprint %s', name, blueprint)
        return self.network.create(name, blueprint)

    def get(self, name):
        """
        Get a network named "name" and return some data about it.

        Example:

            client.network.get("mynetwork")

        """
        logger.info('Getting network %s', name)
        return self.network.get(name)

    def destroy(self, network):
        """
        Destroy the given network.

        Example:

            client.network.destroy(client.network.get("mynetwork"))

        """
        logger.info('Destroying network %s', network)
        return self.network.destroy(network)

    def list(self):
        """
        List all networks.

        Example:

            client.network.list()

        """
        logger.info('Listing networks')
        return self.network.list()
