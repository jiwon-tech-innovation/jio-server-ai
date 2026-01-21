pipeline {
    agent any

    environment {
        AWS_REGION = 'ap-northeast-2'
        ECR_REGISTRY = credentials('aws-account-id') + '.dkr.ecr.' + AWS_REGION + '.amazonaws.com'
        SERVICE_NAME = 'jiaa-server-ai'
        IMAGE_TAG = 'latest'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    dir('jiaa-server-ai') {
                         sh "docker build -t ${SERVICE_NAME}:${IMAGE_TAG} ."
                    }
                }
            }
        }

        stage('Push to ECR') {
            steps {
                script {
                    withAWS(credentials: 'aws-credentials', region: AWS_REGION) {
                        sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
                        sh "docker tag ${SERVICE_NAME}:${IMAGE_TAG} ${ECR_REGISTRY}/${SERVICE_NAME}:${IMAGE_TAG}"
                        sh "docker push ${ECR_REGISTRY}/${SERVICE_NAME}:${IMAGE_TAG}"
                    }
                }
            }
        }

        stage('Deploy to ECS') {
            steps {
                script {
                    withAWS(credentials: 'aws-credentials', region: AWS_REGION) {
                        sh "aws ecs update-service --cluster jiaa-cluster --service ${SERVICE_NAME} --force-new-deployment"
                    }
                }
            }
        }
    }

    post {
        success {
            echo "??Build & Deploy Success: ${SERVICE_NAME}:${IMAGE_TAG}"
        }
        failure {
            echo "??Build Failed: ${SERVICE_NAME}"
        }
        always {
            cleanWs()
        }
    }
}
