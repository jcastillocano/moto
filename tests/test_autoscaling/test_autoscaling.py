from __future__ import unicode_literals
import boto
import boto3
import boto.ec2.autoscale
from boto.ec2.autoscale.launchconfig import LaunchConfiguration
from boto.ec2.autoscale.group import AutoScalingGroup
from boto.ec2.autoscale import Tag
import boto.ec2.elb
import sure  # noqa

from moto import mock_autoscaling, mock_ec2, mock_elb
from tests.helpers import requires_boto_gte


@mock_autoscaling
@mock_elb
def test_create_autoscaling_group():
    elb_conn = boto.ec2.elb.connect_to_region('us-east-1')
    elb_conn.create_load_balancer('test_lb', zones=[], listeners=[(80, 8080, 'http')])

    conn = boto.ec2.autoscale.connect_to_region('us-east-1')
    config = LaunchConfiguration(
        name='tester',
        image_id='ami-abcd1234',
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)

    group = AutoScalingGroup(
        name='tester_group',
        availability_zones=['us-east-1c', 'us-east-1b'],
        default_cooldown=60,
        desired_capacity=2,
        health_check_period=100,
        health_check_type="EC2",
        max_size=2,
        min_size=2,
        launch_config=config,
        load_balancers=["test_lb"],
        placement_group="test_placement",
        vpc_zone_identifier='subnet-1234abcd',
        termination_policies=["OldestInstance", "NewestInstance"],
        tags=[Tag(
            resource_id='tester_group',
            key='test_key',
            value='test_value',
            propagate_at_launch=True
            )
        ],
    )
    conn.create_auto_scaling_group(group)

    group = conn.get_all_groups()[0]
    group.name.should.equal('tester_group')
    set(group.availability_zones).should.equal(set(['us-east-1c', 'us-east-1b']))
    group.desired_capacity.should.equal(2)
    group.max_size.should.equal(2)
    group.min_size.should.equal(2)
    group.instances.should.have.length_of(2)
    group.vpc_zone_identifier.should.equal('subnet-1234abcd')
    group.launch_config_name.should.equal('tester')
    group.default_cooldown.should.equal(60)
    group.health_check_period.should.equal(100)
    group.health_check_type.should.equal("EC2")
    list(group.load_balancers).should.equal(["test_lb"])
    group.placement_group.should.equal("test_placement")
    list(group.termination_policies).should.equal(["OldestInstance", "NewestInstance"])
    len(list(group.tags)).should.equal(1)
    tag = list(group.tags)[0]
    tag.resource_id.should.equal('tester_group')
    tag.key.should.equal('test_key')
    tag.value.should.equal('test_value')
    tag.propagate_at_launch.should.equal(True)


@mock_autoscaling
def test_create_autoscaling_groups_defaults():
    """ Test with the minimum inputs and check that all of the proper defaults
    are assigned for the other attributes """
    conn = boto.connect_autoscale()
    config = LaunchConfiguration(
        name='tester',
        image_id='ami-abcd1234',
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)

    group = AutoScalingGroup(
        name='tester_group',
        max_size=2,
        min_size=2,
        launch_config=config,
    )
    conn.create_auto_scaling_group(group)

    group = conn.get_all_groups()[0]
    group.name.should.equal('tester_group')
    group.max_size.should.equal(2)
    group.min_size.should.equal(2)
    group.launch_config_name.should.equal('tester')

    # Defaults
    list(group.availability_zones).should.equal([])
    group.desired_capacity.should.equal(2)
    group.vpc_zone_identifier.should.equal('')
    group.default_cooldown.should.equal(300)
    group.health_check_period.should.equal(300)
    group.health_check_type.should.equal("EC2")
    list(group.load_balancers).should.equal([])
    group.placement_group.should.equal(None)
    list(group.termination_policies).should.equal([])
    list(group.tags).should.equal([])


@mock_autoscaling
def test_autoscaling_group_describe_filter():
    conn = boto.connect_autoscale()
    config = LaunchConfiguration(
        name='tester',
        image_id='ami-abcd1234',
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)

    group = AutoScalingGroup(
        name='tester_group',
        max_size=2,
        min_size=2,
        launch_config=config,
    )
    conn.create_auto_scaling_group(group)
    group.name = 'tester_group2'
    conn.create_auto_scaling_group(group)
    group.name = 'tester_group3'
    conn.create_auto_scaling_group(group)

    conn.get_all_groups(names=['tester_group', 'tester_group2']).should.have.length_of(2)
    conn.get_all_groups().should.have.length_of(3)


