import mimetypes
import os
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, WaiterError

STUDENT = "hanine"                  

BUCKET = f"{STUDENT}-gallery-2026"
TABLE_NAME = f"{STUDENT}_Images"
SG_NAME = f"{STUDENT}-gallery-web"

IMAGE_FILE = "image.png"                  # your image, in this folder
IMAGE_ID = os.path.basename(IMAGE_FILE)   # "photo.png"
IMAGE_KEY = "images/" + IMAGE_ID          # "images/photo.png"

AMI_PARAM = ("/aws/service/ami-amazon-linux-latest/"
             "al2023-ami-kernel-default-x86_64")
INSTANCE_PROFILE = "LabInstanceProfile"
INSTANCE_TYPE = "t3.micro"
KEY_NAME = "vockey"

session = boto3.session.Session()
REGION = session.region_name or "us-east-1"

s3 = session.client("s3", region_name=REGION)
ec2 = session.client("ec2", region_name=REGION)
ssm = session.client("ssm", region_name=REGION)
sts = session.client("sts", region_name=REGION)
dynamodb = session.resource("dynamodb", region_name=REGION)
ddb_client = session.client("dynamodb", region_name=REGION)



def show_identity():
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    print(f"Account ID : {identity['Account']}")
    print(f"User ID    : {identity['UserId']}")
    print(f"ARN        : {identity['Arn']}")
    

def explain(e):
    if isinstance(e, NoCredentialsError):
        print("No AWS credentials found. Check ~/.aws/credentials.")
        return

    code = e.response.get("Error", {}).get("Code", "Unknown")
    msg = e.response.get("Error", {}).get("Message", str(e))

    if code == "ExpiredToken":
        print("Your AWS session has expired. "
              "Refresh your lab credentials and try again.")
    elif code == "AccessDenied":
        print(f"Access denied ({code}). You may not have permission: {msg}")
    elif code == "NoSuchBucket":
        print("That bucket does not exist yet — create it first (option 2).")
    elif code == "ResourceNotFoundException":
        print("That resource does not exist (table/item?).")
    elif code == "InvalidGroup.Duplicate":
        print("The security group already exists — reusing it.")
    else:
        print(f"AWS error [{code}]: {msg}")


# ======================================================== PART 1 - S3 ====

def create_bucket():
    name=BUCKET
    try:
            if REGION == "us-east-1":
                s3.create_bucket(Bucket=name)
            else:
                s3.create_bucket(
                    Bucket=name,
                    CreateBucketConfiguration={"LocationConstraint": REGION},
                )
            print(f"Created bucket '{name}'")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "BucketAlreadyExists":
            print("That name is taken by another AWS account.")
        elif code == "BucketAlreadyOwnedByYou":
            print("You already own that bucket.")
        else:
            print(f"[AWS ERROR] {code}")
    

def upload_image():
    path = IMAGE_FILE
    bucket = BUCKET
    
    if not os.path.isfile(path):
        print(f"image not found: {path}")
        return
    
    default_key = os.path.basename(path)
    key = input(f"Object key [{default_key}]: ").strip() or default_key
    
    s3.upload_file(path, bucket, key,ExtraArgs={"ContentType": "image/png"},)
    print(f"Uploaded {path} -> s3://{bucket}/{key}")
  

