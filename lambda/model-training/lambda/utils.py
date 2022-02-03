import boto3
import pandas as pd
import numpy as np
import json
from io import StringIO
import tempfile
from joblib import dump, load


def read_data(bucket: str, key: str) -> np.array:
    '''
        Reads small CSV files from S3.
        
        args:
            bucket: S3 bucket name
            key: S3 path to the CSV file
        returns:
            np.array containing the data
    '''
    s3_csv = boto3.client("s3").get_object(Bucket=bucket, Key=key)
    csv_string = s3_csv["Body"].read().decode("utf-8")
    dataset = pd.read_csv(StringIO(csv_string)).to_numpy()
    return dataset
    

def save_model_to_s3(model, bucket: str, key: str) -> None:
    '''
        Serializes a machine learning model and writes it to S3.
        
        args:
            model: Scikit-learn model
            bucket: S3 bucket name
            key: S3 path where the serialized model will be written
        returns:
            None
    '''
    with tempfile.TemporaryFile() as fp:
        dump(model, fp)
        fp.seek(0)
        boto3.resource("s3").Object(bucket, key).put(Body=fp.read())
    
    