@mock_autoscaling
def test_autoscaling_update():
    conn = boto.connect_autoscale()
    config = LaunchConfiguration(
        name='tester',
        image_id='ami-abcd1234',
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)

    group = AutoScalingGroup(
        name='tester_group',
        availability_zones=['us-east-1c', 'us-east-1b'],
        desired_capacity=2,
        max_size=2,
        min_size=2,
        launch_config=config,
        vpc_zone_identifier='subnet-1234abcd',
    )
    conn.create_auto_scaling_group(group)

    group = conn.get_all_groups()[0]
    group.vpc_zone_identifier.should.equal('subnet-1234abcd')

    group.vpc_zone_identifier = 'subnet-5678efgh'
    group.update()

    group = conn.get_all_groups()[0]
    group.vpc_zone_identifier.should.equal('subnet-5678efgh')


@mock_autoscaling
def test_autoscaling_group_delete():
    conn = boto.connect_autoscale()
    config = LaunchConfiguration(
        name='tester',
        image_id='ami-abcd1234',
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)

    group = AutoScalingGroup(
        name='tester_group',
        max_size=2,
        min_size=2,
        launch_config=config,
    )
    conn.create_auto_scaling_group(group)

    conn.get_all_groups().should.have.length_of(1)

    conn.delete_auto_scaling_group('tester_group')
    conn.get_all_groups().should.have.length_of(0)


@mock_ec2
@mock_autoscaling
def test_autoscaling_group_describe_instances():
    conn = boto.connect_autoscale()
    config = LaunchConfiguration(
        name='tester',
        image_id='ami-abcd1234',
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)

    group = AutoScalingGroup(
        name='tester_group',
        max_size=2,
        min_size=2,
        launch_config=config,
    )
    conn.create_auto_scaling_group(group)

    instances = list(conn.get_all_autoscaling_instances())
    instances.should.have.length_of(2)
    instances[0].launch_config_name.should.equal('tester')
    autoscale_instance_ids = [instance.instance_id for instance in instances]

    ec2_conn = boto.connect_ec2()
    reservations = ec2_conn.get_all_instances()
    instances = reservations[0].instances
    instances.should.have.length_of(2)
    instance_ids = [instance.id for instance in instances]
    set(autoscale_instance_ids).should.equal(set(instance_ids))
    instances[0].instance_type.should.equal("t2.medium")


@requires_boto_gte("2.8")
@mock_autoscaling
def test_set_desired_capacity_up():
    conn = boto.connect_autoscale()
    config = LaunchConfiguration(
        name='tester',
        image_id='ami-abcd1234',
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)

    group = AutoScalingGroup(
        name='tester_group',
        availability_zones=['us-east-1c', 'us-east-1b'],
        desired_capacity=2,
        max_size=2,
        min_size=2,
        launch_config=config,
        vpc_zone_identifier='subnet-1234abcd',
    )
    conn.create_auto_scaling_group(group)

    group = conn.get_all_groups()[0]
    group.desired_capacity.should.equal(2)
    instances = list(conn.get_all_autoscaling_instances())
    instances.should.have.length_of(2)

    conn.set_desired_capacity("tester_group", 3)
    group = conn.get_all_groups()[0]
    group.desired_capacity.should.equal(3)

    instances = list(conn.get_all_autoscaling_instances())
    instances.should.have.length_of(3)


@requires_boto_gte("2.8")
@mock_autoscaling
def test_set_desired_capacity_down():
    conn = boto.connect_autoscale()
    config = LaunchConfiguration(
        name='tester',
        image_id='ami-abcd1234',
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)

    group = AutoScalingGroup(
        name='tester_group',
        availability_zones=['us-east-1c', 'us-east-1b'],
        desired_capacity=2,
        max_size=2,
        min_size=2,
        launch_config=config,
        vpc_zone_identifier='subnet-1234abcd',
    )
    conn.create_auto_scaling_group(group)

    group = conn.get_all_groups()[0]
    group.desired_capacity.should.equal(2)
    instances = list(conn.get_all_autoscaling_instances())
    instances.should.have.length_of(2)

    conn.set_desired_capacity("tester_group", 1)
    group = conn.get_all_groups()[0]
    group.desired_capacity.should.equal(1)

    instances = list(conn.get_all_autoscaling_instances())
    instances.should.have.length_of(1)


