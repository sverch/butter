"""
Test for temporary SSH key setup.
"""
import os
from io import StringIO
import pytest
from moto import mock_ec2, mock_autoscaling, mock_elb, mock_route53
import paramiko
import butter
from butter.types.common import Service
from butter.types.networking import CidrBlock
from butter.testutils.blueprint_tester import generate_unique_name, call_with_retries
from butter.testutils.ssh import create_test_instance

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

# pylint: disable=too-many-locals,too-many-statements
def run_ssh_test(provider, credentials):
    """
    Test that the instance management works against the given provider.
    """

    # Get the client for this test
    client = butter.Client(provider, credentials)

    # Get a somewhat unique network name
    network_name = generate_unique_name("unittest")

    # Provision all the resources
    test_network = client.network.create(network_name, blueprint=NETWORK_BLUEPRINT)
    if provider in ["aws", "mock-aws"]:
        test_service = create_test_instance(client, test_network, provider, AWS_SERVICE_BLUEPRINT,
                                            ssh_setup_method="provider-default")
    else:
        assert provider == "gce"
        test_service = create_test_instance(client, test_network, provider, GCE_SERVICE_BLUEPRINT,
                                            ssh_setup_method="provider-default")

    def validate_service(network, service, count):
        discovered_service = client.service.get(network, service.name)
        assert discovered_service.network == network
        assert discovered_service.name == service.name
        assert discovered_service == service
        assert isinstance(discovered_service, Service)
        assert isinstance(service, Service)
        instances = []
        for subnetwork in discovered_service.subnetworks:
            instances.extend(subnetwork.instances)
        assert len(instances) == count
        assert instances == client.service.get_instances(service)

    # Check that our service is provisioned properly
    validate_service(test_network, test_service.service, 1)

    # Add a path for SSH
    internet = CidrBlock("0.0.0.0/0")
    client.paths.add(internet, test_service.service, 22)

    if provider != "mock-aws":
        # Test that we can connect with the given key
        def attempt_connection():
            ssh = paramiko.SSHClient()
            ssh_key = paramiko.RSAKey(file_obj=StringIO(test_service.private_key))
            public_ip = [i.public_ip for i in client.service.get_instances(test_service.service)][0]
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=public_ip, username="ubuntu", pkey=ssh_key)
            return ssh
        call_with_retries(attempt_connection, int(10), float(1.0))
        ssh = attempt_connection()
        _, ssh_stdout, ssh_stderr = ssh.exec_command("whoami")
        assert ssh_stdout.read().decode().strip() == "ubuntu"
        assert ssh_stderr.read().decode().strip() == ""

    # Make sure they are gone when I destroy them
    client.service.destroy(test_service.service)

    # Clean up the VPC
    client.network.destroy(test_network)

# Despite the fact that the mock-aws provider uses moto, we must also annotate it here since the
# test uses the AWS client directly to verify that things were created as expected.
@mock_ec2
@mock_elb
@mock_autoscaling
@mock_route53
@pytest.mark.mock_aws
def test_ssh_mock():
    """
    Run tests using the mock aws driver (moto).
    """
    run_ssh_test(provider="mock-aws", credentials={})

@pytest.mark.aws
def test_ssh_aws():
    """
    Run tests against real AWS (using global configuration).
    """
    run_ssh_test(provider="aws", credentials={})

@pytest.mark.gce
def test_ssh_gce():
    """
    Run tests against real GCE (environment variables below must be set).
    """
    run_ssh_test(provider="gce", credentials={
        "user_id": os.environ['BUTTER_GCE_USER_ID'],
        "key": os.environ['BUTTER_GCE_CREDENTIALS_PATH'],
        "project": os.environ['BUTTER_GCE_PROJECT_NAME']})
