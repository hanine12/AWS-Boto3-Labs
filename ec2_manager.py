import boto3
from botocore.exceptions import ClientError, WaiterError
import urllib.request
from datetime import datetime, timezone

REGION = 'us-east-1'
ec2 = boto3.client('ec2', region_name=REGION)
ssm = boto3.client('ssm', region_name=REGION)

T3_MICRO_PRICE = 0.0104  


SG_NAME = "boto3-lab-web"
TAG_CREATED_BY = {"Key": "CreatedBy", "Value": "boto3-lab"}

USER_DATA_TEMPLATE = """#!/bin/bash
dnf install -y httpd
echo "<h1>Hello from $(hostname -f)</h1><p>Deployed by {student_name}</p>" > /var/www/html/index.html
systemctl enable --now httpd
"""


def estimate_cost(instance_id):

    d=ec2.describe_instances(InstanceIds=[instance_id])
    inst = d['Reservations'][0]['Instances'][0]

    launch= inst['LaunchTime']
    now = datetime.now(timezone.utc)
    uptime = now - launch
    hours = uptime.total_seconds() / 3600

    cost = hours * T3_MICRO_PRICE
    print(f"Instance:  {instance_id}")
    print(f"Launched:  {launch.isoformat()}")
    print(f"Uptime:    {uptime}  ({hours:.3f} hours)")
    print(f"Rate:      ${T3_MICRO_HOURLY}/hour (t3.micro, us-east-1)")
    print(f"Cost so far: ${cost:.4f}")

    return cost


def build_user_data(student_name):
    return USER_DATA_TEMPLATE.format(student_name=student_name)


# ---------- Step 2: AMI from SSM ----------
def get_latest_amazon_linux_ami():
    parameter = ("/aws/service/ami-amazon-linux-latest/"
                 "al2023-ami-kernel-default-x86_64")
    response = ssm.get_parameter(Name=parameter)
    return response['Parameter']['Value']


# ---------- Step 1: list ----------
def list_instances():
    paginator = ec2.get_paginator('describe_instances')
    rows = []
    for page in paginator.paginate():
        for reservation in page['Reservations']:
            for inst in reservation['Instances']:
                rows.append(inst)          # FIX: single inner loop

    print(f"{'InstanceId':<21} {'Type':<12} {'State':<12} {'PublicIP':<16} Name")
    print("-" * 80)
    for inst in rows:
        if inst['State']['Name'] == 'terminated':   # FIX: no space in key
            continue
        tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
        print(f"{inst['InstanceId']:<21} "
              f"{inst['InstanceType']:<12} "
              f"{inst['State']['Name']:<12} "
              f"{inst.get('PublicIpAddress', '-'):<16} "
              f"{tags.get('Name', '(no name)')}")


# ---------- Step 3 + 4: launch + wait ----------
def launch_instance(name):
    ami_id = get_latest_amazon_linux_ami()
    print(f"Using latest Amazon Linux 2023 AMI: {ami_id}")
    response = ec2.run_instances(
        ImageId=ami_id,
        InstanceType='t3.micro',
        MinCount=1,
        MaxCount=1,
        KeyName="vockey",
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [
                {'Key': 'Name', 'Value': name},
                TAG_CREATED_BY,
            ],
        }],
    )
    iid = response['Instances'][0]['InstanceId']
    state = response['Instances'][0]['State']['Name']
    print(f"Launched {iid}, state = {state}")
    return iid


def wait_running(instance_id):
    try:
        print("Waiting for the instance to reach 'running' ...")
        ec2.get_waiter('instance_running').wait(
            InstanceIds=[instance_id],
            WaiterConfig={'Delay': 15, 'MaxAttempts': 40},
        )
        print("Instance is running.")
        detail = ec2.describe_instances(InstanceIds=[instance_id])
        inst = detail['Reservations'][0]['Instances'][0]
        print("Public IP:", inst.get('PublicIpAddress', 'not assigned'))
    except WaiterError:
        print("Timed out. Check the Console.")


# ---------- Step 5: start / stop / reboot ----------
def start_instance(instance_id):
    r = ec2.start_instances(InstanceIds=[instance_id])
    change = r['StartingInstances'][0]
    print(change['PreviousState']['Name'], '->', change['CurrentState']['Name'])
    ec2.get_waiter('instance_running').wait(InstanceIds=[instance_id])
    print("Instance is running.")


