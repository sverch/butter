"""
Common types.

The overall structure is:

    Network
      |- Services
          |- Subnetworks
              |- Instances

The Network object does not contain any Services to avoid circular dependencies.  However, the
Services object and children include all the remaining parts of the heirarchy.

This is because the API only has two entry points: a Network or a Service.  The Service contains
what Network it's in and encapsulates all information about it.  Additional functions to only
extract instances or subnetworks could be layered on top of this.
"""
class Network:
    """
    Simple container to hold network information.
    """
    def __init__(self, name, network_id, cidr_block, region):
        self.name = name
        self.network_id = network_id
        self.cidr_block = cidr_block
        self.region = region

    def __eq__(self, other):
        return (self.name == other.name and
                self.network_id == other.network_id and
                self.cidr_block == other.cidr_block)

    def __repr__(self):
        return "Network(name=%r, network_id=%r, cidr_block=%r, region=%r)" % (
            self.name, self.network_id, self.cidr_block, self.region)

    def __dict__(self):
        result = {
            "Name": self.name,
            "Id": self.network_id,
            }
        if self.cidr_block:
            result["CidrBlock"] = self.cidr_block
        if self.region:
            result["Region"] = self.region
        return result

class Service:
    """
    Simple container to hold service information.
    """
    def __init__(self, network, name, subnetworks):
        self.network = network
        self.name = name
        self.subnetworks = subnetworks

    def __eq__(self, other):
        return (self.network == other.network and
                self.name == other.name and
                self.subnetworks == other.subnetworks)

    def __repr__(self):
        return "Service(network=%r, name=%r, subnetworks=%r)" % (self.network, self.name,
                                                                 self.subnetworks)

    def __dict__(self):
        return {
            "Name": self.name,
            "Network": self.network,
            "Subnetworks": self.subnetworks
            }

class Subnetwork:
    """
    Simple container to hold subnetwork information.
    """
    # pylint: disable=too-many-arguments
    def __init__(self, subnetwork_id, name, cidr_block, region, availability_zone, instances):
        self.subnetwork_id = subnetwork_id
        self.name = name
        self.cidr_block = cidr_block
        self.region = region
        self.availability_zone = availability_zone
        self.instances = instances

    def __eq__(self, other):
        return (self.subnetwork_id == other.subnetwork_id and
                self.name == other.name and
                self.cidr_block == other.cidr_block and
                self.region == other.region and
                self.availability_zone == other.availability_zone and
                self.instances == other.instances)

    def __repr__(self):
        return ("Subnetwork(subnetwork_id=%r, name=%r, cidr_block=%r, region=%r, "
                "availability_zone=%r, instances=%r)") % (self.subnetwork_id, self.name,
                                                          self.cidr_block, self.region,
                                                          self.availability_zone, self.instances)

    def __dict__(self):
        result = {
            "Id": self.subnetwork_id,
            "Name": self.name,
            "CidrBlock": self.cidr_block,
            "Region": self.region,
            "Instances": self.instances
            }
        if self.availability_zone:
            result["AvailabilityZone"] = self.availability_zone
        return result

class Instance:
    """
    Simple container to hold instance information.
    """
    def __init__(self, instance_id, public_ip, private_ip, state):
        self.instance_id = instance_id
        self.public_ip = public_ip
        self.private_ip = private_ip
        self.state = state

    def __eq__(self, other):
        return (self.instance_id == other.instance_id and
                self.public_ip == other.public_ip and
                self.private_ip == other.private_ip and
                self.state == other.state)

    def __repr__(self):
        return "Instance(instance_id=%r, public_ip=%r, private_ip=%r, state=%r)" % (
            self.instance_id, self.public_ip, self.private_ip, self.state)

    def __dict__(self):
        return {
            "Id": self.instance_id,
            "PublicIp": self.public_ip,
            "PrivateIp": self.private_ip,
            "State": self.state
            }

class Path:
    """
    Simple container to hold path information.
    """
    def __init__(self, source, destination, protocol, port):
        self.source = source
        self.destination = destination
        self.protocol = protocol
        self.port = port

    def __eq__(self, other):
        return (self.source == other.source and
                self.destination == other.destination and
                self.protocol == other.protocol and
                self.port == other.port)

    def __repr__(self):
        return "Path(source=%r, destination=%r, protocol=%r, port=%r)" % (self.source,
                                                                          self.destination,
                                                                          self.protocol, self.port)

    def __dict__(self):
        return {
            "Source": self.source,
            "Destination": self.destination,
            "Protocol": self.protocol,
            "Port": self.port
            }
