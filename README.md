# MLOps-Challenge

**Actions taken to complete this challenge:**

1. Create an AWS CodeCommit repository and attach it to a SageMaker Studio user.

2. With a data science Jupyter notebook as the starting point, we begin by modularizing it into Python scripts, one for each major component of the ML workflow. Each component will become a Lambda function containing its Python code.

3. We create 3 folders, one for each specialized Lambda function: Data Preparation, Model Training, and Model Evaluation. These serverless microservices will be invoked sequentially by an AWS Step Function orchestrator.

4. We include unit tests to assert our components produce the correct output, placing emphasis on data types and shapes.

5. We include Dockerfile and requirements.txt files for each Lambda function so that we can containerize them at CI/CD build time, across environments.

6. Next, we leverage the Cloud Development Kit (CDK) within Cloud9 to build all the CI/CD and training pipeline infrastructure using object-oriented programming (Python). We choose L1 Constructs to maintain maximum control over the underlying CloudFormation resources.

7. We write 2 classes, CICDStack and LightweightTrainingStack, and perform cdk deploy from the centralized Machine Learning DevOps environment. This provisions an entire CI/CD pipeline and the training pipeline for our Scikit-learn LinearRegression model, respectively.

8. We use AWS CodePipeline with build, test, and cross-account deploy stages, with the source stage listening to commits into the CodeCommit repository from step 1. The source stage also listens to the ML DevOps repository for any releases/updates to the ML infrastructure. This guarantees every ML solution’s infrastructure stays up to date as the ML DevOps team releases changes.

9. Next, we write buildspec.yml files to be used by the CodeBuild components of the CI/CD pipeline. Within a CLI environment, these files containerize the Lambda functions for the various components of the training pipeline and push the Docker images to Elastic Container Registry (ECR). These Lambda image URIs become arguments into the creation/updates of the corresponding Lambda functions during CloudFormation template synthesis through CDK.

These images illustrate the flow of git commits through the CI/CD pipeline:

<img width="1731" alt="CodePipeline1" src="https://user-images.githubusercontent.com/98974746/152398369-cfe7a12e-fb79-404e-b3dc-4ea027cad117.png">
<img width="1720" alt="CodePipeline2" src="https://user-images.githubusercontent.com/98974746/152398374-806f227b-1aa7-46be-92e6-5d05f6a96033.png">

Here we see a successful system test, which involves invoking the training pipeline Step Function and verifying successful execution prior to cross-account production deployments:

<img width="1705" alt="RegressionSF" src="https://user-images.githubusercontent.com/98974746/152406373-22526243-7c31-469d-a55f-e93fd96d8863.png">

**Please refer to cdk/training-pipeline/training_pipeline/ for the Step Function code definition)**

Final MLOps architecture to deploy Scikit-learn regression models:

<img width="749" alt="MLOps-Regression" src="https://user-images.githubusercontent.com/98974746/152399075-31a11edd-8c86-4352-9a4e-04c8b2ca2914.png">