def list_bucket():
    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    total = 0
    try:
        for page in paginator.paginate(Bucket=BUCKET):
            for obj in page.get("Contents", []):
                print(f"{obj['Size']:>12,}  {obj['Key']}")
                count += 1
                total += obj["Size"]
        print(f"\n{count} object(s), {total:,} bytes total.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchBucket":
            print(f"Bucket '{BUCKET}' does not exist — create it first.")
        else:
            raise


# ======================================================== PART 2 - DDB ===

def create_table():
    try:
        new_table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'image_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'image_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print(f"Creating table {TABLE_NAME}...")
        new_table.wait_until_exists()
        print(f"Table {TABLE_NAME} created successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table {TABLE_NAME} already exists.")
        else:
            raise



def save_metadata(size, content_type):
    if size is None:
        print("No size available — upload the image first (option 3).")
        return
    if content_type is None:
        content_type = mimetypes.guess_type(IMAGE_FILE)[0] or "image/png"

    table = dynamodb.Table(TABLE_NAME)
    uploaded_at = datetime.now(timezone.utc).isoformat()

    table.put_item(Item={
        "image_id":       IMAGE_ID,
        "file_size_bytes": size,
        "content_type":   content_type,
        "uploaded_by":    STUDENT,
        "uploaded_at":    uploaded_at,
    })
    print(f"Saved metadata for '{IMAGE_ID}' at {uploaded_at}.")



def read_metadata():
    table = dynamodb.Table(TABLE_NAME)
    try:
        resp = table.get_item(Key={"image_id": IMAGE_ID})
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"Table '{TABLE_NAME}' does not exist — create it first.")
            return
        raise

    item = resp.get("Item")
    if not item:
        print(f"No metadata found for image_id='{IMAGE_ID}'.")
        return

    print(f"Metadata for '{IMAGE_ID}':")
    for k, v in item.items():
        print(f"  {k:<18} {v}")
  


# ======================================================== PART 3 - EC2 ===

def load_user_data():
    """
    """
    with open("user_data.sh") as f:
        script = f.read()

    script = (script
              .replace("__BUCKET__", BUCKET)
              .replace("__TABLE__", TABLE_NAME)
              .replace("__REGION__", REGION)
              .replace("__IMAGE_KEY__", IMAGE_KEY)
              .replace("__IMAGE_ID__", IMAGE_ID))

    if "__" in script:
        print("WARNING: a placeholder was not replaced!")
    return script


def create_security_group():
    response = ec2.create_security_group(
        GroupName=SG_NAME,
        Description="Image gallery web server - port 80",
    )
    sg_id = response["GroupId"]
 
    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            "IpProtocol": "tcp",
            "FromPort": 80,
            "ToPort": 80,
            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
        }],
    )
    return sg_id



def get_latest_ami():
    response = ssm.get_parameter(Name=AMI_PARAM)
    return response['Parameter']['Value']



def launch_web_server(sg_id):
    ami_id = get_latest_ami()
    script = load_user_data()

    resp = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        SecurityGroupIds=[sg_id],
        IamInstanceProfile={"Name": INSTANCE_PROFILE},
        UserData=script,
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name",  "Value": f"{STUDENT}-gallery-web"},
                {"Key": "Owner", "Value": STUDENT},
            ],
        }],
    )
    instance_id = resp["Instances"][0]["InstanceId"]
    print(f"Launched instance {instance_id}. Waiting for 'running'...")

    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])

    desc = ec2.describe_instances(InstanceIds=[instance_id])
    ip = desc["Reservations"][0]["Instances"][0].get("PublicIpAddress")
    if ip:
        print(f"Open this in your browser: http://{ip}")
    else:
        print("Instance running but no public IP yet — try option 10.")


