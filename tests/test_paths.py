"""
Test for path management.
"""
import os
import pytest
from moto import mock_ec2, mock_autoscaling, mock_elb, mock_route53
import butter
from butter.types.common import Path
from butter.testutils.blueprint_tester import generate_unique_name

EXAMPLE_BLUEPRINTS_DIR = os.path.join(os.path.dirname(__file__),
                                      "..",
                                      "example-blueprints")
NETWORK_BLUEPRINT = os.path.join(EXAMPLE_BLUEPRINTS_DIR,
                                 "network", "blueprint.yml")
SUBNETWORK_BLUEPRINT = os.path.join(EXAMPLE_BLUEPRINTS_DIR,
                                    "subnetwork", "blueprint.yml")

AWS_SERVICE_BLUEPRINT = os.path.join(EXAMPLE_BLUEPRINTS_DIR,
                                     "aws-nginx", "blueprint.yml")
GCE_SERVICE_BLUEPRINT = os.path.join(EXAMPLE_BLUEPRINTS_DIR,
                                     "gce-apache", "blueprint.yml")

def run_paths_test(provider, credentials):
    """
    Test that the path management works against the given provider.
    """

    # Get the client for this test
    client = butter.Client(provider, credentials)

    # Get a somewhat unique network name
    network_name = generate_unique_name("unittest")

    # Provision all the resources
    test_network = client.network.create(network_name, blueprint=NETWORK_BLUEPRINT)
    if provider == "aws":
        lb_service = client.service.create(test_network, "web-lb", AWS_SERVICE_BLUEPRINT, {})
        web_service = client.service.create(test_network, "web", AWS_SERVICE_BLUEPRINT, {})
    else:
        assert provider == "gce"
        lb_service = client.service.create(test_network, "web-lb", GCE_SERVICE_BLUEPRINT, {})
        web_service = client.service.create(test_network, "web", GCE_SERVICE_BLUEPRINT, {})

    # Create CIDR block object for the paths API
    internet = butter.paths.CidrBlock("0.0.0.0/0")

    assert not client.paths.has_access(lb_service, web_service, 80)
    assert not client.paths.internet_accessible(lb_service, 80)

    client.paths.add(lb_service, web_service, 80)
    client.paths.add(internet, lb_service, 80)
    for path in client.paths.list():
        assert isinstance(path, Path)
    client.graph()

    assert client.paths.has_access(lb_service, web_service, 80)
    assert client.paths.internet_accessible(lb_service, 80)

    client.paths.remove(lb_service, web_service, 80)
    assert not client.paths.has_access(lb_service, web_service, 80)

    client.paths.remove(internet, lb_service, 80)
    assert not client.paths.internet_accessible(lb_service, 80)

    client.service.destroy(lb_service)
    client.service.destroy(web_service)
    client.network.destroy(test_network)

@mock_ec2
@mock_elb
@mock_autoscaling
@mock_route53
@pytest.mark.mock_aws
def test_paths_mock():
    """
    Run tests using the mock aws driver (moto).
    """
    run_paths_test(provider="aws", credentials={})

@pytest.mark.aws
def test_paths_aws():
    """
    Run tests against real AWS (using global configuration).
    """
    run_paths_test(provider="aws", credentials={})

@pytest.mark.gce
def test_paths_gce():
    """
    Run tests against real GCE (environment variables below must be set).
    """
    run_paths_test(provider="gce", credentials={
        "user_id": os.environ['BUTTER_GCE_USER_ID'],
        "key": os.environ['BUTTER_GCE_CREDENTIALS_PATH'],
        "project": os.environ['BUTTER_GCE_PROJECT_NAME']})
