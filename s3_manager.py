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
    bucket = input("Bucket name: ").strip()
    key = input("Object key: ").strip()
    dest = input("Save as: ").strip() or os.path.basename(key)

    try:
        s3.download_file(bucket, key, dest)
        print(f"Downloaded -> {dest}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            print("That object does not exist.")
        else:
            raise

def delete_file():
    bucket = input("Bucket name: ").strip()
    key = input("Object key (or 'all' to delete everything in the bucket): ").strip()

    if key.lower() == "all":
        confirm = input(f"Type '{bucket}' again to confirm deleting ALL objects: ").strip()
        if confirm != bucket:
            print("Names didn't match — cancelled.")
            return

        paginator = s3.get_paginator("list_objects_v2")
        deleted = 0
        for page in paginator.paginate(Bucket=bucket):
            objects = page.get("Contents", [])
            if not objects:
                continue
            keys = [{"Key": obj["Key"]} for obj in objects]
            s3.delete_objects(Bucket=bucket, Delete={"Objects": keys})
            deleted += len(keys)

        print(f"Deleted {deleted} object(s) from '{bucket}'.")
        return

    s3.delete_object(Bucket=bucket, Key=key)
    print(f"Deleted s3://{bucket}/{key}")

def generate_presigned_url():
    bucket = input("Bucket name: ").strip()
    key = input("Object key: ").strip()
    raw = input("Valid for how many seconds? [3600]: ").strip()
    expires = int(raw) if raw.isdigit() else 3600

    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
    print(f"\nValid for {expires} seconds:\n{url}\n")

def delete_bucket():
    name = input("Bucket to delete: ").strip()
    confirm = input(f"Type the bucket name again to confirm deletion: ").strip()

    if confirm != name:
        print("Names didn't match — deletion cancelled.")
        return

    try:
        s3.delete_bucket(Bucket=name)
        print(f"Deleted bucket '{name}'")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "BucketNotEmpty":
            print("Bucket is not empty. Delete all objects first (option 6, or list with option 4 and remove each).")
        else:
            print(f"[AWS ERROR] {code}")

def backup_folder():
    folder = input("Local folder to back up: ").strip()
    bucket = input("Target bucket: ").strip()
    prefix = input("Key prefix (e.g. backup/): ").strip()

    if not os.path.isdir(folder):
        print(f"Folder not found: {folder}")
        return

    successes = 0
    failures = 0

    for root, dirs, files in os.walk(folder):
        for filename in files:
            local_path = os.path.join(root, filename)
            relative = os.path.relpath(local_path, folder)
            key = prefix + relative.replace(os.sep, "/")

            try:
                s3.upload_file(local_path, bucket, key)
                successes += 1
            except (ClientError, OSError) as e:
                print(f"Failed: {local_path} ({e})")
                failures += 1

    print(f"\nBackup complete: {successes} succeeded, {failures} failed.")

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