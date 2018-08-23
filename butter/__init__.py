"""
Butter

This is a python library to provide a basic set of easy to use primitive
operations that can work with many different cloud providers.

These primitives are:

    - Create a "Network" (also known as VPC, Network, Environment).  e.g. "dev".
    - Create a "Service" within that network.  e.g. "apache-public".
    - Easily control network connections and firewalls.

The goal is to provide an intuitive abstraction that is powerful enough to build
on, so that building other layers on top is easy and anything built on it is
automatically cross cloud.
"""
from butter import network, service, paths


# pylint: disable=too-few-public-methods
class Client:
    """
    Butter Client Object

    This is the object through which all calls are made.

    Usage:

        import butter
        client = butter.Client(provider, credentials)
        client.network.*
        client.paths.*

    See the documentation on those sub-components for more details.
    """

    def __init__(self, provider, credentials):
        self.network = network.NetworkClient(provider, credentials)
        self.service = service.ServiceClient(provider, credentials)
        self.paths = paths.PathsClient(provider, credentials)

    # pylint: disable=too-many-locals
    def graph(self):
        """
        Return a human readable formatted string representation of the paths
        graph.
        """

        def start_graph():
            return "digraph services {\n\n"

        def end_graph(graph_string):
            graph_string += "\n}\n"
            return graph_string

        def start_cluster(graph_string, cluster_id, cluster_name):
            graph_string += "subgraph cluster_%s {\n" % cluster_id
            graph_string += "    label = \"%s\";\n" % cluster_name
            return graph_string

        def end_cluster(graph_string):
            graph_string += "\n}\n"
            return graph_string

        def add_path(graph_string, from_node, to_node, protocol, port):
            if not from_node.name:
                cidr_blocks = [subnetwork.cidr_block for subnetwork in from_node.subnetworks]
                from_name = ",".join(cidr_blocks)
                from_network_name = "external"
            else:
                from_name = from_node.name
                from_network_name = from_node.network.name
            path_template = "\"%s (%s)\" -> \"%s (%s)\" [ label=\"(%s:%s)\" ];\n"
            graph_string += path_template % (from_name, from_network_name, to_node.name,
                                             to_node.network.name, protocol, port)
            return graph_string

        def add_node(graph_string, node_name, network_name):
            graph_string += "    \"%s (%s)\";\n" % (node_name, network_name)
            return graph_string

        def group_paths_by_network(paths_info):
            net_to_path = {}
            for path in paths_info:
                if path.network.name not in net_to_path:
                    net_to_path[path.network.name] = []
                net_to_path[path.network.name].append(path)
            return net_to_path

        def group_services_by_network(services_info):
            net_to_service = {}
            for service_info in services_info:
                if service_info.network.name not in net_to_service:
                    net_to_service[service_info.network.name] = []
                net_to_service[service_info.network.name].append(service_info)
            return net_to_service

        # First group paths and services by network
        paths_info = self.paths.list()
        net_to_path = group_paths_by_network(paths_info)
        services_info = self.service.list()
        net_to_service = group_services_by_network(services_info)
        networks_info = self.network.list()

        graph_string = start_graph()
        cluster_id = 0
        for network_info in networks_info:

            # Each network is a "cluster" in graphviz terms
            graph_string = start_cluster(graph_string, cluster_id, network_info.name)
            cluster_id += 1

            # If the network is empty just make a placeholder node
            if network_info.name not in net_to_service and network_info.name not in net_to_path:
                graph_string = add_node(graph_string, "Empty Network", network_info.name)
                graph_string = end_cluster(graph_string)
                continue

            # Otherwise, add all the services and path in this network
            if network_info.name in net_to_service:
                for service_info in net_to_service[network_info.name]:
                    graph_string = add_node(graph_string, service_info.name,
                                            service_info.network.name)
            graph_string = end_cluster(graph_string)

            # We do all paths outside the cluster so that public CIDRs will show up outside the
            # networks.
            if network_info.name in net_to_path:
                for path_info in net_to_path[network_info.name]:
                    graph_string = add_path(graph_string, path_info.source, path_info.destination,
                                            path_info.protocol, path_info.port)

        graph_string = end_graph(graph_string)
        return graph_string
