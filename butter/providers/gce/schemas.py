"""
Schemas of the results returned by various API calls for GCE.
"""

def canonicalize_network_info(network):
    """
    Convert what is returned from GCE into the butter standard format.
    """
    cidr_block = network.cidr
    if not cidr_block:
        cidr_block = "N/A"
    return {
        "Name": network.name,
        "Id": network.id,
        "CidrBlock": cidr_block
    }

def canonicalize_subnetwork_info(subnetwork):
    """
    Convert what is returned from GCE into the butter standard format.
    """
    return {
        "Id": subnetwork.id,
        "Name": subnetwork.name,
        "Network": subnetwork.network.name,
        "CidrBlock": subnetwork.cidr,
        "Region": subnetwork.region.name,
        "AvailabilityZone": "N/A",
    }

def canonicalize_instances_info(node_name, nodes):
    """
    Convert what is returned from GCE into the butter standard format.
    """
    return {"Id": node_name,
            "Instances": [
                {
                    "Id": node.uuid,
                    "PublicIp": node.public_ips[0],
                    "PrivateIp": node.private_ips[0],
                    "State": node.state
                    } for node in nodes
                ]
            }
