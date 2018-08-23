# Butter

:warning: :construction: :skull: This is a proof of concept, do not use in
production. :skull: :construction: :warning:

This tool should make it easier to interact with cloud resources by doing most
of the work that a human doesn't need to care about for you, and by being
transparent about what it's doing.

## Installation

This project depends on [Python
3.6.0](https://www.python.org/downloads/release/python-360/) or greater.  It can
be installed as a normal python package using pip, but an environment manager
such as [pipenv](https://pipenv.readthedocs.io/en/latest/) is recommended.

To install locally, make a dedicated directory where you want to test this out
and run:

```
cd butter_experimentation
pipenv install git+https://github.com/sverch/butter.git#egg=butter
```

Having a dedicated directory will allow pipenv to scope the dependencies to that
project directory and prevent this project from installing stuff on your main
system.

## Client Setup

First, you must create a client object to connect to the cloud platform that
you'll be working with.  The client handles authentication with the cloud
provider, so you must pass it the name of the provider and the authentication
credentials.

If you are trying this project for the first time, it's recommended that you use
the "mock-aws" client.

### Google Compute Engine Client

To use the Google Compute Engine client, you must create a service account and
download the credentials locally.  Because this provider is implemented using
[Apache Libcloud](https://libcloud.apache.org/), you can refer to the [Google
Compute Engine Driver
Setup](https://libcloud.readthedocs.io/en/latest/compute/drivers/gce.html#getting-driver-with-service-account-authentication)
documentation in that project for more details.

When you have the credentials, you can do something like this, preferably in a
dotfile you don't commit to version control.  Note the credentials file is in
JSON format:

```
export BUTTER_GCE_USER_ID="sverch-butter@butter-000000.iam.gserviceaccount.com"
export BUTTER_GCE_CREDENTIALS_PATH="/home/sverch/.gce/credentials.json"
export BUTTER_GCE_PROJECT_NAME="butter-000000"
```

Then, you can run these commands in a python shell to create a GCE client:

```
import butter
import os
client = butter.Client("gce", credentials={
    "user_id": os.environ['BUTTER_GCE_USER_ID'],
    "key": os.environ['BUTTER_GCE_CREDENTIALS_PATH'],
    "project": os.environ['BUTTER_GCE_PROJECT_NAME']})
```

### Amazon Web Services Client

Currently no credentials can be passed in as arguments for the AWS provider
(they are ignored).  However this provider is implemented with
[Boto](http://docs.pythonboto.org/en/latest/), which looks in many other places
for the credentials, so you can configure them in other ways.  See the [boto3
credential setup
documentation](https://boto3.readthedocs.io/en/latest/guide/configuration.html)
for more details.

Once you have set up your credentials, you can run the following to create an
AWS client:

```
import butter
client = butter.Client("aws", credentials={})
```

### Mock Amazon Web Services Client

The Mock AWS client is for demonstration and testing.  Since it is all running
locally, you don't need any credentials.  Simply run:

```
import butter
client = butter.Client("mock-aws", credentials={})
```

## Concepts

There are only four concepts in Butter, a Blueprint, a Network, a Service, and a
Path.

### Blueprint

A blueprint is a YAML file that describes how a Network or a Service should be
configured.  This includes things like max number of servers (which
automatically gets translated to subnetwork size) and the memory and CPU
requirements (which automatically get translated to a virtual machine offering
from the backing provider that can satisfy the requirements).

Examples blueprint files for Networks and Services are shown below.

### Network

A Network is the top level container for everything else.  A Blueprint file for
a network might look like:

```
---
network:
  legacy_network_size_bits: 16
```

The `legacy_network_size_bits` option only matters for the AWS provider, since
GCE lets you creates subnets directly without a top level network, but AWS does
not.  That option tells AWS to create a top level network (VPC) of size 16,
which will mean that the network has 2^16 unique IP addresses in it.  Note that
everything is currently still using IPv4.

Once you have your blueprint file, you can work with networks using the
following commands:

```
client.network.create("dev", blueprint="example-blueprints/network/blueprint.yml")
client.network.discover("dev")
client.network.list()
client.network.destroy("dev")
```

In [ipython](https://ipython.org/), you can run `<object>?` to [get help on any
object](https://ipython.readthedocs.io/en/stable/interactive/python-ipython-diff.html#accessing-help),
for example `client.network.create?`.

### Service

A Service a logical group of instances and whatever resources are needed to
support them (subnetworks, firewalls, etc.).

This is an example of what a service blueprint might look like:

```
---
network:
  subnetwork_max_instance_count: 768

placement:
  availability_zones: 3

instance:
  public_ip: True
  memory: 4GB
  cpus: 1
  gpu: false
  disks:
    - size: 8GB
      type: standard
      device_name: /dev/sda1

image:
  name: "ubuntu/images/hvm-ssd/ubuntu-xenial-16.04-amd64-server-*"

initialization:
  - path: "nginx-cloud-config.yml"
```

The "network" section tells Butter to create subnetworks big enough for 768
instances.

The "placement" section tells Butter to ensure these instances are provisioned
across three availaibility zones (which most cloud providers guarantee are
separated somehow for resilience).

The "instance" section describes the resource reqirements of each server.

container for everything else.  A Blueprint file for
a network might look like:

The example blueprints are different for AWS and GCE because the provided OS
images are different.  If the same base image was created for both platforms
these wouldn't be different.

#### AWS Instances

```
instances = client.instances.create("dev", "private",
                                    blueprint="example-blueprints/aws-nginx/blueprint.yml")
private_ips = [i["PrivateIp"] for i in instances["Instances"]]
client.instances.create("dev", "public",
                        blueprint="example-blueprints/aws-haproxy/blueprint.yml",
                        template_vars={"PrivateIps": private_ips})
client.instances.discover("dev", "public")
client.instances.discover("dev", "private")
client.instances.list()
client.instances.destroy("dev", "public")
client.instances.destroy("dev", "private")
```

#### GCE Instances

```
client.instances.create("dev", "public", blueprint="example-blueprints/gce-apache/blueprint.yml")
client.instances.discover("dev", "public")
client.instances.list()
client.instances.destroy("dev", "public")
```

### Paths (Firewalls)

```
from butter.types.networking import Service, CidrBlock
public_service = Service("dev", "public")
private_service = Service("dev", "private")
internet = CidrBlock("0.0.0.0/0")
client.paths.add(public_service, private_service, 80)
client.paths.add(internet, public_service, 443)
client.paths.list()
client.graph()
```

### Prototype UI

Get a summary in the form of a graphviz compatible dot file by running:

```
client.graph()
```

To generate the vizualizations, run:

```
cd ui && env PROVIDER=<provider> bash graph.sh
```

And open `ui/graph.html` in a browser.

### Blueprint Tester

This project provides a framework to help test that blueprint files work as
expected.

Example (butter must be installed):

```
butter-test --provider aws --blueprint_dir example-blueprints/haproxy run
```

Run `butter-test` with no arguments for usage.

This runner tries to import `blueprint_fixture.BlueprintTest` from the root of
your blueprint directory.  This must be a class that inherits from
`butter.testutils.fixture.BlueprintTestInterface` and implements all the
required methods.  See the documentation on that class for usage details.

The runner expects the blueprint file that you are testing to be name
`blueprint.yml` in the blueprint directory.

See [example-blueprints](example-blueprints) for all examples.

## Testing

To run the local tests run:

```
pipenv install --dev
tox
```

To run tests against GCE and AWS, run:

```
tox -e gce
tox -e aws
```

For GCE, you must set `BUTTER_GCE_USER_ID`, `BUTTER_GCE_CREDENTIALS_PATH`, and
`BUTTER_GCE_PROJECT_NAME` as described above.
