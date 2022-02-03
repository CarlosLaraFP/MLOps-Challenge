import uuid
import s3fs
import json
import numpy as np
import math
from sklearn.metrics import mean_squared_error

from utils import read_data, load_model_from_s3


def lambda_handler(event, context):
    
    # *********************************************
    # Read evaluation data from S3
    #*********************************************
    
    # Reading variables passed in by the parent Step Function
    run_id = json.loads(event['Input']['RunParameters'])['RunId']
    run_date = json.loads(event['Input']['RunParameters'])['RunDate']
    environment = json.loads(event['Input']['RunParameters'])['Environment']
    project = json.loads(event['Input']['RunParameters'])['Project']
    
    project_bucket = f"pr-{environment}-{project}-bucket"
    prefix = f"training-pipeline/data-preparation/{run_date}/{run_id}"
    
    test_features = read_data(project_bucket, f"{prefix}/test-features.csv")
    assert test_features.shape == (7, 1)
    assert test_features.dtype == "int64"

    test_labels = read_data(project_bucket, f"{prefix}/test-labels.csv").flatten()
    assert test_labels.shape == (7,)
    assert test_labels.dtype == "int64"

    assert test_features.shape[0] == test_labels.shape[0]

    # *********************************************
    # Load serialized model from S3 so it's accessible inside this Lambda container
    #*********************************************

    model = load_model_from_s3(project_bucket, "models/LinearRegression_Model.pkl")

    evaluation_predictions = model.predict(test_features)

    assert type(evaluation_predictions) == np.ndarray
    assert evaluation_predictions.shape == (7,)
    
    # *********************************************
    # Add a test for the accuracy of the model (JD)
    #*********************************************
    
    test_rmse = math.sqrt(mean_squared_error(test_labels.flatten(), evaluation_predictions))
    
    '''
        If there is an existing deployed model, we load its RMSE and compare it against this 
        "challenger" model's RMSE to decide whether this challenger model will replace the champion model.
        
        If there is no model in production yet (1st time deployment), obtain a maximum RMSE from product management.
        If we meet or exceed it, we deploy the model to production. Otherwise, improve model performance iteratively.
        
        In practice, we perform model evaluation on distinct slices of the test set, 
        weigh them by importance/business impact, and produce a weighted sum for the final model evaluation score.
        
        For now, testing the model "against itself" by obtaining a RMSE on the train set. 
        This train_rmse mocks the baseline RMSE.
    '''
    
    train_features = read_data(project_bucket, f"{prefix}/train-features.csv")
    train_labels = read_data(project_bucket, f"{prefix}/train-labels.csv")
    
    baseline_predictions = model.predict(train_features)
    train_rmse = math.sqrt(mean_squared_error(train_labels.flatten(), baseline_predictions))
    
    if test_rmse < train_rmse:
        '''
        Proceed to production deployment. Options:
        
        - Shadow deployment
        - Canary deployment
        - Blue/green deployment
        - A/B testing
        '''
        print("Production deployment implementation pending...")
    else:
        print("No new champion model found in this training pipeline run.")
    
    
    # *********************************************
    # TODO: Log microservice metadata
    #*********************************************
    