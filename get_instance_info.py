"""
Helper to get pricing.
"""
import json
import boto3

def get_price(node_info):
    """
    Given a node returned by the pricing api extract the price.
    """
    price = None
    for _, on_demand_value in json.loads(node_info)["terms"]["OnDemand"].items():
        if "priceDimensions" in on_demand_value:
            for _, price_dimension_value in on_demand_value["priceDimensions"].items():
                if price:
                    raise Exception("Found multiple prices, %s and %s" % (
                        price, price_dimension_value["pricePerUnit"]["USD"]))
                price = price_dimension_value["pricePerUnit"]["USD"]
    return price

def node_types(family):
    """
    Get a list of node sizes to use for matching resource requirements to
    instance type.
    """
    pricing = boto3.client("pricing")

    filters = [
        {"Type":"TERM_MATCH", "Field":"ServiceCode", "Value":"AmazonEC2"},
        {"Type":"TERM_MATCH", "Field":"location", "Value":"US East (N. Virginia)"},
        #{"Type":"TERM_MATCH", "Field":"instanceFamily", "Value":"General Purpose"},
        #{"Type":"TERM_MATCH", "Field":"currentGeneration", "Value":"Yes"},
        {"Type":"TERM_MATCH", "Field":"operatingSystem", "Value":"Linux"},
        {"Type":"TERM_MATCH", "Field":"productFamily", "Value":"Compute Instance"},
        {"Type":"TERM_MATCH", "Field":"preinstalledSw", "Value":"NA"},
        {"Type":"TERM_MATCH", "Field":"capacitystatus", "Value":"Used"},
        {"Type":"TERM_MATCH", "Field":"operation", "Value":"RunInstances"},
        {"Type":"TERM_MATCH", "Field":"tenancy", "Value":"shared"}
        ]
    next_token = ""
    node_sizes = []
    while True:
        products = pricing.get_products(ServiceCode="AmazonEC2",
                                        Filters=filters, NextToken=next_token)
        for node_info in products["PriceList"]:
            node_price = get_price(node_info)
            node_attributes = json.loads(node_info)["product"]["attributes"]
            if not node_attributes["instanceType"].startswith(family):
                continue
            node_sizes.append({"memory": node_attributes["memory"], "cpu": node_attributes["vcpu"],
                               "type": node_attributes["instanceType"], "price": node_price})
        if "NextToken" not in products:
            break
        next_token = products["NextToken"]
    return node_sizes

def rds_types(family):
    """
    Get a list of rds sizes to use for matching resource requirements to instance type.
    """
    pricing = boto3.client("pricing")

    filters = [
        {"Type":"TERM_MATCH", "Field":"ServiceCode", "Value":"AmazonRDS"},
        {"Type":"TERM_MATCH", "Field":"productFamily", "Value":"Database Instance"},
        {"Type":"TERM_MATCH", "Field":"databaseEngine", "Value":"PostgreSQL"},
        #{"Type":"TERM_MATCH", "Field":"instanceFamily", "Value":"General Purpose"},
        #{"Type":"TERM_MATCH", "Field":"instanceTypeFamily", "Value":family.upper()},
        {"Type":"TERM_MATCH", "Field":"location", "Value":"US East (N. Virginia)"},
        {"Type":"TERM_MATCH", "Field":"deploymentOption", "Value":"Single-AZ"},
        ]
    next_token = ""
    node_sizes = []
    while True:
        products = pricing.get_products(ServiceCode="AmazonRDS",
                                        Filters=filters, NextToken=next_token)
        for node_info in products["PriceList"]:
            node_price = get_price(node_info)
            node_attributes = json.loads(node_info)["product"]["attributes"]
            if not node_attributes["instanceType"].startswith("db.%s" % family):
                continue
            node_sizes.append({"memory": node_attributes["memory"], "cpu": node_attributes["vcpu"],
                               "type": node_attributes["instanceType"], "price": node_price})
        if "NextToken" not in products:
            break
        next_token = products["NextToken"]
    return node_sizes

def compare_prices(family):
    """
    Compare prices for RDS and EC2.
    """
    rds_pricing = rds_types(family)
    ec2_pricing = node_types(family)

    for rds_price in rds_pricing:
        for ec2_price in ec2_pricing:
            _, instance_type = ec2_price["type"].split(".")
            _, _, rds_instance_type = rds_price["type"].split(".")
            if instance_type == rds_instance_type:
                print("%s markup percentage over %s: " % (rds_price["type"], ec2_price["type"]))
                print((float(rds_price["price"]) / float(ec2_price["price"])) * 100)

compare_prices("m4")
compare_prices("t2")
compare_prices("r4")
compare_prices("r3")
