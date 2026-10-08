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


    print(f"ID:           {instance['InstanceId']}")
    print(f"Name:         {tags.get('Name', '(no name)')}")
    print(f"State:        {instance['State']['Name']}")
    print(f"Type:         {instance['InstanceType']}")
    print(f"AMI:          {instance['ImageId']}")
    print(f"AZ:           {instance['Placement']['AvailabilityZone']}")
    print(f"Public IP:    {instance.get('PublicIpAddress', '-')}")
    print(f"Private IP:   {instance.get('PrivateIpAddress', '-')}")
    print(f"Key pair:     {instance.get('KeyName', '-')}")
    print(f"Launch time:  {instance['LaunchTime']}")
    print(f"Security groups: {[g['GroupName'] for g in instance['SecurityGroups']]}")
    print("Tags:")
    for k, v in tags.items():
        print(f"  {k} = {v}")


def tag_instance(instance_id, key, value):
    ec2.create_tags(
        Resources=[instance_id],
        Tags=[{'Key': key, 'Value': value}]
    )
    print(f"Tag added: {key} = {value}")


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
        print("9. Cleanup (terminate all boto3-lab instances)")
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
        elif choice == "0":
            break
        else:
            print("Unknown option.")

if __name__ == "__main__":
    main()


def cleanup():
    reponse = ec2.describe_instances(
        Filters=[
            {
                'Name': 'tag:CreatedBy',
                'Values': ['boto3-lab']
            },
            {
                'Name': 'instance-state-name',
                'Values': ['pending','stopping','running', 'stopped']
            }
        ])
    ids = [
        instance['InstanceId']
        for reservation in reponse['Reservations']
        for instance in reservation['Instances']
    ]
    if not ids:
        print("nothing to cleanup")
        return
    print("These instances will be terminated: ")
    for i in ids:
        print("  ", i)

    if input("Are you sure? (y/n) ").strip().lower() != 'y':
        ec2.terminate_instances(InstanceIds=ids)
        print("waiting for instances to terminate ...")
        ec2.get_waiter('instance_terminated').wait(InstanceIds=ids)
        print(f"terminated {len(ids)} instance(s).")