def stop_instance(instance_id):
    r = ec2.stop_instances(InstanceIds=[instance_id])
    change = r['StoppingInstances'][0]
    print(change['PreviousState']['Name'], '->', change['CurrentState']['Name'])
    ec2.get_waiter('instance_stopped').wait(InstanceIds=[instance_id])
    print("Instance is stopped.")


def reboot_instance(instance_id):
    # Reboot has NO waiter — the instance never leaves 'running'.
    ec2.reboot_instances(InstanceIds=[instance_id])
    print(f"Reboot requested for {instance_id} (no waiter — state stays 'running').")


# ---------- Step 6: describe + tag ----------
def describe_instance(instance_id):
    d = ec2.describe_instances(InstanceIds=[instance_id])
    inst = d['Reservations'][0]['Instances'][0]
    tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}

    print(f"ID:              {inst['InstanceId']}")
    print(f"Name:            {tags.get('Name', '(no name)')}")
    print(f"State:           {inst['State']['Name']}")
    print(f"Type:            {inst['InstanceType']}")
    print(f"AMI:             {inst['ImageId']}")
    print(f"AZ:              {inst['Placement']['AvailabilityZone']}")
    print(f"Public IP:       {inst.get('PublicIpAddress', '-')}")
    print(f"Private IP:      {inst.get('PrivateIpAddress', '-')}")
    print(f"Key pair:        {inst.get('KeyName', '-')}")
    print(f"Launch time:     {inst['LaunchTime']}")
    sgs = [f"{g['GroupName']} ({g['GroupId']})" for g in inst.get('SecurityGroups', [])]
    print(f"Security groups: {sgs}")
    print("Tags:")
    for k, v in tags.items():
        print(f"  {k} = {v}")


def tag_instance(instance_id, key, value):
    ec2.create_tags(Resources=[instance_id], Tags=[{'Key': key, 'Value': value}])
    print(f"Tag added: {key} = {value}")


# ---------- Challenge: security group ----------
def get_or_create_web_sg():
    # Try to find an existing one (idempotent)
    existing = ec2.describe_security_groups(
        Filters=[
            {'Name': 'group-name', 'Values': [SG_NAME]},
            {'Name': 'tag:CreatedBy', 'Values': ['boto3-lab']},
        ]
    )
    if existing['SecurityGroups']:
        gid = existing['SecurityGroups'][0]['GroupId']
        print(f"Reusing existing security group: {gid}")
        return gid

    try:
        sg = ec2.create_security_group(
            GroupName=SG_NAME,
            Description="Allow HTTP traffic to web server",
            TagSpecifications=[{
                'ResourceType': 'security-group',
                'Tags': [
                    TAG_CREATED_BY,
                    {'Key': 'Name', 'Value': SG_NAME},
                ],
            }],
        )
        gid = sg['GroupId']
        print(f"Created security group: {gid}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidGroup.Duplicate':
            print("SG already exists — reusing.")
            existing = ec2.describe_security_groups(
                Filters=[{'Name': 'group-name', 'Values': [SG_NAME]}]
            )
            return existing['SecurityGroups'][0]['GroupId']
        raise

    ec2.authorize_security_group_ingress(
        GroupId=gid,
        IpPermissions=[{
            'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'IpRanges': [{'CidrIp': '0.0.0.0/0',
                          'Description': 'Allow HTTP'}],
        }],
    )
    print("Authorized HTTP (port 80) from 0.0.0.0/0")
    return gid


