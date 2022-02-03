import uuid
import s3fs
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from utils import read_data, save_model_to_s3


def lambda_handler(event, context):
    
    # *********************************************
    # Read training data from S3
    #*********************************************
    
    # Reading variables passed in by the parent Step Function
    run_id = json.loads(event['Input']['RunParameters'])['RunId']
    run_date = json.loads(event['Input']['RunParameters'])['RunDate']
    environment = json.loads(event['Input']['RunParameters'])['Environment']
    project = json.loads(event['Input']['RunParameters'])['Project']
    
    project_bucket = f"pr-{environment}-{project}-bucket"
    prefix = f"training-pipeline/data-preparation/{run_date}/{run_id}"
    
    train_features = read_data(project_bucket, f"{prefix}/train-features.csv")
    
    assert train_features.shape == (7, 1)
    assert train_features.dtype == "int64"

    train_labels = read_data(project_bucket, f"{prefix}/train-labels.csv").flatten()
    
    assert train_labels.shape == (7,)
    assert train_labels.dtype == "int64"
    
    # *********************************************
    # Train model, seralize it, and write it to S3
    #*********************************************
    
    model = LinearRegression().fit(train_features, train_labels) 
    
    save_model_to_s3(model, project_bucket, "models/LinearRegression_Model.pkl")
    
    # *********************************************
    # TODO: Log microservice metadata
    # MODEL METADATA GOES INTO SAGEMAKER MODEL REGISTRY
    #*********************************************
    
    
