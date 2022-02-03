# MLOps-Challenge

Steps followed:

1. Create CodeCommit repository and attach it to a SageMaker Studio user.

2. With a data science Jupyter notebook as the starting point, we begin by modularizing it into Python scripts, one for each major component of the ML workflow. Each component will become a Lambda function containing its Python code.

3. We create 3 folders, one for each specialized Lambda function: Data Preparation, Model Training, and Model Evaluation. These serverless microservices will be invoked sequentially by AWS Step Functions.

4. We include unit tests to assert our components produce the correct output, placing emphasis on data types and shapes.

5. We include Dockerfile and requirements.txt files for each Lambda function so that we can containerize them at CI/CD build time.

6. Next, we leverage the Cloud Development Kit (CDK) within Cloud9 to build all the infrastructure using object-oriented programming (Python). We choose L1 Constructs to maintain maximum control over the underlying CloudFormation resources.

7. We write 2 classes, CICDStack and TrainingPipelineStack, and perform cdk deploy from the centralized Machine Learning DevOps environment. This provisions an entire CI/CD pipeline and the training pipeline for our model, respectively.

8. We use AWS CodePipeline with build, test, and cross-account deploy stages, with the source stage listening to commits into the CodeCommit repository from step 1. The source stage also listens to the ML DevOps repository for any releases/updates to the infrastructures. This guarantees every ML solution’s infrastructure stays up to date as the ML DevOps team releases changes.

9. Next, we write buildspec.yml files to be used by the CodeBuild components of the CI/CD pipeline. These files containerize the Lambda functions for the various components of the training pipeline, pushes the Docker images to ECR, and stores the image URIs in a DynamoDB table for lookup at TrainingPipelineStack synthesis time.


<img width="1731" alt="CodePipeline1" src="https://user-images.githubusercontent.com/98974746/152398369-cfe7a12e-fb79-404e-b3dc-4ea027cad117.png">
<img width="1720" alt="CodePipeline2" src="https://user-images.githubusercontent.com/98974746/152398374-806f227b-1aa7-46be-92e6-5d05f6a96033.png">

Final MLOps architecture to deploy Scikit-learn regression models:

<img width="749" alt="MLOps-Regression" src="https://user-images.githubusercontent.com/98974746/152399075-31a11edd-8c86-4352-9a4e-04c8b2ca2914.png">