@requires_boto_gte("2.8")
@mock_autoscaling
def test_set_desired_capacity_the_same():
    conn = boto.connect_autoscale()
    config = LaunchConfiguration(
        name='tester',
        image_id='ami-abcd1234',
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)

    group = AutoScalingGroup(
        name='tester_group',
        availability_zones=['us-east-1c', 'us-east-1b'],
        desired_capacity=2,
        max_size=2,
        min_size=2,
        launch_config=config,
        vpc_zone_identifier='subnet-1234abcd',
    )
    conn.create_auto_scaling_group(group)

    group = conn.get_all_groups()[0]
    group.desired_capacity.should.equal(2)
    instances = list(conn.get_all_autoscaling_instances())
    instances.should.have.length_of(2)

    conn.set_desired_capacity("tester_group", 2)
    group = conn.get_all_groups()[0]
    group.desired_capacity.should.equal(2)

    instances = list(conn.get_all_autoscaling_instances())
    instances.should.have.length_of(2)

@mock_autoscaling
@mock_elb
def test_autoscaling_group_with_elb():
    elb_conn = boto.connect_elb()
    zones = ['us-east-1a', 'us-east-1b']
    ports = [(80, 8080, 'http'), (443, 8443, 'tcp')]
    lb = elb_conn.create_load_balancer('my-lb', zones, ports)
    instances_health = elb_conn.describe_instance_health('my-lb')
    instances_health.should.be.empty

    conn = boto.connect_autoscale()
    config = LaunchConfiguration(
        name='tester',
        image_id='ami-abcd1234',
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)
    group = AutoScalingGroup(
        name='tester_group',
        max_size=2,
        min_size=2,
        launch_config=config,
        load_balancers=["my-lb"],
    )
    conn.create_auto_scaling_group(group)
    group = conn.get_all_groups()[0]
    elb = elb_conn.get_all_load_balancers()[0]
    group.desired_capacity.should.equal(2)
    elb.instances.should.have.length_of(2)

    autoscale_instance_ids = set(instance.instance_id for instance in group.instances)
    elb_instace_ids = set(instance.id for instance in elb.instances)
    autoscale_instance_ids.should.equal(elb_instace_ids)

    conn.set_desired_capacity("tester_group", 3)
    group = conn.get_all_groups()[0]
    elb = elb_conn.get_all_load_balancers()[0]
    group.desired_capacity.should.equal(3)
    elb.instances.should.have.length_of(3)

    autoscale_instance_ids = set(instance.instance_id for instance in group.instances)
    elb_instace_ids = set(instance.id for instance in elb.instances)
    autoscale_instance_ids.should.equal(elb_instace_ids)

    conn.delete_auto_scaling_group('tester_group')
    conn.get_all_groups().should.have.length_of(0)
    elb = elb_conn.get_all_load_balancers()[0]
    elb.instances.should.have.length_of(0)


'''
Boto3
'''


@mock_autoscaling
def test_create_autoscaling_group_boto3():
        client = boto3.client('autoscaling', region_name='us-east-1')
        _ = client.create_launch_configuration(
            LaunchConfigurationName='test_launch_configuration'
        )
        response = client.create_auto_scaling_group(
            AutoScalingGroupName='test_asg',
            LaunchConfigurationName='test_launch_configuration',
            MinSize=0,
            MaxSize=20,
            DesiredCapacity=5
        )
        response['ResponseMetadata']['HTTPStatusCode'].should.equal(200)


@mock_autoscaling
def test_describe_autoscaling_groups_boto3():
        client = boto3.client('autoscaling', region_name='us-east-1')
        _ = client.create_launch_configuration(
            LaunchConfigurationName='test_launch_configuration'
        )
        _ = client.create_auto_scaling_group(
            AutoScalingGroupName='test_asg',
            LaunchConfigurationName='test_launch_configuration',
            MinSize=0,
            MaxSize=20,
            DesiredCapacity=5
        )
        response = client.describe_auto_scaling_groups(
            AutoScalingGroupNames=["test_asg"]
        )
        response['ResponseMetadata']['HTTPStatusCode'].should.equal(200)
        response['AutoScalingGroups'][0]['AutoScalingGroupName'].should.equal('test_asg')

@mock_autoscaling
def test_update_autoscaling_group_boto3():
    client = boto3.client('autoscaling', region_name='us-east-1')
    _ = client.create_launch_configuration(
        LaunchConfigurationName='test_launch_configuration'
    )
    _ = client.create_auto_scaling_group(
        AutoScalingGroupName='test_asg',
        LaunchConfigurationName='test_launch_configuration',
        MinSize=0,
        MaxSize=20,
        DesiredCapacity=5
    )

    response = client.update_auto_scaling_group(
        AutoScalingGroupName='test_asg',
        MinSize=1,
    )

    response = client.describe_auto_scaling_groups(
        AutoScalingGroupNames=["test_asg"]
    )
    response['AutoScalingGroups'][0]['MinSize'].should.equal(1)
