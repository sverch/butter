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
                print(price_dimension_value["pricePerUnit"])
                if price:
                    raise Exception("Found multiple prices, %s and %s" % (
                        price, price_dimension_value["pricePerUnit"]["USD"]))
                price = price_dimension_value["pricePerUnit"]["USD"]
    return price

def node_types():
    """
    Get a list of node sizes to use for matching resource requirements to
    instance type.
    """
    pricing = boto3.client("pricing")

    filters = [
        {"Type":"TERM_MATCH", "Field":"ServiceCode", "Value":"AmazonEC2"},
        {"Type":"TERM_MATCH", "Field":"location", "Value":"US East (N. Virginia)"},
        {"Type":"TERM_MATCH", "Field":"instanceFamily", "Value":"General Purpose"},
        {"Type":"TERM_MATCH", "Field":"currentGeneration", "Value":"Yes"},
        {"Type":"TERM_MATCH", "Field":"operatingSystem", "Value":"Linux"},
        {"Type":"TERM_MATCH", "Field":"productFamily", "Value":"Compute Instance"},
        {"Type":"TERM_MATCH", "Field":"preinstalledSw", "Value":"NA"}
        ]
    next_token = ""
    node_sizes = []
    while True:
        products = pricing.get_products(ServiceCode="AmazonEC2",
                                        Filters=filters, NextToken=next_token)
        for node_info in products["PriceList"]:
            node_price = get_price(node_info)
            node_attributes = json.loads(node_info)["product"]["attributes"]
            if not node_attributes["instanceType"].startswith("t3"):
                continue
            node_sizes.append({"memory": node_attributes["memory"], "cpu": node_attributes["vcpu"],
                               "type": node_attributes["instanceType"], "price": node_price})
        if "NextToken" not in products:
            break
        next_token = products["NextToken"]
    return node_sizes

print(json.dumps(node_types(), indent=2, sort_keys=True))
