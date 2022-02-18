#!/bin/bash

# BEGIN CUSTOM CONNECTOR WORK
# Next deploy the SAM template that creates a state machine for generating historical data, configuring an hourly data cron, and setting up Lookout for Metrics.
pip install aws-sam-cli
sam --version
sam deploy --template-file template.yaml --stack-name custom-rs-connector --capabilities CAPABILITY_IAM --s3-bucket $1 --parameter-overrides "RedshiftCluster=$2 RedshiftSecret=$3 SageMakerNotebookRole=$4"
bucket=$(aws cloudformation describe-stacks --stack-name custom-rs-connector --query "Stacks[0].Outputs[?OutputKey=='InputBucketName'].OutputValue" --output text)
l4mrole=$(aws cloudformation describe-stacks --stack-name custom-rs-connector --query "Stacks[0].Outputs[?OutputKey=='LookoutForMetricsRole'].OutputValue" --output text)
l4mroleArn=$(aws cloudformation describe-stacks --stack-name custom-rs-connector --query "Stacks[0].Outputs[?OutputKey=='LookoutForMetricsRoleArn'].OutputValue" --output text)
policy_for_sagemaker=$(aws cloudformation describe-stacks --stack-name custom-rs-connector --query "Stacks[0].Outputs[?OutputKey=='SageMakerNotebookS3BucketWritePolicy'].OutputValue" --output text)
policy_for_sagemaker_arn=$(aws iam list-policies --query 'Policies[?PolicyName=="$policy_for_sagemaker"].Arn' --output text)

# Build params.json
python ./params_builder.py $l4mrole $bucket

# Add Lambda IAM Role to Redshift Cluster
sleep 30
aws redshift modify-cluster-iam-roles --cluster-identifier $2 --add-iam-roles $l4mroleArn
sleep 30
# Ship params.json to bucket
aws s3 cp params.json s3://$bucket/ --quiet

# Kick off and deploy Scheduled Lambda for Continuous Crawling
sam deploy --template-file l4m-redshift-continuous-crawl.yaml --stack-name custom-rs-connector-crawl --capabilities CAPABILITY_IAM --s3-bucket $1 --parameter-overrides "InputBucketName=$bucket RedshiftCluster=$2 RedshiftSecret=$3"
