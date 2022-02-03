# MLOps-Challenge

Create CodeCommit repository and attach it to a SageMaker Studio user.

With a data science Jupyter notebook as the starting point, we begin by modularizing it into Python scripts, one for each major component of the ML workflow.

We create 3 folders, one for each specialized Lambda function: Data Preparation, Model Training, and Model Evaluation. These serverless microservices will be executed sequentially by AWS Step Functions.

We include unit tests to assert our components produce the correct output, placing emphasis on data types and shapes.

We include Dockerfile and requirements.txt files for each Lambda function so that we can containerize them at CI/CD build time.

Next, we leverage the Cloud Development Kit (CDK) within Cloud9 to build all the infrastructure using object-oriented programming (Python). We choose L1 Constructs to maintain maximum control over the underlying CloudFormation resources.

We write 2 classes, CICDStack and TrainingPipelineStack, and perform cdk deploy from the centralized Machine Learning DevOps environment. This provisions an entire CI/CD pipeline and the training pipeline for our model, respectively.

We use AWS CodePipeline with build, test, and cross-account deploy stages, with the source stage listening to commits into the CodeCommit repository from step 1. The source stage also listens to the ML DevOps repository for any releases/updates to the infrastructures. This guarantees every ML solution’s infrastructure stays up to date as the ML DevOps team releases changes.

Next, we write buildspec.yml files to be used by the CodeBuild components of the CI/CD pipeline. These files containerize the Lambda functions for the various components of the training pipeline, pushes the Docker images to ECR, and stores the image URIs in a DynamoDB table for lookup at TrainingPipelineStack synthesis time.

Next
