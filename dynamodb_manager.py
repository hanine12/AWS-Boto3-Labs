import boto3
from botocore.exceptions import ClientError
from decimal import Decimal, InvalidOperation

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

#------------------------------------------------------------------------------------------------------------------------------------------------------------------

def add_student():
    item = {
        'student_id': input("Enter student ID: ").strip(),
        'name': input("Enter student name: ").strip(),
        'age': int(input("Enter student age: ").strip()),
        'program': input("Enter student program: ").strip(),}

    year = input("Enter student year: ").strip()
    if year.isdigit():
        item['year'] = int(year)

    try:
        table.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(student_id)'  # Ensure no duplicate student_id
        )
        print(f"Student {item['name']} added successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f"Student with ID {item['student_id']} already exists.")
        else:
            raise
        
#------------------------------------------------------------------------------------------------------------------------------------------------------------------
def get_student():
    student_id = input("Enter student ID: ").strip()
    response = table.get_item(
        Key={'student_id': student_id}
    )
    if 'Item'  not in response:
        print(f"No student found with ID {student_id}.")
        return

    for key, value in response['Item'].items():
        print(f"{key:<14}: {value}")
#------------------------------------------------------------------------------------------------------------------------------------------------------------------
def update_student():
    student_id = input("Enter student ID to update: ").strip()
    field = input("Enter the field to update (name, age, program, year): ").strip()
    value = input(f"Enter the new value for {field}: ").strip()

    if field in ['year', 'age']:
        try:
            value = Decimal(value)
        except (InvalidOperation):
            print("year/age must be a number.")
            return

    try:
        response = table.update_item(
            Key={'student_id': student_id},
            UpdateExpression=f"SET {field} = :val",
            ExpressionAttributeValues={':val': value},
            ConditionExpression='attribute_exists(student_id)',  
            ReturnValues="ALL_NEW"
        )
        print("Updated:", response['Attributes'])
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f"No student found with ID {student_id}.")
        else:
            raise

#------------------------------------------------------------------------------------------------------------------------------------------------------------------
def delete_student():
    student_id = input("Enter student ID to delete: ").strip()
    try:
        response=table.delete_item(
            Key={'student_id': student_id},
            ConditionExpression='attribute_exists(student_id)', 
            ReturnValues='ALL_OLD'
            
        )
        print(f"Deleted student: {response.get('Attributes',{}).get('name',student_id)}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f"No student found with ID {student_id}.")
        else:
            raise

#------------------------------------------------------------------------------------------------------------------------------------------------------------------

def main():
    while True:
        print("\nDynamoDB Manager")
        print("1. Create Table")
        print("2. Add Student")
        print("3. Get Student")
        print("4. Update Student")
        print("5. Delete Student")
        print("0. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            create_table()
        elif choice == '2':
            add_student()
        elif choice == '3':
            get_student()
        elif choice == '4':
            update_student()
        elif choice == '5':
            delete_student()
        elif choice == '0':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()