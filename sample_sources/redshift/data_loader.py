# Imports
import botocore.session as s
from botocore.exceptions import ClientError
import json
import boto3
import os
import base64
import sys
import time

# Sleep so IAM and things are calmer
time.sleep(60)


# Obtain Secrets for DB Connection Information
secret_name = 'redshift-l4mintegration'  ## replace the secret name with yours
session = boto3.session.Session()
region = session.region_name

client = session.client(
    service_name='secretsmanager',
    region_name=region
)

try:
    get_secret_value_response = client.get_secret_value(
        SecretId=secret_name
    )
    secret_arn = get_secret_value_response['ARN']

except ClientError as e:
    print("Error retrieving secret. Error: " + e.response['Error']['Message'])

else:
    # Depending on whether the secret is a string or binary, one of these fields will be populated.
    if 'SecretString' in get_secret_value_response:
        secret = get_secret_value_response['SecretString']
    else:
        secret = base64.b64decode(get_secret_value_response['SecretBinary'])

secret_json = json.loads(secret)
cluster_id = secret_json['dbClusterIdentifier']
db = secret_json['db']

# With the secrets, connect to Redshift
client_redshift = session.client("redshift-data")

# Get the s3 bucket info
bucket = os.getenv('s3bucket')
# Get the role for Redshift to access the data
iam = boto3.resource('iam')
role = iam.Role(sys.argv[1])
print(role.arn)

# Build a query string for the copy command
query_str = "copy ecommerce \
from 's3://" + bucket + "/ecommerce/output.csv' \
iam_role '" + str(role.arn) +"' \
csv; commit;"

print(query_str)

# Execute the query
client_redshift.execute_statement(Database= db, SecretArn= secret_arn, Sql= query_str, ClusterIdentifier= cluster_id)


