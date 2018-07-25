import logging
import time
import boto3

from butter.util.blueprint import NetworkBlueprint
from butter.util.subnet_generator import generate_subnets
from butter.util.exceptions import (BadEnvironmentStateException,
                                    DisallowedOperationException,
                                    OperationTimedOut,
                                    NotEnoughIPSpaceException)
from butter.providers.aws.impl.internet_gateways import InternetGateways

RETRY_COUNT = int(60)
RETRY_DELAY = float(1.0)
ALLOCATION_BLOCKS = ["10.0.0.0/8"]

logger = logging.getLogger(__name__)


class NetworkClient(object):
    def __init__(self, credentials):
        self.credentials = credentials
        self.internet_gateways = InternetGateways(credentials)

    def _get_cidr(self, prefix, address_range_includes,
                  address_range_excludes):
        for address_range_include in address_range_includes:
            for cidr in generate_subnets(address_range_include,
                                         address_range_excludes, prefix):
                return str(cidr)
        raise NotEnoughIPSpaceException("Could not allocate network of size "
                                        "%s in %s, excluding %s" %
                                        (prefix, address_range_includes,
                                         address_range_includes))

    def _canonicalize_vpc_info(self, name, vpc):
        return {
            "Name": name,
            "Id": vpc["VpcId"],
            "CidrBlock": vpc["CidrBlock"]
        }

    def create(self, name, blueprint, inventories=None):
        ec2 = boto3.client("ec2")
        if self.discover(name):
            raise DisallowedOperationException(
                "Found existing VPC named: %s" % name)
        network_blueprint = NetworkBlueprint(blueprint)
        prefix = network_blueprint.get_prefix()
        exclude_cidrs = []
        if inventories:
            for inventory in inventories:
                exclude_cidrs.extend(inventory())
        vpc = ec2.create_vpc(CidrBlock=self._get_cidr(prefix,
                                                      ALLOCATION_BLOCKS,
                                                      exclude_cidrs))
        vpc_id = vpc["Vpc"]["VpcId"]
        try:
            creation_retries = 0
            while creation_retries < RETRY_COUNT:
                try:
                    ec2.create_tags(Resources=[vpc_id],
                                    Tags=[{"Key": "Name",
                                           "Value": name}])
                    if not self.discover(name):
                        time.sleep(float(RETRY_DELAY))
                    else:
                        break
                except Exception:
                    time.sleep(float(RETRY_DELAY))
                    creation_retries = creation_retries + 1
                    if creation_retries >= RETRY_COUNT:
                        raise OperationTimedOut(
                            "Cannot find created VPC: %s" % vpc_id)
        except Exception as e:
            ec2.delete_vpc(VpcId=vpc_id)
            raise e
        return self._canonicalize_vpc_info(name, vpc["Vpc"])

    def discover(self, name):
        ec2 = boto3.client("ec2")
        deployment_filter = {'Name': "tag:Name",
                             'Values': [name]}
        vpcs = ec2.describe_vpcs(Filters=[deployment_filter])
        if len(vpcs["Vpcs"]) > 1:
            raise BadEnvironmentStateException(
                "Expected to find at most one VPC named: %s, "
                "output: %s" % (name, vpcs))
        elif not vpcs["Vpcs"]:
            return None
        else:
            return self._canonicalize_vpc_info(name, vpcs["Vpcs"][0])

    def destroy(self, name):
        ec2 = boto3.client("ec2")
        dc_info = self.discover(name)
        if not dc_info:
            return None

        # Check to see if we have any subnets, otherwise bail out
        subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id',
                                                 'Values': [dc_info["Id"]]}])
        if subnets["Subnets"]:
            message = "Found subnets in network, cannot delete: %s" % subnets
            logger.error(message)
            raise DisallowedOperationException(message)

        # Delete internet gateway if it's no longer referenced
        igw = ec2.describe_internet_gateways(
            Filters=[{'Name': 'attachment.vpc-id',
                      'Values': [dc_info["Id"]]}])
        igw_id = None
        if len(igw["InternetGateways"]) == 1:
            igw_id = igw["InternetGateways"][0]["InternetGatewayId"]
        elif len(igw["InternetGateways"]) > 1:
            raise Exception(
                "Invalid response from describe_internet_gateways: %s" %
                igw)
        if igw_id and not self.internet_gateways.route_count(dc_info["Id"],
                                                             igw_id):
            ec2.detach_internet_gateway(InternetGatewayId=igw_id,
                                        VpcId=dc_info["Id"])
            ec2.delete_internet_gateway(InternetGatewayId=igw_id)

        # Since we check above that there are no subnets, and therefore nothing
        # deployed in this VPC, for now assume it is safe to delete.
        #
        # TODO: Make sure there are no proprietary things that don't return
        # subnets but still use security groups.
        security_groups = ec2.describe_security_groups(
            Filters=[{'Name': 'vpc-id', 'Values': [dc_info["Id"]]}])
        for security_group in security_groups["SecurityGroups"]:
            if security_group["GroupName"] == "default":
                continue
            logger.info("Deleting security group: %s",
                        security_group["GroupName"])
            ec2.delete_security_group(GroupId=security_group["GroupId"])

        # Delete internet gateway, also safe because our subnets are gone.
        igws = ec2.describe_internet_gateways(
            Filters=[{'Name': 'attachment.vpc-id', 'Values': [dc_info["Id"]]}])
        logger.info("Deleting internet gateways: %s", igws)
        for igw in igws["InternetGateways"]:
            logger.info("Deleting internet gateway: %s", igw)
            igw_id = igw["InternetGatewayId"]
            ec2.detach_internet_gateway(InternetGatewayId=igw_id,
                                        VpcId=dc_info["Id"])
            ec2.delete_internet_gateway(InternetGatewayId=igw_id)

        # Now, actually delete the VPC
        try:
            deletion_result = ec2.delete_vpc(VpcId=dc_info["Id"])
        except ec2.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'DependencyViolation':
                logger.info("Dependency violation deleting VPC: %s", e)
            raise e
        return deletion_result

    def list(self):
        ec2 = boto3.client("ec2")

        def get_deployment_tag(vpc):
            if "Tags" not in vpc:
                return None
            for tag in vpc["Tags"]:
                if tag["Key"] == "Name":
                    return tag["Value"]
            return None

        vpcs = ec2.describe_vpcs()
        named_vpcs = []
        unnamed_vpcs = []
        for vpc in vpcs["Vpcs"]:
            name = get_deployment_tag(vpc)
            if name:
                named_vpcs.append(self._canonicalize_vpc_info(name, vpc))
            else:
                unnamed_vpcs.append(self._canonicalize_vpc_info(None, vpc))
        return {"Named": named_vpcs, "Unnamed": unnamed_vpcs}
