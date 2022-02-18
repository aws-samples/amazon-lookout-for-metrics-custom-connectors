"""
Purpose

This Lambda function will be called via a state machine when setting up a custom Redshift connector.
It starts by grabbing all of the historical data from Redshift that is relevant to L4M, then placing it in an s3 bucket.

After that, the state machine will progress to the next steps.
"""

import logging
import boto3
import botocore.session as s
from botocore.exceptions import ClientError
from datetime import datetime
import json
import time
import os
import base64

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_and_parse_params():
    """
    uses the environment variable of an s3 bucket to fetch a file loaded with everything else needed from the step
    functions configuration.
    :return: params as JSON object
    """
    s3 = boto3.client('s3')
    s3.download_file(os.getenv('InputBucketName'), 'params.json', '/tmp/params.json')
    with open("/tmp/params.json") as file:
        return json.load(file)


def lambda_handler(event, context):
    """
    Accepts the params passed to it via the statemachine call param event.

    :param event: The event dict that contains the parameters sent when the function
                  is invoked. This has all the information needed to engage with Redshift
    :param context: The context in which the function is called.
    :return: The result of the specified action.
    """
    # Configure logging
    logger.info('Event: %s', event)
    # Load the Params File from S3 For latest configuration
    params = get_and_parse_params()
    # Load the secret name and connect to the service
    secret_name = params['secret_name']
    session = boto3.session.Session()
    region = session.region_name

    client = session.client(
        service_name='secretsmanager',
        region_name=region
    )

    # Validate the secret name
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
        secret_arn = get_secret_value_response['ARN']

    except ClientError as e:
        print("Error retrieving secret. Error: " + e.response['Error']['Message'])
    # Perform this if there are no exceptions with the earlier block of code
    else:
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            secret = base64.b64decode(get_secret_value_response['SecretBinary'])
    # Create a dictionary object of the secrets values for use later
    secrets = json.loads(secret)
    cluster_id = secrets['dbClusterIdentifier']
    db = secrets['db']

    # Build Redshift Connection:
    session = boto3.session.Session()
    bc_session = s.get_session()
    region = session.region_name
    session = boto3.Session(
        botocore_session=bc_session,
        region_name=region,
    )
    client_redshift = session.client("redshift-data")
    isSynchronous = True

    # Read file for connection query:
    with open("query.sql", "r") as sql_file:
        query_input = sql_file.read().strip('\n')
        iam_role = params['metric_source']['S3SourceConfig']['RoleArn']
        bucket_str = params['s3_path_continuous_root']
        #Now for a continuous detector we need a timestamp pathing format, we recommend: {{yyyyMMdd}}/{{HHmm}} so add that to the string
        date_str = datetime.today().strftime('%Y%m%d/%H00/')
        bucket_str += date_str
        print(bucket_str)
        # build the query that will perform the content from the file, and stream it to S3.
        query = "unload ('" + query_input + "') to '" + bucket_str + "' iam_role '" + iam_role + "' header CSV;"
        # execute the query
        client_redshift.execute_statement(Database=db, SecretArn=secret_arn, Sql=query,
                                          ClusterIdentifier=cluster_id)
        MAX_WAIT_CYCLES = 15
        attempts = 0
        # Calling Redshift Data API with executeStatement()
        res = client_redshift.execute_statement(Database=db, SecretArn=secret_arn, Sql=query,
                                          ClusterIdentifier=cluster_id)
        query_id = res["Id"]
        desc = client_redshift.describe_statement(Id=query_id)
        query_status = desc["Status"]
        logger.info(
            "Query status: {} .... for query-->{}".format(query_status, query))
        done = False

        # Wait until query is finished or max cycles limit has been reached.
        while not done and isSynchronous and attempts < MAX_WAIT_CYCLES:
            attempts += 1
            time.sleep(60)
            desc = client_redshift.describe_statement(Id=query_id)
            query_status = desc["Status"]

            if query_status == "FAILED":
                raise Exception('SQL query failed:' +
                                query_id + ": " + desc["Error"])

            elif query_status == "FINISHED":
                logger.info("query status is: {} for query id: {}".format(
                    query_status, query_id))
                done = True
                # print result if there is a result (typically from Select statement)
                if desc['HasResultSet']:
                    response = client_redshift.get_statement_result(
                        Id=query_id)
                    logger.info(
                        "Printing response of query --> {}".format(response['Records']))
            else:
                logger.info(
                    "Current working... query status is: {} ".format(query_status))

        # Timeout Precaution
        if done == False and attempts >= MAX_WAIT_CYCLES and isSynchronous:
            logger.info(
                "Limit for MAX_WAIT_CYCLES has been reached before the query was able to finish. We have exited out of the while-loop. You may increase the limit accordingly. \n")
            raise Exception("query status is: {} for query id: {}".format(
                query_status, query_id))


        response = {'result': ("Current working... query status is: {} ".format(query_status))}
        return response