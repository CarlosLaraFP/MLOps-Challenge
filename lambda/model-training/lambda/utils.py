import boto3
import pandas as pd
import numpy as np
import json
from io import StringIO
import tempfile
from joblib import dump, load


def read_data(bucket: str, key: str) -> np.array:
    '''
    '''
    s3_csv = boto3.client("s3").get_object(Bucket=bucket, Key=key)
    csv_string = s3_csv["Body"].read().decode("utf-8")
    dataset = pd.read_csv(StringIO(csv_string)).to_numpy()
    return dataset
    

def save_model_to_s3(model, bucket: str, key: str) -> None:
    '''
    '''
    with tempfile.TemporaryFile() as fp:
        dump(model, fp)
        fp.seek(0)
        boto3.resource("s3").Object(bucket, key).put(Body=fp.read())
    
    