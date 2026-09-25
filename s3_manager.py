import sys
import os
import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
REGION = boto3.session.Session().region_name or "us-east-1"

MENU = """
=========================================
                S3 MANAGER
=========================================
1. Create Bucket          5. Download File
2. List Buckets           6. Delete File
3. Upload File             7. Generate Presigned URL
4. List Files              8. Delete Bucket
9. Backup Local Folder     0. Exit
=========================================
"""

def create_bucket():
    name = input("New bucket name: ").strip()
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

def list_buckets():
    response = s3.list_buckets()
    buckets = response.get("Buckets", [])
    if not buckets:
        print("(no buckets)")
        return
    for b in buckets:
        print(f"{b['Name']:<40} created {b['CreationDate']:%Y-%m-%d}")

def upload_file():
    path = input("Local file path: ").strip()
    bucket = input("Target bucket: ").strip()

    if not os.path.isfile(path):
        print(f"File not found: {path}")
        return

    default_key = os.path.basename(path)
    key = input(f"Object key [{default_key}]: ").strip() or default_key

    s3.upload_file(path, bucket, key)
    print(f"Uploaded {path} -> s3://{bucket}/{key}")

def list_objects():
    bucket = input("Bucket name: ").strip()
    prefix = input("Prefix filter (Enter for all): ").strip()

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    total_objects = 0
    total_bytes = 0

    for page in pages:
        for obj in page.get("Contents", []):
            total_objects += 1
            total_bytes += obj["Size"]
            print(f"{obj['Key']:<50} {obj['Size']:>12,} "
                  f"{obj['LastModified']:%Y-%m-%d %H:%M}")

    if total_objects == 0:
        print("(bucket is empty)")
    else:
        print(f"\n{total_objects} object(s), "
              f"{total_bytes / 1024 / 1024:.2f} MB")


        
def download_file():
    print("download_file() called")

def delete_file():
    print("delete_file() called")

def generate_presigned_url():
    print("generate_presigned_url() called")

def delete_bucket():
    print("delete_bucket() called")

def backup_folder():
    print("backup_folder() called")

ACTIONS = {
    "1": create_bucket,
    "2": list_buckets,
    "3": upload_file,
    "4": list_objects,
    "5": download_file,
    "6": delete_file,
    "7": generate_presigned_url,
    "8": delete_bucket,
    "9": backup_folder,
}

def main():
    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()
        if choice == "0":
            sys.exit(0)
        action = ACTIONS.get(choice)
        if action:
            action()
        else:
            print("Invalid option.")

if __name__ == "__main__":
    main()