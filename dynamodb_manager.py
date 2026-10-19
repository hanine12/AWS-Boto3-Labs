import boto3
from botocore.exceptions import ClientError
from decimal import Decimal, InvalidOperation
from boto3.dynamodb.conditions import Key, Attr

table_name = 'hanine_hosni_students'
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table(table_name)


def create_table():
    try:
        new_table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'student_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'student_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print(f"Creating table {table_name}...")
        new_table.wait_until_exists()
        print(f"Table {table_name} created successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table {table_name} already exists.")
        else:
            raise


def add_student():
    item = {
        'student_id': input("Enter student ID: ").strip(),
        'name': input("Enter student name: ").strip(),
        'program': input("Enter student program: ").strip(),
    }
    age = input("Enter student age: ").strip()
    if age.isdigit():
        item['age'] = Decimal(age)
    year = input("Enter student year: ").strip()
    if year.isdigit():
        item['year'] = Decimal(year)

    try:
        table.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(student_id)'
        )
        print(f"Student {item['name']} added successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f"Student with ID {item['student_id']} already exists.")
        else:
            raise


def get_student():
    student_id = input("Enter student ID: ").strip()
    response = table.get_item(Key={'student_id': student_id})
    if 'Item' not in response:
        print(f"No student found with ID {student_id}.")
        return
    for key, value in response['Item'].items():
        print(f"{key:<14}: {value}")


def update_student():
    student_id = input("Enter student ID to update: ").strip()
    field = input("Enter the field to update (name, age, program, year): ").strip()
    value = input(f"Enter the new value for {field}: ").strip()

    if field in ('year', 'age'):
        try:
            value = Decimal(value)
        except InvalidOperation:
            print("year/age must be a number.")
            return

    try:
        response = table.update_item(
            Key={'student_id': student_id},
            UpdateExpression="SET #f = :val",              # ← alias
            ExpressionAttributeNames={'#f': field},        # ← alias map
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


def delete_student():
    student_id = input("Enter student ID to delete: ").strip()
    try:
        response = table.delete_item(
            Key={'student_id': student_id},
            ConditionExpression='attribute_exists(student_id)',
            ReturnValues='ALL_OLD'
        )
        print(f"Deleted student: {response.get('Attributes', {}).get('name', student_id)}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f"No student found with ID {student_id}.")
        else:
            raise


def list_students():
    items = []
    scan_kwargs = {}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        if 'LastEvaluatedKey' not in response:
            break
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    if not items:
        print("No students found.")
        return

    for item in sorted(items, key=lambda x: x['student_id']):
        print(f"ID: {item['student_id']:<6}, "
              f"Name: {item.get('name', 'N/A'):<9}, "
              f"Age: {item.get('age', 'N/A')}, "
              f"Program: {item.get('program', 'N/A')}, "
              f"Year: {item.get('year', 'N/A')}")
    print(f"Total students: {len(items)}")


def search_students_scan():
    search_field = input("Enter the field (name / id / age / program / year): ").strip()

    if search_field == 'id':
        search_field = 'student_id'

    if search_field not in ('name', 'student_id', 'age', 'program', 'year'):
        print("Invalid search field.")
        return

    search_value = input(f"Enter the value for {search_field}: ").strip()

    if search_field in ('year', 'age'):
        try:
            search_value = Decimal(search_value)
        except InvalidOperation:
            print("year/age must be a number.")
            return

    response = table.scan(FilterExpression=Attr(search_field).eq(search_value))
    items = response.get('Items', [])

    for item in sorted(items, key=lambda x: x['student_id']):
        print(f"ID: {item['student_id']:<6}, "
              f"Name: {item.get('name', 'N/A'):<9}, "
              f"Age: {item.get('age', 'N/A')}, "
              f"Program: {item.get('program', 'N/A')}, "
              f"Year: {item.get('year', 'N/A')}")

    if not items:
        print(f"No students found with {search_field} = {search_value}.")
    else:
        print(f"Total students found: {len(items)}")
        print("Note: Scan read the WHOLE table. The filter only reduced what we received.")


def search_students_query():
    # Query works ONLY on the partition key: student_id
    student_id = input("Enter student ID to query: ").strip()

    response = table.query(
        KeyConditionExpression=Key('student_id').eq(student_id)
    )
    items = response.get('Items', [])

    for item in items:
        print(f"ID: {item['student_id']:<6}, "
              f"Name: {item.get('name', 'N/A'):<9}, "
              f"Age: {item.get('age', 'N/A')}, "
              f"Program: {item.get('program', 'N/A')}, "
              f"Year: {item.get('year', 'N/A')}")

    if not items:
        print(f"No student found with ID {student_id}.")
    else:
        print(f"Query returned {len(items)} item(s).")


def delete_table():
    confirm = input(f"Type DELETE to delete '{table_name}': ").strip()
    if confirm != "DELETE":
        print("Aborted.")
        return
    try:
        table.delete()
        print(f"Deleting table {table_name}...")
        table.wait_until_not_exists()
        print(f"Table {table_name} deleted successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Table {table_name} does not exist.")
        else:
            raise


def list_tables():
    try:
        response = dynamodb.list_tables()
        names = response.get('TableNames', [])
        if not names:
            print("No tables found.")
        else:
            print("Tables:")
            for n in names:
                print(f"- {n}")
    except ClientError as e:
        print(f"Error listing tables: {e}")


def main():
    while True:
        print("\nDynamoDB Manager")
        print("1. Create Table")
        print("2. Add Student")
        print("3. Get Student")
        print("4. Update Student")
        print("5. Delete Student")
        print("6. List Students")
        print("7. Search Students (Query — by ID only)")
        print("8. Search Students (Scan + Filter)")
        print("9. Delete Table")
        print("10. List Tables")
        print("0. Exit")
        choice = input("Enter your choice: ").strip()

        if choice == '1':   create_table()
        elif choice == '2': add_student()
        elif choice == '3': get_student()
        elif choice == '4': update_student()
        elif choice == '5': delete_student()
        elif choice == '6': list_students()
        elif choice == '7': search_students_query()
        elif choice == '8': search_students_scan()
        elif choice == '9': delete_table()
        elif choice == '10': list_tables()
        elif choice == '0':
            print("Exiting...")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()