# ---------- Challenge: deploy web server ----------
def deploy_web_server(student_name):
    group_id = get_or_create_web_sg()
    ami_id = get_latest_amazon_linux_ami()
    user_data = build_user_data(student_name)

    print(f"Using latest Amazon Linux 2023 AMI: {ami_id}")
    response = ec2.run_instances(
        ImageId=ami_id,
        InstanceType='t3.micro',
        MinCount=1,
        MaxCount=1,
        KeyName="vockey",
        SecurityGroupIds=[group_id],
        UserData=user_data,
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [
                {'Key': 'Name', 'Value': 'boto3-lab-web'},
                TAG_CREATED_BY,
            ],
        }],
    )
    iid = response['Instances'][0]['InstanceId']
    print(f"Launched {iid}, waiting for 'running' ...")

    ec2.get_waiter('instance_running').wait(
        InstanceIds=[iid],
        WaiterConfig={'Delay': 15, 'MaxAttempts': 40},
    )
    print("State: running. Waiting for status checks (OS boot) ...")

    ec2.get_waiter('instance_status_ok').wait(
        InstanceIds=[iid],
        WaiterConfig={'Delay': 15, 'MaxAttempts': 40},
    )
    print("Instance status: OK.")

    detail = ec2.describe_instances(InstanceIds=[iid])
    inst = detail['Reservations'][0]['Instances'][0]
    public_ip = inst.get('PublicIpAddress')
    if not public_ip:
        print("No public IP assigned — cannot print URL.")
        return iid

    url = f"http://{public_ip}/"
    print(f"URL: {url}")

    # Bonus: check the page from Python
    print("Checking the page from Python ...")
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read(200).decode(errors='replace')
            print(f"HTTP status: {resp.status}")
            print(f"Body (first 200 chars): {body}")
    except Exception as e:
        print(f"Page check failed: {e}")

    return iid


# ---------- Step 7: cleanup (instances + SGs) ----------
def cleanup():
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:CreatedBy', 'Values': ['boto3-lab']},
            {'Name': 'instance-state-name',
             'Values': ['pending', 'running', 'stopping', 'stopped']},
        ]
    )
    ids = [
        inst['InstanceId']
        for res in response['Reservations']
        for inst in res['Instances']
    ]

    # Security groups tagged CreatedBy=boto3-lab
    sgs = ec2.describe_security_groups(
        Filters=[{'Name': 'tag:CreatedBy', 'Values': ['boto3-lab']}]
    )['SecurityGroups']
    sg_ids = [sg['GroupId'] for sg in sgs]

    if not ids and not sg_ids:
        print("Nothing to clean up.")
        return

    if ids:
        print("These instances will be terminated:")
        for i in ids:
            print("  ", i)
    if sg_ids:
        print("These security groups will be deleted:")
        for g in sg_ids:
            print("  ", g)

    if input("Type YES to confirm: ").strip() != "YES":
        print("Cleanup aborted.")
        return

    if ids:
        ec2.terminate_instances(InstanceIds=ids)
        print("Waiting for instances to terminate ...")
        ec2.get_waiter('instance_terminated').wait(InstanceIds=ids)
        print(f"Terminated {len(ids)} instance(s).")

    # SGs can only be deleted once no ENIs reference them; give AWS a moment.
    for gid in sg_ids:
        try:
            ec2.delete_security_group(GroupId=gid)
            print(f"Deleted security group {gid}")
        except ClientError as e:
            print(f"Could not delete {gid}: {e.response['Error']['Code']} "
                  f"(likely still in use — retry in a minute)")


# ---------- Menu ----------
def main():
    while True:
        print("\n1. List instances")
        print("2. Launch instance")
        print("3. Start instance")
        print("4. Stop instance")
        print("5. Reboot instance")
        print("6. Describe instance")
        print("7. Tag instance")
        print("8. Get latest AMI")
        print("9. Cleanup (terminate all boto3-lab instances + SGs)")
        print("10. Deploy Web Server (challenge)")
        print("11. Estimate Cost")
        print("0. Exit")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            list_instances()
        elif choice == "2":
            name = input("Name tag for the instance: ").strip()
            iid = launch_instance(name)
            wait_running(iid)
        elif choice == "3":
            start_instance(input("Instance ID: ").strip())
        elif choice == "4":
            stop_instance(input("Instance ID: ").strip())
        elif choice == "5":
            reboot_instance(input("Instance ID: ").strip())
        elif choice == "6":
            describe_instance(input("Instance ID: ").strip())
        elif choice == "7":
            iid = input("Instance ID: ").strip()
            key = input("Tag key: ").strip()
            val = input("Tag value: ").strip()
            tag_instance(iid, key, val)
        elif choice == "8":
            print(get_latest_amazon_linux_ami())
        elif choice == "9":
            cleanup()
        elif choice == "10":
            name = input("Your name (shown on the page): ").strip() or "Student"
            deploy_web_server(name)
        elif choice == "11":
            estimate_cost(input("Instance ID: ").strip())
        elif choice == "0":
            break
        else:
            print("Unknown option.")


if __name__ == "__main__":
    main()