def show_url():
    resp = ec2.describe_instances(Filters=[
        {"Name": "tag:Owner", "Values": [STUDENT]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ])
    ids = [(i["InstanceId"], i.get("PublicIpAddress"))
           for r in resp["Reservations"] for i in r["Instances"]]
    if not ids:
        print("No running instance found.")
        return
    for iid, ip in ids:
        print(f"{iid}  ->  Open this in your browser: http://{ip}")


def debug_console_output():
    """
    """
    try:
        response = ec2.describe_instances(Filters=[
            {"Name": "tag:Owner", "Values": [STUDENT]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ])
        ids = [i["InstanceId"] for r in response["Reservations"]
               for i in r["Instances"]]
        if not ids:
            print("No running instance.")
            return
        out = ec2.get_console_output(InstanceId=ids[0]).get("Output", "")
        if not out:
            print("Console output not ready yet - wait a minute, try again.")
            return
        print("----- last 40 lines of the boot log -----")
        print("\n".join(out.splitlines()[-40:]))
        print("-----------------------------------------")
    except ClientError as e:
        explain(e)


# ======================================================== PART 4 =========

def cleanup():
    try:
        resp = ec2.describe_instances(Filters=[
            {"Name": "tag:Owner", "Values": [STUDENT]},
            {"Name": "instance-state-name",
            "Values": ["pending", "running", "stopping", "stopped"]},
        ])
        ids = [i["InstanceId"] for r in resp["Reservations"]
            for i in r["Instances"]]
        if ids:
            ec2.terminate_instances(InstanceIds=ids)
            print(f"Terminating {len(ids)} instance(s)...")
            ec2.get_waiter("instance_terminated").wait(InstanceIds=ids)
            print("Instances terminated.")
        else:
            print("No instances to terminate.")
    except ClientError as e :
       explain(e)

    try:
        resp = ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [SG_NAME]}])
        for sg in resp["SecurityGroups"]:
            try:
                ec2.delete_security_group(GroupId=sg["GroupId"])
                print(f"Deleted security group {sg['GroupId']}.")
            except ClientError as e:
                if e.response["Error"]["Code"] in (
                        "InvalidGroup.NotFound", "DependencyViolation"):
                    print(f"Could not delete SG {sg['GroupId']}: "
                          f"{e.response['Error']['Code']}")
                else:
                    raise
        if not resp["SecurityGroups"]:
            print("No security group to delete.")
    except ClientError as e:
        explain(e)

 
    try:
        paginator = s3.get_paginator("list_objects_v2")
        deleted = 0
        for page in paginator.paginate(Bucket=BUCKET):
            objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objs:
                s3.delete_objects(Bucket=BUCKET,
                                  Delete={"Objects": objs})
                deleted += len(objs)
        s3.delete_bucket(Bucket=BUCKET)
        print(f"Emptied and deleted bucket '{BUCKET}' ({deleted} object(s)).")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchBucket", "404"):
            print(f"Bucket '{BUCKET}' does not exist — nothing to delete.")
        else:
            explain(e)


    try:
        ddb_client.delete_table(TableName=TABLE_NAME)
        print(f"Deleting table '{TABLE_NAME}' ...")
        ddb_client.get_waiter("table_not_exists").wait(TableName=TABLE_NAME)
        print("Table deleted.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"Table '{TABLE_NAME}' does not exist — nothing to delete.")
        else:
            explain(e)
  


# ======================================================== MENU ===========

MENU = """
=========================================
            IMAGE GALLERY
=========================================
  1. Show my AWS identity        (0.1)
  2. Create the S3 bucket        (1.1)
  3. Upload the image            (1.2)
  4. List the bucket             (1.3)
  5. Create the DynamoDB table   (2.1)
  6. Save the image metadata     (2.2)
  7. Read the metadata back      (2.3)
  8. Create the security group   (3.1)
  9. Launch the web server       (3.3 + 3.4)
 10. Show the server URL
 11. Debug: the instance boot log
  C. CLEAN UP everything         (4.2)
  0. Exit
=========================================
"""


def main():
    if STUDENT == "hanine hosni":
        print("Set STUDENT at the top of this file to your own name first.")
        sys.exit(1)

    print(f"Region: {REGION}   Student: {STUDENT}")
    print(f"Bucket: {BUCKET}   Table: {TABLE_NAME}")

    size = content_type = None

    while True:
        print(MENU)
        choice = input("Choose an option: ").strip().upper()

        try:
            if choice == "0":
                print("Did you clean up?")
                sys.exit(0)
            elif choice == "1":
                show_identity()
            elif choice == "2":
                create_bucket()
            elif choice == "3":
                size,content_type = upload_image()
            elif choice == "4":
                list_bucket()
            elif choice == "5":
                create_table()
            elif choice == "6":
                if size is None and os.path.isfile(IMAGE_FILE):
                    size = os.path.getsize(IMAGE_FILE)
                    content_type = (mimetypes.guess_type(IMAGE_FILE)[0]
                                    or "image/png")
                save_metadata(size, content_type)
            elif choice == "7":
                read_metadata()
            elif choice == "8":
                create_security_group()
            elif choice == "9":
                sg_id = create_security_group()
                launch_web_server(sg_id)
            elif choice == "10":
                show_url()
            elif choice == "11":
                debug_console_output()
            elif choice == "C":
                cleanup()
            else:
                print("Invalid option.")

        except NoCredentialsError:
            print("No credentials found. Check ~/.aws/credentials")
        except ClientError as e:
            explain(e)
        except WaiterError:
            print("Timed out waiting. Check the AWS Console.")


if __name__ == "__main__":
    main()
