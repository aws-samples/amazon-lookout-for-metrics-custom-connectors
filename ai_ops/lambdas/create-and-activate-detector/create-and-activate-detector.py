import boto3


def lambda_handler(event, context):
    # Logging
    print(event)
    # Connect to L4M:
    l4m = boto3.client("lookoutmetrics")

    # Create Detector
    response = l4m.create_anomaly_detector(
        AnomalyDetectorName=event['detector_name'] + "-" + event['database_type'],
        AnomalyDetectorDescription=event['detector_description'],
        AnomalyDetectorConfig={
            "AnomalyDetectorFrequency": event['detector_frequency'],
        },
    )

    anomaly_detector_arn = response["AnomalyDetectorArn"]

    params = {
        "AnomalyDetectorArn": anomaly_detector_arn,
        "MetricSetName":  event['detector_name'] + "-" + event['database_type'] + '-metric-set-1',
        "MetricList": event['metrics_set'],

        "DimensionList": event['dimension_list'],

        "TimestampColumn": event['timestamp_column'],

        "Offset": event['offset'], # seconds the detector will wait before attempting to read latest data per current time and detection frequency below
        "MetricSetFrequency": event['detector_frequency'],

        "MetricSource": event['metric_source']
    }

    anomaly_detector_metric_set_arn = l4m.create_metric_set(**params)

    # Activate the Detector
    l4m.activate_anomaly_detector(AnomalyDetectorArn=anomaly_detector_arn)

    # actions.take_action(status['status'])
    return_dict = {}
    return_dict['anomaly_detector_arn'] = anomaly_detector_arn
    return_dict['anomaly_detector_metric_set_arn'] = anomaly_detector_metric_set_arn
    return return_dict