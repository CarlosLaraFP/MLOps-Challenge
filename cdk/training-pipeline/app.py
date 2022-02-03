#!/usr/bin/env python3
import os
import sys

import aws_cdk as cdk

from training_pipeline.ci_cd_stack import CICDStack
from training_pipeline.lightweight_training_stack import LightweightTrainingStack

# *** IMMUTABLE INFRASTRUCTURE - only approved IAM Users can commit changes through the centralized DevOps accounts ***

def read_buildspec(path: str) -> str:
    '''
        Open local buildspec.yml file, read it into a string object & return for input into CDK CICDStack's props.
        This abstracts CodeBuild configuration away from data scientists.
    '''
    file = open(path)
    buildspec_yml = file.read()
    file.close()
    return buildspec_yml
    

app = cdk.App()

CICDStack(app, "RegressionCICDStack", 
    buildspec_yml_build=read_buildspec("lambda-build/build.yml"), 
    buildspec_yml_factory=read_buildspec("lambda-build/factory.yml"),
    buildspec_yml_deploy=read_buildspec("lambda-build/deploy.yml"),
    buildspec_yml_prod_factory=read_buildspec("lambda-build/prod-factory.yml"),
    env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION"))
)
LightweightTrainingStack(app, "RegressionTrainingPipelineStack", env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")))

app.synth()
