# EchoPrime Infrastructure

This directory contains the OpenTofu (Terraform) configuration for the EchoPrime SageMaker deployment infrastructure.

## Architecture

The infrastructure is organized into the following components:

- **IAM**: Roles and policies for SageMaker and GitHub Actions
- **Storage**: S3 bucket for SageMaker data with proper encryption and lifecycle policies
- **ECR**: Container registry for the EchoPrime Docker image
- **SageMaker**: Model, endpoint configuration, and endpoint for inference

## Security Features

- KMS encryption for all sensitive data (S3, ECR)
- GitHub Actions OIDC for secure CI/CD without long-term credentials
- Least privilege IAM policies
- S3 bucket policies enforcing encryption and TLS
- ECR image scanning on push

## Modules

The configuration is organized into reusable modules:

- `modules/iam`: IAM roles and policies
- `modules/storage`: S3 bucket and related resources
- `modules/ecr`: ECR repository and related resources

## State Management

The state is stored in an S3 bucket with the following configuration:

- Bucket: `echoprime-terraform-state`
- Key: `echoprime/terraform.tfstate`
- Region: `us-west-2`
- DynamoDB Table for Locking: `echoprime-terraform-locks`

## Usage

### Prerequisites

- AWS CLI configured with appropriate credentials
- OpenTofu or Terraform installed

### Initialization

```bash
cd opentofu
tofu init
```

### Planning

```bash
tofu plan -out=tfplan
```

### Applying

```bash
tofu apply tfplan
```

### Destroying

```bash
tofu destroy
```

## GitHub Actions Integration

This infrastructure works with GitHub Actions for CI/CD using AWS access keys.

### Setting Up GitHub Actions Authentication

1. Add the following secrets to your GitHub repository:
   - `AWS_REGION`: The AWS region (e.g., `us-west-2`)
   - `AWS_ACCESS_KEY_ID`: Your AWS access key
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key

2. The GitHub Actions workflow uses these credentials to:
   - Deploy infrastructure changes with OpenTofu
   - Build and push Docker images to ECR
   - Deploy models to SageMaker

### Workflow Configuration

The workflow:
1. Uses AWS access keys to authenticate with AWS
2. Extracts outputs from the modular OpenTofu configuration
3. Deploys to SageMaker using the same credentials

### Example Access Key Configuration

```yaml
jobs:
  deploy:
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}
```

### Future Security Enhancement

For improved security, consider migrating to OIDC authentication in the future, which:
- Eliminates the need for long-term access keys
- Uses short-lived credentials
- Reduces credential management overhead

## Important Notes

- The SageMaker endpoint is configured for async inference
- Auto-scaling is enabled for the SageMaker endpoint
- ECR lifecycle policies automatically clean up old images
- S3 lifecycle policies expire inference outputs after 30 days
