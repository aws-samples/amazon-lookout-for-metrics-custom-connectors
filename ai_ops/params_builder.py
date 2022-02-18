#!/usr/bin/python
import sys
import json
import boto3

# Open params and read as a dict
with open('params.json') as f:
    data = json.load(f)

# Dynamically set a few things
role_arn = sys.argv[1]

s3_path_backtest = "s3://" + sys.argv[2] + '/ecommerce/backtest/'
s3_path_continuous = "s3://" + sys.argv[2] + '/ecommerce/live/{{yyyyMMdd}}/{{HHmm}}'
s3_path_continuous_root = "s3://" + sys.argv[2] + '/ecommerce/live/'

sts = boto3.client("sts")
account_id = sts.get_caller_identity()["Account"]

data['metric_source']['S3SourceConfig']['RoleArn'] = "arn:aws:iam::" + account_id + ":role/" + role_arn

# Configure Historical Path
data['metric_source']['S3SourceConfig']['HistoricalDataPathList'] = [s3_path_backtest]

# Configure Future Path
data['metric_source']['S3SourceConfig']['TemplatedPathList'] = [s3_path_continuous]
data['s3_path_continuous_root'] = s3_path_continuous_root
# Configure Bucket
data['s3_bucket'] = sys.argv[2]


# Close the File
with open('params.json', 'w') as json_file:
    json.dump(data, json_file, indent=4, sort_keys=True)