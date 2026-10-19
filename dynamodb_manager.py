import boto3
from botocore.exceptions import ClientError

table_name = 'hanine_hosni_students'
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table(table_name)

def create_table():
    try:
        new_table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'student_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'student_id',
                    'AttributeType': 'S'  # String
                }
            ],
            BillingMode='PAY_PER_REQUEST'  # On-demand mode
        )
        print(f"Creating table {table_name}...")
        new_table.wait_until_exists()
        print(f"Table {table_name} created successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table {table_name} already exists.")
        else:
            raise

def main():
    while True:
        print("\nDynamoDB Manager")
        print("1. Create Table")
        print("0. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            create_table()
        elif choice == '0':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()