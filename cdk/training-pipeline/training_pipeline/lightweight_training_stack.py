from aws_cdk import (
    # Duration,
    Stack, Aws, CfnTag, Fn,
    aws_s3 as s3,
    aws_glue as glue,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_stepfunctions as sf,
    aws_lambda as lambda_,
    aws_logs as logs
)
from constructs import Construct
import os
import boto3


class LightweightTrainingStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        repo = self.node.try_get_context("repo")
        project = self.node.try_get_context("project")
        account_id = self.node.try_get_context("account_id")
        region = self.node.try_get_context("region")
        
        if account_id == "test_account_id":
            environment = "test"
        elif account_id == "prod_account_id":
            environment = "prod"
        else:
            print("Unknown AWS account")
        
        
        # ********************************************************************************
        # Lambda IAM Role & Policy
        # ********************************************************************************
        
        lambda_policy = iam.CfnManagedPolicy(self, "LambdaPolicy", 
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "logs:*",
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:*"
                        ],
                        "Resource": [
                            f"arn:aws:s3:::pr-{environment}-{project}-bucket",
                            f"arn:aws:s3:::pr-{environment}-{project}-bucket/*"
                        ]
                    }
                ]
            }, 
            description=f"IAM managed policy for {project} training pipeline Lambda Functions",
            managed_policy_name=f"pr-{environment}-{project}-lambda-policy"
        )
        
        lambda_iam_role = iam.CfnRole(self, "LambdaRole", 
            assume_role_policy_document={
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Effect": "Allow",
                  "Principal": {
                    "Service": [
                        "lambda.amazonaws.com"
                    ]
                  },
                  "Action": "sts:AssumeRole"
                }
              ]
            }, 
            description=f"IAM role for {project} training pipeline Lambda Functions", 
            managed_policy_arns=[
                lambda_policy.ref
            ],
            role_name=f"pr-{environment}-{project}-lambda-role", 
            tags=[
                CfnTag(
                    key="Environment",
                    value=environment
                ),
                CfnTag(
                    key="Project",
                    value=project
                )
            ]
        )
        
        lambda_iam_role.add_depends_on(lambda_policy)
        
        inline_string = '''import uuid\nimport datetime\nimport json\ndef lambda_handler(event, context):\n    RunParameters = { 'RunId': str(uuid.uuid4())[:8], 'RunDate': str(datetime.datetime.today().date()), 'Environment': 'environment_name', 'Project': 'project_name' }\n    return json.dumps(RunParameters)'''
        inline_string = inline_string.replace("environment_name", environment)
        inline_string = inline_string.replace("project_name", project)
        
        sf_init_lambda = lambda_.CfnFunction(self, "SFInitLambda", 
            code=lambda_.CfnFunction.CodeProperty(
                zip_file=inline_string
            ), 
            role=lambda_iam_role.attr_arn, 
            architectures=["x86_64"],
            description="Lambda function to initialize training pipeline run parameters to maintain Step Function state", 
            function_name=f"pr-{environment}-{project}-run-parameters-lambda", 
            handler="index.lambda_handler",
            memory_size=128, 
            package_type="Zip",
            runtime="python3.8", 
            tags=[
                CfnTag(
                    key="Environment",
                    value=environment
                ),
                CfnTag(
                    key="Project",
                    value=project
                )
            ], 
            timeout=30
        )
        
        sf_init_lambda.add_depends_on(lambda_iam_role)
        
        # ********************************************************************************
        # Data Preparation Lambda Function
        # ********************************************************************************
        
        def get_latest_image_uri(lambda_order: int) -> str:
            '''
                Return the latest ECR image URI for a Lambda function.
                args:
                    lambda_order: Lambda build sequence order according to buildspec
            '''
            search_expr = f"sort_by(imageDetails, &to_string(imagePushedAt))[{lambda_order}].imageTags"
           
            filter_iterator = boto3.client('ecr')\
                .get_paginator('describe_images')\
                .paginate(repositoryName=f"pr-{environment}-{project}-ecr-repo")\
                .search(search_expr)
               
            image_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/pr-{environment}-{project}-ecr-repo:{list(filter_iterator)[0]}"
            return image_uri
        
        assert "data-preparation-lambda" in get_latest_image_uri(-3)
        assert "model-training-lambda" in get_latest_image_uri(-2)
        assert "model-evaluation-lambda" in get_latest_image_uri(-1)
        
        
        data_preparation_lambda = lambda_.CfnFunction(self, "DataPreparationLambda", 
            code=lambda_.CfnFunction.CodeProperty(
                image_uri=get_latest_image_uri(-3)
            ), 
            role=lambda_iam_role.attr_arn, 
            architectures=["x86_64"],
            description="Lambda function to extract, validate, and load small datasets", 
            function_name=f"pr-{environment}-{project}-data-preparation-lambda",
            memory_size=512, 
            package_type="Image",
            tags=[
                CfnTag(
                    key="Environment",
                    value=environment
                ),
                CfnTag(
                    key="Project",
                    value=project
                )
            ], 
            timeout=180
        )
        
        data_preparation_lambda.add_depends_on(lambda_iam_role)
        
        
        # ********************************************************************************
        # Model Training Lambda Function
        # ********************************************************************************
        
        model_training_lambda = lambda_.CfnFunction(self, "ModelTrainingLambda", 
            code=lambda_.CfnFunction.CodeProperty(
                image_uri=get_latest_image_uri(-2)
            ), 
            role=lambda_iam_role.attr_arn, 
            architectures=["x86_64"],
            description="Lambda function to train simple models", 
            function_name=f"pr-{environment}-{project}-model-training-lambda",
            memory_size=512, 
            package_type="Image",
            tags=[
                CfnTag(
                    key="Environment",
                    value=environment
                ),
                CfnTag(
                    key="Project",
                    value=project
                )
            ], 
            timeout=180
        )
        
        model_training_lambda.add_depends_on(lambda_iam_role)
        
        # ********************************************************************************
        # Model Evaluation Lambda Function
        # ********************************************************************************
        
        model_evaluation_lambda = lambda_.CfnFunction(self, "ModelEvaluationLambda", 
            code=lambda_.CfnFunction.CodeProperty(
                image_uri=get_latest_image_uri(-1)
            ), 
            role=lambda_iam_role.attr_arn, 
            architectures=["x86_64"],
            description="Lambda function to evaluate simple models using small datasets", 
            function_name=f"pr-{environment}-{project}-model-evaluation-lambda",
            memory_size=512, 
            package_type="Image",
            tags=[
                CfnTag(
                    key="Environment",
                    value=environment
                ),
                CfnTag(
                    key="Project",
                    value=project
                )
            ], 
            timeout=180
        )
        
        model_evaluation_lambda.add_depends_on(lambda_iam_role)
        
        # ********************************************************************************
        # Step Function State Machine, Log Group, & IAM Role/Policy
        # ********************************************************************************
        
        sf_log_group = logs.CfnLogGroup(self, "StepFunctionLogGroup", 
            log_group_name=f"/aws/vendedlogs/states/pr-{environment}-{project}-training-step-function-logs", 
            retention_in_days=90, 
            tags=[
                CfnTag(
                    key="Environment",
                    value=environment
                ),
                CfnTag(
                    key="Project",
                    value=project
                )
            ]
        )
        
        step_functions_policy = iam.CfnManagedPolicy(self, "StepFunctionsPolicy", 
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "lambda:InvokeFunction"
                        ],
                        "Resource": [
                            sf_init_lambda.attr_arn,
                            f"{sf_init_lambda.attr_arn}:*",
                            data_preparation_lambda.attr_arn,
                            f"{data_preparation_lambda.attr_arn}:*",
                            model_training_lambda.attr_arn,
                            f"{model_training_lambda.attr_arn}:*",
                            model_evaluation_lambda.attr_arn,
                            f"{model_evaluation_lambda.attr_arn}:*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogDelivery",
                            "logs:GetLogDelivery",
                            "logs:UpdateLogDelivery",
                            "logs:DeleteLogDelivery",
                            "logs:ListLogDeliveries",
                            "logs:PutResourcePolicy",
                            "logs:DescribeResourcePolicies",
                            "logs:DescribeLogGroups"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "xray:PutTraceSegments",
                            "xray:PutTelemetryRecords",
                            "xray:GetSamplingRules",
                            "xray:GetSamplingTargets"
                        ],
                        "Resource": "*"
                    }
                ]
            }, 
            description=f"IAM managed policy for {project} training pipeline Step Functions",
            managed_policy_name=f"pr-{environment}-{project}-step-functions-policy"
        )
        
        step_functions_policy.add_depends_on(sf_init_lambda)
        step_functions_policy.add_depends_on(data_preparation_lambda)
        step_functions_policy.add_depends_on(model_training_lambda)
        step_functions_policy.add_depends_on(model_evaluation_lambda)
        step_functions_policy.add_depends_on(sf_log_group)
        
        sf_iam_role = iam.CfnRole(self, "StepFunctionsRole", 
            assume_role_policy_document={
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Effect": "Allow",
                  "Principal": {
                    "Service": [
                        "states.amazonaws.com"
                    ]
                  },
                  "Action": "sts:AssumeRole"
                }
              ]
            }, 
            description=f"IAM role for {project} training pipeline Step Functions", 
            managed_policy_arns=[
                step_functions_policy.ref
            ],
            role_name=f"pr-{environment}-{project}-step-functions-role", 
            path="/service-role/",
            tags=[
                CfnTag(
                    key="Environment",
                    value=environment
                ),
                CfnTag(
                    key="Project",
                    value=project
                )
            ]
        )
        
        sf_iam_role.add_depends_on(step_functions_policy)
        
        training_step_function = sf.CfnStateMachine(self, "TrainingStepFunction", 
            role_arn=sf_iam_role.attr_arn, 
            definition_string=Fn.sub(
                body='''{
                    "StartAt": "Create Run Parameters",
                    "States": {
                      "Create Run Parameters": {
                        "Type": "Task",
                        "Resource": "${init_lambda_arn}",
                        "ResultPath": "$.RunParameters",
                        "Next": "Data Preparation"
                      },
                      "Data Preparation": {
                        "Type": "Task",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                          "FunctionName": "${data_preparation_lambda_arn}",
                            "Payload": {
                              "Input.$": "$"
                            }
                        },
                        "ResultPath": null,
                        "Next": "Model Training"
                      },
                      "Model Training": {
                        "Type": "Task",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                          "FunctionName": "${model_training_lambda_arn}",
                            "Payload": {
                              "Input.$": "$"
                            }
                        },
                        "ResultPath": null,
                        "Next": "Model Evaluation"
                      },
                      "Model Evaluation": {
                          "Type": "Task",
                          "Resource": "arn:aws:states:::lambda:invoke",
                          "Parameters": {
                            "FunctionName": "${model_evaluation_lambda_arn}",
                            "Payload": {
                              "Input.$": "$"
                            }
                          },
                          "End": true
                      }
                    }
                } ''', 
                variables={
                    "environment": environment,
                    "project": project,
                    "init_lambda_arn": sf_init_lambda.attr_arn,
                    "data_preparation_lambda_arn": data_preparation_lambda.attr_arn,
                    "model_training_lambda_arn": model_training_lambda.attr_arn,
                    "model_evaluation_lambda_arn": model_evaluation_lambda.attr_arn
                }
            ),
            logging_configuration=sf.CfnStateMachine.LoggingConfigurationProperty(
                destinations=[
                    sf.CfnStateMachine.LogDestinationProperty(
                        cloud_watch_logs_log_group=sf.CfnStateMachine.CloudWatchLogsLogGroupProperty(
                            log_group_arn=sf_log_group.attr_arn
                        )
                    )
                ], 
                include_execution_data=True, 
                level="ALL"
            ), 
            state_machine_name=f"pr-{environment}-{project}-training-step-function", 
            state_machine_type="STANDARD", 
            tags=[
                sf.CfnStateMachine.TagsEntryProperty(
                    key="Environment",
                    value=environment
                ),
                sf.CfnStateMachine.TagsEntryProperty(
                    key="Project",
                    value=project
                )
            ]
        )
        
        training_step_function.add_depends_on(sf_init_lambda)
        training_step_function.add_depends_on(data_preparation_lambda)
        training_step_function.add_depends_on(model_training_lambda)
        training_step_function.add_depends_on(model_evaluation_lambda)
        training_step_function.add_depends_on(sf_log_group)
        training_step_function.add_depends_on(sf_iam_role)
    
    
