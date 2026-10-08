import boto3
from botocore.exceptions import ClientError , WaiterError

REGION = 'us-east-1'
ec2 = boto3.client('ec2', region_name=REGION)
ssm = boto3.client('ssm', region_name=REGION)


def list_instances():
    paginator = ec2.get_paginator('describe_instances')
    rows = []
    for page in paginator.paginate():
        for  reservation in page['Reservations']:
            for instance in reservation['Instances']:
                for inst in reservation['Instances']:
                    rows.append(inst)
    for inst in rows:
        if inst['State']['Name'] == 'terminated':
            continue
        tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}   
        print(f"{inst['InstanceId']:<21} "
              f"{inst['InstanceType']:<12} "
              f"{inst['State']['Name']:<12} "
              f"{inst.get('PublicIpAddress', '-'):<16} "
              f"{tags.get('Name', '(no name)')}")

def get_latest_amazon_linux_ami():
    parameter = ("/aws/service/ami-amazon-linux-latest/"
                 "al2023-ami-kernel-default-x86_64")
    response = ssm.get_parameter(Name=parameter)
    return response['Parameter']['Value']

def launch_instance(name):
    ami_id = get_latest_amazon_linux_ami()
    print(f"Using latest Amazon Linux 2023 AMI: {ami_id}")

    reponse = ec2.run_instances(
        ImageId=ami_id,
        InstanceType='t3.micro',
        MinCount=1,
        MaxCount=1,
        KeyName="vockey",
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': name},
                    {'Key' : "CreatedBy", 'Value' : "boto3-lab"},
                ],
            }
        ],)
    instance_id = reponse['Instances'][0]['InstanceId']
    state= reponse['Instances'][0]['State']['Name']
    print(f"Instance launched: {instance_id} with state: {state}")
    return instance_id


def wait_running(instance_id):
    try:
        print("Waiting for the instance to reach 'running' ...")
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(
            InstanceIds=[instance_id],
            WaiterConfig={
                'Delay': 15,
                'MaxAttempts': 40,
            }
        )
    except WaiterError as e:
        print("timed out . check the Console")
        return 

    detail= ec2.describe_instances(InstanceIds=[instance_id])
    running= detail['Reservations'][0]['Instances'][0]
    print("Public IP address: ", running.get('PublicIpAddress', 'not assigned'))


def start_instance(instance_id):
    r= ec2.start_instances(InstanceIds=[instance_id])
    change= r['StartingInstances'][0]
    print(change["PreviousState"]["Name"], "->", change["CurrentState"]["Name"])
    ec2.get_waiter('instance_running').wait(InstanceIds=[instance_id])

def stop_instance(instance_id):
    r= ec2.stop_instances(InstanceIds=[instance_id])
    change= r['StoppingInstances'][0]
    print(change["PreviousState"]["Name"], "->", change["CurrentState"]["Name"])
    ec2.get_waiter('instance_stopped').wait(InstanceIds=[instance_id])

def reboot_instance(instance_id):
    r= ec2.reboot_instances(InstanceIds=[instance_id])
    change= r["RebootingInstances"][0] if "RebootInstances" in r else None
    if change:
        print(change["PreviousSatet"]["Name"], "->", change["CurrentState"]["Name"])


def describe_instance(instance_id):
    d= ec2.describe_instances(InstanceIds=[instance_id])
    instance= d['Reservations'][0]['Instances'][0]
    tags= {t['Key']: t['Value'] for t in instance.get('Tags', [])}


    print(f"ID:           {inst['InstanceId']}")
    print(f"Name:         {tags.get('Name', '(no name)')}")
    print(f"State:        {inst['State']['Name']}")
    print(f"Type:         {inst['InstanceType']}")
    print(f"AMI:          {inst['ImageId']}")
    print(f"AZ:           {inst['Placement']['AvailabilityZone']}")
    print(f"Public IP:    {inst.get('PublicIpAddress', '-')}")
    print(f"Private IP:   {inst.get('PrivateIpAddress', '-')}")
    print(f"Key pair:     {inst.get('KeyName', '-')}")
    print(f"Launch time:  {inst['LaunchTime']}")
    print(f"Security groups: {[g['GroupName'] for g in inst['SecurityGroups']]}")
    print("Tags:")
    for k, v in tags.items():
        print(f"  {k} = {v}")


def tag_instance(instance_id, key, value):
    ec2.create_tags(
        Resources=[instance_id],
        Tags=[{'Key': key, 'Value': value}]
    )
    print(f"Tag added: {key} = {value}")