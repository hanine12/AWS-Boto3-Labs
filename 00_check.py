import boto3

sts=boto3.client("sts")

print(sts.get_caller_identity())
print("Region", boto3.session.Session().region_name)