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


def load_model_from_s3(bucket: str, key: str):
    '''
        Downloads a serialized machine learning model from S3, deserializes it, and returns it.
        
        args:
            bucket: S3 bucket name
            key: S3 path where the serialized model will be loaded from
        returns:
            Scikit-learn model
    '''
    with tempfile.TemporaryFile() as fp:
        boto3.client("s3").download_fileobj(Fileobj=fp, Bucket=bucket, Key=key)
        fp.seek(0)
        model = load(fp)
        return model
        
