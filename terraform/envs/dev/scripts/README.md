# Terraform Development Environment Setup

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform installed
- Proper AWS permissions for creating resources

## Directory Structure

Navigate to the development environment directory:
```bash
cd /terraform/envs/dev
```

---

## SPIN UP

### Step 1: Initialize Terraform
```bash
terraform init
```

### Step 2: Setup Prerequisites

Make the setup script executable and run it to create initial credentials and generate GitHub workflow:
```bash
chmod +x setup-dev-env-prerequisites.sh
./setup-dev-env-prerequisites.sh
```

This script will:
- Create initial AWS credentials (SSM parameters, Secrets Manager secrets)
- Generate GitHub workflow configurations

### Step 3: Apply Terraform Configuration

Initialize Terraform (if not already done) and apply the configuration:
```bash
terraform init
terraform apply -var="engineer_name=<ENGINEER_NAME>"
```

Review the plan and type `yes` to confirm and create the infrastructure.

---

## TEAR DOWN

### Step 1: Destroy Infrastructure
```bash
terraform destroy -var="engineer_name=<ENGINEER_NAME>" -refresh=false
```

> **Note**: Use `-refresh=false` flag to avoid errors with missing secrets/parameters during destruction.

If you encounter errors about missing resources, you can also try:
```bash
terraform destroy -var="engineer_name=<ENGINEER_NAME>" -refresh=false -auto-approve
```

### Step 2: Cleanup Secrets

Make the cleanup script executable and run it to remove initial credentials:
```bash
chmod +x cleanup-dev-env.sh
./cleanup-dev-env.sh
```

This script will:
- Remove SSM parameters
- Delete Secrets Manager secrets
- Clean up any residual credentials

---