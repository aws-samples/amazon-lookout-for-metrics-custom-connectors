# Imports
import botocore.session as s
from botocore.exceptions import ClientError
import json
import boto3
import time
import base64
import pandas as pd

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
bc_session = s.get_session()
session = boto3.Session(
    botocore_session=bc_session,
    region_name=region,
)
client_redshift = session.client("redshift-data")

# The query string below creates 3 database tables for storing demo data
query_str = 'create table platform(\
id	bigint identity(0, 1),\
name varchar(30),\
primary key(id));\
create table marketplace(\
id	bigint identity(0, 1),\
name varchar(30),\
primary key(id));\
create table ecommerce(\
id bigint identity(0, 1),\
ts timestamp not null,\
platform int not null references platform (id),\
marketplace int not null references marketplace (id),\
views int,\
revenue decimal(9,2),\
primary key(id));\
'
client_redshift.execute_statement(Database= db, SecretArn= secret_arn, Sql= query_str, ClusterIdentifier= cluster_id)

# Read the sample data
data_df = pd.read_csv('/home/ec2-user/SageMaker/amazon-lookout-for-metrics-custom-connectors/data/ecommerce/backtest/input.csv')

# Parse platforms into DB from the dataframe
for platform in data_df.platform.unique():
    print(platform)
    query_str = "Begin;insert into platform ( name ) VALUES('" + platform + "');Commit;"
    client_redshift.execute_statement(Database= db, SecretArn= secret_arn, Sql= query_str, ClusterIdentifier= cluster_id)
# Parse marketplaces into DB from the dataframe
for marketplace in data_df.marketplace.unique():
    print(marketplace)
    query_str = "Begin;insert into marketplace ( name ) VALUES('" + marketplace + "');Commit;"
    client_redshift.execute_statement(Database= db, SecretArn= secret_arn, Sql= query_str, ClusterIdentifier= cluster_id)

# Next fetch the individual values from their tables so you have their ID and string value for both platforms and marketplaces
client_redshift = session.client("redshift-data")
query_str = "select * from platform;"
response = client_redshift.execute_statement(Database= db, SecretArn= secret_arn, Sql= query_str, ClusterIdentifier= cluster_id)
time.sleep(10)
platforms = client_redshift.get_statement_result(Id=response['Id'])['Records']
for item in platforms:
    data_df.loc[data_df.platform == item[1]['stringValue'], "platform"] = item[0]['longValue']
query_str = "select * from marketplace;"
response = client_redshift.execute_statement(Database= db, SecretArn= secret_arn, Sql= query_str, ClusterIdentifier= cluster_id)
time.sleep(10)
marketplaces = client_redshift.get_statement_result(Id=response['Id'])['Records']

# Convert the dataframe into one using the DB's primary key values
for item in marketplaces:
    data_df.loc[data_df.marketplace == item[1]['stringValue'], "marketplace"] = item[0]['longValue']

# Reorder the columns to map to those of the database
data_df = data_df[['timestamp', 'platform', 'marketplace', 'views', 'revenue']]

# Export this file to disk so it can be used later to fill in the sample DB in Redshift.
data_df.to_csv("output.csv", header=False, index=False)


