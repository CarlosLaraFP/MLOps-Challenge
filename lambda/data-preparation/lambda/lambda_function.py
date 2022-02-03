import uuid
import json
from io import StringIO
import s3fs
import boto3
import pandas as pd
import numpy as np


def lambda_handler(event, context):
    
    # *********************************************
    # Extract, Validate, and Load training data to S3
    # Helpful for: Data Lineage, Data Provenance, Debugging, Audits
    #*********************************************
    
    # Reading variables passed in by the parent Step Function
    run_id = json.loads(event['Input']['RunParameters'])['RunId']
    run_date = json.loads(event['Input']['RunParameters'])['RunDate']
    environment = json.loads(event['Input']['RunParameters'])['Environment']
    project = json.loads(event['Input']['RunParameters'])['Project']
    
    project_bucket = f"pr-{environment}-{project}-bucket"
    prefix = f"training-pipeline/data-preparation/{run_date}/{run_id}"

    train_features = np.array([6, 16, 26, 36, 46, 56, 64]).reshape((-1, 1))
    assert train_features.shape == (7, 1)
    assert train_features.dtype == "int64"

    train_labels = np.array([4, 18, 20, 22, 24, 35, 45])
    assert train_labels.shape == (7,)
    assert train_labels.dtype == "int64"

    assert train_features.shape[0] == train_labels.shape[0]

    # We need test_features and test_labels for evaluation (canonical test set)
    test_features = np.array([1, 12, 24, 36, 48, 60, 72]).reshape((-1,1))
    assert test_features.shape == (7, 1)
    assert test_features.dtype == "int64"

    test_labels = np.array([3, 9, 20, 29, 42, 53, 60])
    assert test_labels.shape == (7,)
    assert test_labels.dtype == "int64"

    assert test_features.shape[0] == test_labels.shape[0]

    # The 1 data point represents inference after the model is already deployed, at which time we do not have labels
    # Save for the end depending on time
    inference_data = np.array([1]).reshape((-1,1))
    assert inference_data.shape == (1, 1)
    assert inference_data.dtype == "int64"
    
    s3_resource = boto3.resource('s3')

    # Write 3 separate CSV files to S3 for Training microservice consumption
    data = {
        "train-features.csv": train_features, 
        "train-labels.csv": train_labels, 
        "test-features.csv": test_features, 
        "test-labels.csv": test_labels, 
        "inference-data.csv": inference_data
    }

    for file_name, dataset in data.items():
        csv_buffer = StringIO()
        pd.DataFrame(dataset).to_csv(csv_buffer, index=None)
        s3_resource.Object(project_bucket, f"{prefix}/{file_name}").put(Body=csv_buffer.getvalue())
        
    # *********************************************
    # TODO: Log microservice metadata
    #*********************************************
    
