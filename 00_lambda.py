import io
import json
import zipfile
import boto3

"""Lambda: zip the handler, deploy it, invoke it, delete it.

Needs lambda_function.py in the same folder.
"""


sts = boto3.client("sts")
lambda_client = boto3.client("lambda")

account = sts.get_caller_identity()["Account"]
role_arn = f"arn:aws:iam::{account}:role/LabRole"   # you cannot create IAM roles
name = "my-first-lambda"

# Zip the handler in memory. arcname keeps it at the root of the zip.
buffer = io.BytesIO()
with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
    z.write("lambda_function.py", arcname="lambda_function.py")

lambda_client.create_function(
    FunctionName=name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler",
    Code={"ZipFile": buffer.getvalue()},
    Timeout=10,
)
print("Created", name)

# Waiter the function is Pending for a few seconds after creation.
lambda_client.get_waiter("function_active_v2").wait(FunctionName=name)

response = lambda_client.invoke(
    FunctionName=name,
    Payload=json.dumps({"name": "Learner Lab"}).encode(),
)
print(json.loads(response["Payload"].read()))

lambda_client.delete_function(FunctionName=name)
print("Deleted", name)