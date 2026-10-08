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
        