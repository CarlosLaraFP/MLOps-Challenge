from aws_cdk import (
    # Duration,
    Stack, Aws, 
    CfnResource, CfnCondition, CfnTag, Fn,
    aws_s3 as s3,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_lambda as lambda_
)
from constructs import Construct
import os
import boto3


class CICDStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, buildspec_yml_build: str, buildspec_yml_factory: str, buildspec_yml_deploy: str, buildspec_yml_prod_factory: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        cdk_repo = self.node.try_get_context("cdk_repo")
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
        # S3 Bucket
        # ********************************************************************************
        
        s3_bucket = s3.CfnBucket(self, "CICDBucket", 
            bucket_encryption=s3.CfnBucket.BucketEncryptionProperty(
                server_side_encryption_configuration=[s3.CfnBucket.ServerSideEncryptionRuleProperty(
                    bucket_key_enabled=False,
                    server_side_encryption_by_default=s3.CfnBucket.ServerSideEncryptionByDefaultProperty(
                        sse_algorithm="AES256"
                    )
                )]
            ),
            bucket_name=f"pr-{environment}-{project}-bucket", 
            # Come back to these later
            intelligent_tiering_configurations=None, 
            lifecycle_configuration=None, 
            metrics_configurations=None, 
            # May be useful for security and compliance reasons later
            object_lock_configuration=None, 
            object_lock_enabled=None, 
            public_access_block_configuration=s3.CfnBucket.PublicAccessBlockConfigurationProperty(
                block_public_acls=True,
                block_public_policy=True,
                ignore_public_acls=True,
                restrict_public_buckets=True
            ), 
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
        
        # ********************************************************************************
        # ECR Image Repository
        # ********************************************************************************
        
        ecr_repo = ecr.CfnRepository(self, "ECRRepo", 
            encryption_configuration=ecr.CfnRepository.EncryptionConfigurationProperty(
                encryption_type="AES256"
            ), 
            image_scanning_configuration=ecr.CfnRepository.ImageScanningConfigurationProperty(
                scan_on_push=True
            ), 
            image_tag_mutability="IMMUTABLE", 
            lifecycle_policy=None, 
            repository_name=f"pr-{environment}-{project}-ecr-repo",
            repository_policy_text={
              "Version": "2008-10-17",
              "Statement": [
                {
                  "Sid": "LambdaECRImageRetrievalPolicy",
                  "Effect": "Allow",
                  "Principal": {
                    "Service": "lambda.amazonaws.com"
                  },
                  "Action": "ecr:*"
                }
              ]
            },
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
        
        # ********************************************************************************
        # CfnCondition to conditionally deploy resources based on target environment
        
        # This means that only if the condition evaluates to ‘true’ when the stack is deployed, the resource will be included.
        # ********************************************************************************
        
        # This must evaluate to false at prod time for the CI/CD pipeline resources
        deploy_condition = CfnCondition(self, "DeployCondition",
            expression=Fn.condition_equals(environment, "test")
        )
        
        # ********************************************************************************
        # CI/CD IAM Role & CodeBuild Inline Policy (build & deploy stages)
        # ********************************************************************************
        
        ci_cd_iam_role = iam.CfnRole(self, "CICDPipelineRole", 
            assume_role_policy_document={
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Effect": "Allow",
                  "Principal": {
                    "Service": [
                        "codebuild.amazonaws.com",
                        "codepipeline.amazonaws.com"
                    ]
                  },
                  "Action": "sts:AssumeRole"
                }
              ]
            }, 
            description=f"Service role for {project} CI/CD CodePipeline & CodeBuild", 
            managed_policy_arns=None,
            path="/service-role/",
            policies=None, 
            role_name=f"pr-{environment}-{project}-ci-cd-pipeline-role", 
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
        
        ci_cd_iam_role.cfn_options.condition = deploy_condition
        
        # Inline policy (user-defined)
        codebuild_policy = iam.CfnPolicy(self, "CodeBuildPolicy", 
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:*"
                        ],
                        "Resource": [
                            f"{s3_bucket.attr_arn}",
                            f"{s3_bucket.attr_arn}/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogStream",
                            "logs:CreateLogGroup",
                            "logs:PutLogEvents"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ecr:*"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "codecommit:*"
                        ],
                        "Resource": f"arn:aws:codecommit:{region}:{account_id}:{cdk_repo}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "codebuild:StartBuild",
                            "codebuild:BatchGetBuilds",
                            "codebuild:ListBuildsForProject"
                        ],
                        "Resource": [
                            f"arn:aws:codebuild:{region}:{account_id}:project/pr-{environment}-{project}-codebuild-build",
                            f"arn:aws:codebuild:{region}:{account_id}:project/pr-{environment}-{project}-codebuild-factory",
                            f"arn:aws:codebuild:{region}:{account_id}:project/pr-{environment}-{project}-codebuild-prod-build",
                            f"arn:aws:codebuild:{region}:{account_id}:project/pr-{environment}-{project}-codebuild-prod-factory"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iam:*",
                            "sts:*",
                            "organizations:DescribeAccount",
                            "organizations:DescribeOrganization",
                            "organizations:DescribeOrganizationalUnit",
                            "organizations:DescribePolicy",
                            "organizations:ListChildren",
                            "organizations:ListParents",
                            "organizations:ListPoliciesForTarget",
                            "organizations:ListRoots",
                            "organizations:ListPolicies",
                            "organizations:ListTargetsForPolicy"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": "sts:AssumeRole",
                        "Resource": f"arn:aws:iam::{prod_account_id}:role/Prod-Deploy-Role"
                    }
    
                ]
            }, 
            policy_name=f"pr-{environment}-{project}-codebuild-policy", 
            roles=[
                ci_cd_iam_role.role_name
            ]
        )
        
        codebuild_policy.cfn_options.condition = deploy_condition
        codebuild_policy.add_depends_on(ci_cd_iam_role)
        
        # ********************************************************************************
        # 2x CodeBuild (CI/CD two-part build stage)
        # ********************************************************************************
        
        def set_buildspec_env_variables(buildspec: str, account_id: str, region: str, repo: str, bucket: str, project: str) -> str:
            '''
            '''
            buildspec = buildspec.replace("aws_account_value", account_id)
            buildspec = buildspec.replace("aws_region_value", region)
            buildspec = buildspec.replace("repo_name", repo)
            buildspec = buildspec.replace("bucket_name", bucket)
            buildspec = buildspec.replace("project_name", project)
            buildspec = buildspec.replace("prod_aws_account", prod_account_id)
            return buildspec
            
        
        buildspec_build = set_buildspec_env_variables(buildspec_yml_build, account_id, region, repo, s3_bucket.bucket_name, project)
        
        codebuild_build = codebuild.CfnProject(self, "BuildCodeBuild", 
            artifacts=codebuild.CfnProject.ArtifactsProperty(
                type="CODEPIPELINE"
            ), 
            environment=codebuild.CfnProject.EnvironmentProperty(
                compute_type="BUILD_GENERAL1_SMALL", 
                image="aws/codebuild/amazonlinux2-x86_64-standard:2.0", 
                type="LINUX_CONTAINER",
                image_pull_credentials_type="CODEBUILD", 
                privileged_mode=True
            ), 
            service_role=ci_cd_iam_role.attr_arn, 
            source=codebuild.CfnProject.SourceProperty(
                type="CODEPIPELINE",
                # Local file passed as a string; buildspec.yml must not be requested from the data scientist
                build_spec=buildspec_build
            ),
            description="CI/CD CodeBuild - Build Stage",
            logs_config=codebuild.CfnProject.LogsConfigProperty(
                cloud_watch_logs=codebuild.CfnProject.CloudWatchLogsConfigProperty(
                    status="ENABLED"
                ), 
                s3_logs=codebuild.CfnProject.S3LogsConfigProperty(
                    status="DISABLED", 
                    encryption_disabled=False)
            ), 
            name=f"pr-{environment}-{project}-codebuild-build", 
            queued_timeout_in_minutes=180, 
            resource_access_role=ci_cd_iam_role.attr_arn,
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
            timeout_in_minutes=120,
            visibility="PRIVATE", 
            vpc_config=None
        )
        
        codebuild_build.cfn_options.condition = deploy_condition
        codebuild_build.add_depends_on(ci_cd_iam_role)
        
        buildspec_factory = set_buildspec_env_variables(buildspec_yml_factory, account_id, region, repo, s3_bucket.bucket_name, project)
        
        codebuild_factory = codebuild.CfnProject(self, "FactoryCodeBuild", 
            artifacts=codebuild.CfnProject.ArtifactsProperty(
                type="CODEPIPELINE"
            ), 
            environment=codebuild.CfnProject.EnvironmentProperty(
                compute_type="BUILD_GENERAL1_SMALL", 
                image="aws/codebuild/amazonlinux2-x86_64-standard:2.0", 
                type="LINUX_CONTAINER",
                image_pull_credentials_type="CODEBUILD", 
                privileged_mode=True
            ), 
            service_role=ci_cd_iam_role.attr_arn, 
            source=codebuild.CfnProject.SourceProperty(
                type="CODEPIPELINE",
                build_spec=buildspec_factory
            ),
            description="CI/CD CodeBuild - Factory Stage", 
            logs_config=codebuild.CfnProject.LogsConfigProperty(
                cloud_watch_logs=codebuild.CfnProject.CloudWatchLogsConfigProperty(
                    status="ENABLED"
                ), 
                s3_logs=codebuild.CfnProject.S3LogsConfigProperty(
                    status="DISABLED", 
                    encryption_disabled=False)
            ), 
            name=f"pr-{environment}-{project}-codebuild-factory", 
            queued_timeout_in_minutes=180, 
            resource_access_role=ci_cd_iam_role.attr_arn, 
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
            timeout_in_minutes=120,
            visibility="PRIVATE", 
            vpc_config=None
        )
        
        codebuild_factory.cfn_options.condition = deploy_condition
        codebuild_factory.add_depends_on(codebuild_policy)
        
        # ********************************************************************************
        # 2x CodeBuild CI/CD cross-account Deploy stage
        # ********************************************************************************
        
        buildspec_prod_build = set_buildspec_env_variables(buildspec_yml_deploy, account_id, region, repo, f"pr-prod-{project}-bucket", project)
        
        codebuild_prod_build = codebuild.CfnProject(self, "DeployCodeBuild", 
            artifacts=codebuild.CfnProject.ArtifactsProperty(
                type="CODEPIPELINE"
            ), 
            environment=codebuild.CfnProject.EnvironmentProperty(
                compute_type="BUILD_GENERAL1_SMALL", 
                image="aws/codebuild/amazonlinux2-x86_64-standard:2.0", 
                type="LINUX_CONTAINER",
                image_pull_credentials_type="CODEBUILD", 
                privileged_mode=True
            ), 
            service_role=ci_cd_iam_role.attr_arn, 
            source=codebuild.CfnProject.SourceProperty(
                type="CODEPIPELINE",
                # Local file passed as a string; buildspec.yml must not be requested from the data scientist
                build_spec=buildspec_prod_build
            ),
            description="CI/CD CodeBuild - Prod Build Stage",
            logs_config=codebuild.CfnProject.LogsConfigProperty(
                cloud_watch_logs=codebuild.CfnProject.CloudWatchLogsConfigProperty(
                    status="ENABLED"
                ), 
                s3_logs=codebuild.CfnProject.S3LogsConfigProperty(
                    status="DISABLED", 
                    encryption_disabled=False)
            ), 
            name=f"pr-{environment}-{project}-codebuild-prod-build", 
            queued_timeout_in_minutes=180, 
            resource_access_role=ci_cd_iam_role.attr_arn,
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
            timeout_in_minutes=120,
            visibility="PRIVATE", 
            vpc_config=None
        )
        
        codebuild_prod_build.cfn_options.condition = deploy_condition
        codebuild_prod_build.add_depends_on(ci_cd_iam_role)
        
        buildspec_prod_factory = set_buildspec_env_variables(buildspec_yml_prod_factory, account_id, region, repo, f"pr-prod-{project}-bucket", project)
        
        codebuild_prod_factory = codebuild.CfnProject(self, "ProdFactoryCodeBuild", 
            artifacts=codebuild.CfnProject.ArtifactsProperty(
                type="CODEPIPELINE"
            ), 
            environment=codebuild.CfnProject.EnvironmentProperty(
                compute_type="BUILD_GENERAL1_SMALL", 
                image="aws/codebuild/amazonlinux2-x86_64-standard:2.0", 
                type="LINUX_CONTAINER",
                image_pull_credentials_type="CODEBUILD", 
                privileged_mode=True
            ), 
            service_role=ci_cd_iam_role.attr_arn, 
            source=codebuild.CfnProject.SourceProperty(
                type="CODEPIPELINE",
                build_spec=buildspec_prod_factory
            ),
            description="CI/CD CodeBuild - Factory Stage", 
            logs_config=codebuild.CfnProject.LogsConfigProperty(
                cloud_watch_logs=codebuild.CfnProject.CloudWatchLogsConfigProperty(
                    status="ENABLED"
                ), 
                s3_logs=codebuild.CfnProject.S3LogsConfigProperty(
                    status="DISABLED", 
                    encryption_disabled=False)
            ), 
            name=f"pr-{environment}-{project}-codebuild-prod-factory", 
            queued_timeout_in_minutes=180, 
            resource_access_role=ci_cd_iam_role.attr_arn, 
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
            timeout_in_minutes=120,
            visibility="PRIVATE", 
            vpc_config=None
        )
        
        codebuild_prod_factory.cfn_options.condition = deploy_condition
        codebuild_prod_factory.add_depends_on(codebuild_policy)
        
        # ********************************************************************************
        # CodePipeline (CI/CD orchestrator) & IAM Inline Policy
        # ********************************************************************************
        
        # Inline policy (user-defined)
        codepipeline_policy = iam.CfnPolicy(self, "CodePipelinePolicy", 
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "codebuild:*"
                        ],
                        "Resource": [
                            codebuild_build.attr_arn,
                            codebuild_factory.attr_arn,
                            codebuild_prod_build.attr_arn,
                            codebuild_prod_factory.attr_arn
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "codecommit:*"
                        ],
                        "Resource": f"arn:aws:codecommit:{region}:{account_id}:{repo}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "states:DescribeStateMachine",
                            "states:StartExecution",
                            "states:DescribeExecution"
                        ],
                        "Resource": [
                            f"arn:aws:states:{region}:{account_id}:stateMachine:pr-{environment}-{project}-training-step-function",
                            f"arn:aws:states:{region}:{account_id}:execution:pr-{environment}-{project}-training-step-function:*"
                        ]
                    }
                ]
            }, 
            policy_name=f"pr-{environment}-{project}-codepipeline-policy", 
            roles=[
                ci_cd_iam_role.role_name
            ]
        )
        
        codepipeline_policy.cfn_options.condition = deploy_condition
        codepipeline_policy.add_depends_on(ci_cd_iam_role)
        codepipeline_policy.add_depends_on(codebuild_build)
        codepipeline_policy.add_depends_on(codebuild_factory)
        codepipeline_policy.add_depends_on(codebuild_prod_build)
        codepipeline_policy.add_depends_on(codebuild_prod_factory)
        
        ci_cd_codepipeline = codepipeline.CfnPipeline(self, "CICDCodePipeline", 
            role_arn=ci_cd_iam_role.attr_arn, 
            stages=[
                codepipeline.CfnPipeline.StageDeclarationProperty(
                    actions=[
                        codepipeline.CfnPipeline.ActionDeclarationProperty(
                            action_type_id=codepipeline.CfnPipeline.ActionTypeIdProperty(
                                category="Source", 
                                owner="AWS", 
                                provider="CodeCommit", 
                                version="1"
                            ), 
                            name="Project-Commits",
                            configuration={
                                "BranchName": "main", 
                                "RepositoryName": repo
                            }, 
                            input_artifacts=None,
                            namespace="SourceVariables", 
                            output_artifacts=[
                                codepipeline.CfnPipeline.OutputArtifactProperty(name="SourceArtifact")
                            ], 
                            region=region
                        ),
                        codepipeline.CfnPipeline.ActionDeclarationProperty(
                            action_type_id=codepipeline.CfnPipeline.ActionTypeIdProperty(
                                category="Source", 
                                owner="AWS", 
                                provider="CodeCommit", 
                                version="1"
                            ), 
                            name="CDK-Releases",
                            configuration={
                                "BranchName": "main", 
                                "RepositoryName": cdk_repo
                            }, 
                            input_artifacts=None,
                            namespace="CDKVariables", 
                            output_artifacts=[
                                codepipeline.CfnPipeline.OutputArtifactProperty(name="CDKSourceArtifact")
                            ], 
                            region=region
                        )
                    ], 
                    name="Source"
                ),
                codepipeline.CfnPipeline.StageDeclarationProperty(
                    actions=[
                        codepipeline.CfnPipeline.ActionDeclarationProperty(
                            action_type_id=codepipeline.CfnPipeline.ActionTypeIdProperty(
                                category="Build", 
                                owner="AWS", 
                                provider="CodeBuild", 
                                version="1"
                            ), 
                            name="Build", 
                            configuration={
                                "ProjectName": codebuild_build.name
                            }, 
                            input_artifacts=[
                                codepipeline.CfnPipeline.InputArtifactProperty(name="SourceArtifact")
                            ],
                            output_artifacts=[
                                codepipeline.CfnPipeline.OutputArtifactProperty(name="BuildArtifact")
                            ], 
                            region=region,
                            run_order=1
                        ),
                        codepipeline.CfnPipeline.ActionDeclarationProperty(
                            action_type_id=codepipeline.CfnPipeline.ActionTypeIdProperty(
                                category="Build", 
                                owner="AWS", 
                                provider="CodeBuild", 
                                version="1"
                            ), 
                            name="Factory", 
                            configuration={
                                "ProjectName": codebuild_factory.name
                            }, 
                            input_artifacts=[
                                codepipeline.CfnPipeline.InputArtifactProperty(name="CDKSourceArtifact")
                            ],
                            output_artifacts=[
                                codepipeline.CfnPipeline.OutputArtifactProperty(name="CDKBuildArtifact")
                            ], 
                            region=region,
                            run_order=2
                        )
                    ], 
                    name="Build"
                ),
                codepipeline.CfnPipeline.StageDeclarationProperty(
                    actions=[
                        codepipeline.CfnPipeline.ActionDeclarationProperty(
                            action_type_id=codepipeline.CfnPipeline.ActionTypeIdProperty(
                                    category="Invoke", 
                                    owner="AWS", 
                                    provider="StepFunctions", 
                                    version="1"
                            ),
                            name="System-Testing", 
                            configuration={
                                "StateMachineArn": f"arn:aws:states:{region}:{account_id}:stateMachine:pr-{environment}-{project}-training-step-function"
                            }, 
                            input_artifacts=[
                                codepipeline.CfnPipeline.InputArtifactProperty(name="CDKBuildArtifact")
                            ],
                            output_artifacts=[
                                codepipeline.CfnPipeline.OutputArtifactProperty(name="SystemTestArtifact")
                            ],
                            region=region,
                            # Run after unit testing, after integration testing; run_order=3
                            run_order=None
                        )
                    ], 
                    name="Test"
                ),
                codepipeline.CfnPipeline.StageDeclarationProperty(
                    actions=[
                        codepipeline.CfnPipeline.ActionDeclarationProperty(
                            action_type_id=codepipeline.CfnPipeline.ActionTypeIdProperty(
                                category="Build", 
                                owner="AWS", 
                                provider="CodeBuild", 
                                version="1"
                            ), 
                            name="Prod-Build", 
                            configuration={
                                "ProjectName": codebuild_prod_build.name
                            }, 
                            input_artifacts=[
                                codepipeline.CfnPipeline.InputArtifactProperty(name="SourceArtifact")
                            ],
                            output_artifacts=[
                                codepipeline.CfnPipeline.OutputArtifactProperty(name="ProdBuildArtifact")
                            ], 
                            region=region,
                            run_order=1
                        ),
                        codepipeline.CfnPipeline.ActionDeclarationProperty(
                            action_type_id=codepipeline.CfnPipeline.ActionTypeIdProperty(
                                category="Build", 
                                owner="AWS", 
                                provider="CodeBuild", 
                                version="1"
                            ), 
                            name="Prod-Factory", 
                            configuration={
                                "ProjectName": codebuild_prod_factory.name
                            }, 
                            input_artifacts=[
                                codepipeline.CfnPipeline.InputArtifactProperty(name="CDKSourceArtifact")
                            ],
                            output_artifacts=[
                                codepipeline.CfnPipeline.OutputArtifactProperty(name="ProdCDKBuildArtifact")
                            ], 
                            region=region,
                            run_order=2
                        )
                    ], 
                    name="Deploy"
                )
            ], 
            artifact_store=codepipeline.CfnPipeline.ArtifactStoreProperty(
                location=s3_bucket.bucket_name, 
                type="S3"),
            disable_inbound_stage_transitions=None, 
            name=f"pr-{environment}-{project}-training-codepipeline", 
            restart_execution_on_update=False, 
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
        
        ci_cd_codepipeline.cfn_options.condition = deploy_condition
        ci_cd_codepipeline.add_depends_on(s3_bucket)
        ci_cd_codepipeline.add_depends_on(codepipeline_policy)
        
    
    