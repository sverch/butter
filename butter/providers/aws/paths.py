"""
Butter Paths on AWS

This is a the AWS implmentation for the paths API, a high level interface to add
routes between services, doing the conversion to security groups and firewall
rules.
"""
import boto3

from butter.util import netgraph
from butter.providers.aws import instances
from butter.providers.aws.impl.asg import ASG
from butter.providers.aws.log import logger
from butter.util.exceptions import BadEnvironmentStateException


class PathsClient:
    """
    Client object to interact with paths between resources.
    """
    def __init__(self, credentials):
        self.credentials = credentials
        self.instances = instances.InstancesClient(credentials)
        self.asg = ASG(credentials)

    def expose(self, network_name, subnetwork_name, port):
        """
        Make the "subnetwork_name" service accessible on the internet.
        """
        if self.internet_accessible(network_name, subnetwork_name, port):
            logger.info("Service %s in network %s is already internet "
                        "accessible on port: %s", subnetwork_name,
                        network_name, port)
            return True
        ec2 = boto3.client("ec2")
        security_group_id = self.asg.get_launch_configuration_security_group(
            network_name, subnetwork_name)
        ec2.authorize_security_group_ingress(GroupId=security_group_id,
                                             IpPermissions=[{
                                                 'FromPort': port,
                                                 'ToPort': port,
                                                 'IpProtocol': 'tcp',
                                                 'IpRanges': [{
                                                     'CidrIp': '0.0.0.0/0'
                                                 }]
                                             }]
                                             )
        return True

    def add(self, network, from_name, to_name, port):
        """
        Adds a route from "from_name" to "to_name".
        """
        if self.has_access(network, from_name, to_name, port):
            logger.info("Service %s already has access to %s in network %s "
                        "on port: %s", from_name, to_name,
                        network, port)
            return True
        ec2 = boto3.client("ec2")
        to_sg_id = self.asg.get_launch_configuration_security_group(network,
                                                                    to_name)
        from_sg_id = self.asg.get_launch_configuration_security_group(
            network, from_name)
        ec2.authorize_security_group_ingress(GroupId=to_sg_id,
                                             IpPermissions=[{
                                                 'FromPort': port,
                                                 'ToPort': port,
                                                 'IpProtocol': 'tcp',
                                                 'UserIdGroupPairs': [
                                                     {'GroupId': from_sg_id}
                                                 ]
                                             }]
                                             )
        return True

    def remove(self, network, from_name, to_name, port):
        """
        Remove a route from "from_name" to "to_name".
        """
        ec2 = boto3.client("ec2")
        to_sg_id = self.asg.get_launch_configuration_security_group(network,
                                                                    to_name)
        from_sg_id = self.asg.get_launch_configuration_security_group(
            network, from_name)
        ec2.revoke_security_group_ingress(GroupId=to_sg_id,
                                          IpPermissions=[{
                                              'FromPort': port,
                                              'ToPort': port,
                                              'IpProtocol': 'tcp',
                                              'UserIdGroupPairs': [
                                                  {'GroupId': from_sg_id}
                                              ]
                                          }]
                                          )
    # pylint: disable=too-many-locals
    def list(self):
        """
        List all paths and return a dictionary structure representing a graph.
        """
        ec2 = boto3.client("ec2")
        sg_to_service = {}
        for instance in self.instances.list():
            sg_id = self.asg.get_launch_configuration_security_group(
                instance["Network"], instance["Id"])
            if sg_id in sg_to_service:
                raise BadEnvironmentStateException(
                    "Service %s and %s have same security group: %s" %
                    (sg_to_service[sg_id], instance, sg_id))
            sg_to_service[sg_id] = instance
        security_groups = ec2.describe_security_groups()

        def make_rule(source, rule):
            return {
                "source": source,
                "protocol": rule["IpProtocol"],
                "port": rule.get("FromPort", "N/A"),
                "type": "ingress"
            }

        def get_sg_rules(ip_permissions):
            rules = []
            for ip_range in ip_permissions["IpRanges"]:
                source = ip_range.get("CidrIp", "0.0.0.0/0")
                rules.append(make_rule(source, ip_permissions))
            return rules

        def get_cidr_rules(ip_permissions):
            rules = []
            for group in ip_permissions["UserIdGroupPairs"]:
                service = sg_to_service[group["GroupId"]]
                rules.append(make_rule(service["Id"], ip_permissions))
            return rules

        def get_network(security_group_id):
            return sg_to_service[security_group_id]["Network"]

        fw_info = {}
        network = None
        for security_group in security_groups["SecurityGroups"]:
            if security_group["GroupId"] not in sg_to_service:
                continue
            rules = []
            for ip_permissions in security_group["IpPermissions"]:
                logger.debug("ip_permissions: %s", ip_permissions)
                rules.extend(get_cidr_rules(ip_permissions))
                rules.extend(get_sg_rules(ip_permissions))
            network = get_network(security_group["GroupId"])
            if network not in fw_info:
                fw_info[network] = {}
            service = sg_to_service[security_group["GroupId"]]
            fw_info[network][service["Id"]] = rules
        return {network: netgraph.firewalls_to_net(info)
                for network, info in fw_info.items()}

    def internet_accessible(self, network_name, subnetwork_name, port):
        """
        Return true if the "subnetwork_name" service is accessible on the
        internet.
        """
        ec2 = boto3.client("ec2")
        security_group_id = self.asg.get_launch_configuration_security_group(
            network_name, subnetwork_name)
        security_group = ec2.describe_security_groups(
            GroupIds=[security_group_id])
        ip_permissions = security_group["SecurityGroups"][0]["IpPermissions"]
        for ip_permission in ip_permissions:
            if (ip_permission["IpRanges"] and
                    ip_permission["FromPort"] == port):
                return True
        return False

    def has_access(self, network, from_name, to_name, port):
        """
        Return true if there is a route from "from_name" to "to_name".

        Note, this only checks if the security group is referenced, which is
        what this tool implements internally.  It will not catch if you
        explicitly added subnet CIDR blocks or if the destination service is
        fully internet accessible based on CIDR.

        See https://github.com/sverch/butter/issues/3 for details.
        """
        ec2 = boto3.client("ec2")
        to_group_id = self.asg.get_launch_configuration_security_group(
            network, to_name)
        from_group_id = self.asg.get_launch_configuration_security_group(
            network, from_name)
        security_group = ec2.describe_security_groups(GroupIds=[to_group_id])
        ip_permissions = security_group["SecurityGroups"][0]["IpPermissions"]
        logger.debug("ip_permissions: %s", ip_permissions)
        for ip_permission in ip_permissions:
            if (ip_permission["UserIdGroupPairs"] and
                    ip_permission["FromPort"] == port):
                for pair in ip_permission["UserIdGroupPairs"]:
                    if "GroupId" in pair and pair["GroupId"] == from_group_id:
                        return True
        return False
