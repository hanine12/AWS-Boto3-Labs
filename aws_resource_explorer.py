import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def show_identity():
    sts = boto3.client("sts")
    identity = sts.get_caller_identity()
    print(f"Account ID : {identity['Account']}")
    print(f"User ID    : {identity['UserId']}")
    print(f"ARN        : {identity['Arn']}")


def show_region():
    session = boto3.session.Session()
    print(f"Region  : {session.region_name}")
    print(f"Profile : {session.profile_name}")


def list_buckets_with_client():
    s3 = boto3.client("s3")
    response = s3.list_buckets()

    for bucket in response["Buckets"]:
        created = bucket["CreationDate"].strftime("%Y-%m-%d %H:%M")
        print(f"{bucket['Name']:<45} created {created}")

    print(f"Total: {len(response['Buckets'])} bucket(s)")

def list_buckets_with_resource():
    s3= boto3.resource("s3")
    for bucket in s3.buckets.all():
        print(f"{bucket.name}")


#The resource version is shorter because Boto3 hides the response shape 
# you iterate objects with attributes instead of digging through nested dictionaries.

def list_instances():
    ec2 = boto3.client("ec2")
    response = ec2.describe_instances()

    found_any = False
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            found_any = True
            tags= {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
            print(f"{instance['InstanceId']}  {instance['InstanceType']:<12}  "
                f"{instance['State']['Name']:<12}  "
                f"{tags.get('Name', '(no name)')}" )

    if not found_any:
        print("No instances found.")

def list_regions():
    ec2 = boto3.client("ec2")
    names= sorted([r["RegionName"] for r in ec2.describe_regions()["Regions"]]) 
    for i in range(0, len(names), 4):
        print("  "+"".join(f"{n:<20}" for n in names[i:i+4]))

def main():
    try:
        print("AWS RESOURCE EXPLORER")
        print("Lab 1 - Boto3 Fundamentals")
        print()

        print("=" * 60)
        print("WHO AM I?")
        print("=" * 60)
        show_identity()
        print()

        print("=" * 60)
        print("CURRENT REGION")
        print("=" * 60)
        show_region()
        print()

        print("=" * 60)
        print("S3 BUCKETS (via client)")
        print("=" * 60)
        list_buckets_with_client()
        print()

        print("=" * 60)
        print("S3 BUCKETS (via resource)")
        print("=" * 60)
        list_buckets_with_resource()
        print()

        print("=" * 60)
        print("EC2 INSTANCES")
        print("=" * 60)
        list_instances()
        print()

        print("=" * 60)
        print("AVAILABLE AWS REGIONS")
        print("=" * 60)
        list_regions()
    except NoCredentialsError:
        print("[ERROR] No AWS credentials found. Please configure your AWS credentials.")
    except ClientError as e:
        code = e.response['Error']['Code']
        message = e.response['Error']['Message']
        print(f"[AWS ERROR] {code}: {message}")
        if code in {"ExpiredToken", "ExpiredTokenException"}:
            print("Your AWS session token has expired. Please restart the lab .")


if __name__ == "__main__":
    main()