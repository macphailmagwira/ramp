#!/bin/bash

# ==================================================
# STITCHSENSE DEV ENVIRONMENT PREREQUISITES SETUP
# ==================================================
# Creates only: EC2 key pair, RDS password in SSM, 
# and RDS credentials in Secrets Manager
# ==================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# AWS Configuration
AWS_PROFILE="stitchsense-dev"
AWS_REGION="ap-southeast-1"
USE_PROFILE=false

# Functions
print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║   🔐 STITCHSENSE DEV PREREQUISITES SETUP                     ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Find git repository root
find_repo_root() {
    local current_dir="$PWD"
    while [ "$current_dir" != "/" ]; do
        if [ -d "$current_dir/.git" ]; then
            echo "$current_dir"
            return 0
        fi
        current_dir="$(dirname "$current_dir")"
    done
    
    # Fallback to script-based calculation
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    echo "$(cd "${script_dir}/../.." && pwd)"
}

# Build AWS command with or without profile
aws_cmd() {
    if [ "$USE_PROFILE" = true ]; then
        aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
    else
        aws --region "$AWS_REGION" "$@"
    fi
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install it first."
        exit 1
    fi
    print_success "AWS CLI installed"
    
    # Check AWS credentials
    if aws sts get-caller-identity --profile "$AWS_PROFILE" &> /dev/null; then
        USE_PROFILE=true
        CALLER_IDENTITY=$(aws sts get-caller-identity --profile "$AWS_PROFILE" 2>/dev/null)
        print_success "AWS credentials configured (using profile: $AWS_PROFILE)"
    elif aws sts get-caller-identity &> /dev/null; then
        USE_PROFILE=false
        CALLER_IDENTITY=$(aws sts get-caller-identity 2>/dev/null)
        print_success "AWS credentials configured (using environment variables)"
    else
        print_error "AWS credentials not configured."
        echo ""
        print_info "Please configure credentials using ONE of these methods:"
        echo ""
        echo "  Option 1 - Named Profile:"
        echo "    aws configure --profile $AWS_PROFILE"
        echo ""
        echo "  Option 2 - Environment Variables:"
        echo "    export AWS_ACCESS_KEY_ID=your_access_key"
        echo "    export AWS_SECRET_ACCESS_KEY=your_secret_key"
        echo "    export AWS_DEFAULT_REGION=$AWS_REGION"
        echo ""
        exit 1
    fi
    
    # Display AWS account info
    ACCOUNT_ID=$(echo "$CALLER_IDENTITY" | jq -r .Account)
    USER_ARN=$(echo "$CALLER_IDENTITY" | jq -r .Arn)
    print_info "AWS Account: $ACCOUNT_ID"
    print_info "Identity: $USER_ARN"
    
    echo ""
}

# Get engineer name
get_engineer_name() {
    if [ -n "$1" ]; then
        ENGINEER_NAME="$1"
        if [[ ! "$ENGINEER_NAME" =~ ^[a-z]{3,10}$ ]]; then
            print_error "Invalid name. Must be 3-10 lowercase letters only."
            exit 1
        fi
    else
        while true; do
            read -p "Enter your engineer name (3-10 lowercase letters, e.g., 'john'): " ENGINEER_NAME
            
            if [[ "$ENGINEER_NAME" =~ ^[a-z]{3,10}$ ]]; then
                break
            else
                print_error "Invalid name. Must be 3-10 lowercase letters only."
            fi
        done
    fi
    
    print_success "Engineer name: $ENGINEER_NAME"
    echo ""
}

# Generate secure password
generate_password() {
    PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
    echo "$PASSWORD"
}

# Create EC2 key pair and store in SSM
create_key_pair_in_ssm() {
    print_info "Creating EC2 key pair and storing in SSM..."
    
    KEY_NAME="stitchsense-${ENGINEER_NAME}-key"
    SSM_PARAM_NAME="/stitchsense/dev-${ENGINEER_NAME}/ec2/ssh_private_key"
    
    # Check if key pair already exists in AWS
    if aws_cmd ec2 describe-key-pairs --key-names "$KEY_NAME" &> /dev/null; then
        print_warning "Key pair already exists in AWS: $KEY_NAME"
        
        # Check if SSM parameter exists
        if aws_cmd ssm get-parameter --name "$SSM_PARAM_NAME" &> /dev/null; then
            print_success "Private key already stored in SSM: $SSM_PARAM_NAME"
            return
        else
            print_error "Key pair exists in AWS but private key not found in SSM"
            read -p "Do you want to delete the AWS key pair and create a new one? (y/n): " RECREATE_KEY
            
            if [[ "$RECREATE_KEY" == "y" ]]; then
                aws_cmd ec2 delete-key-pair --key-name "$KEY_NAME" > /dev/null 2>&1
                print_info "Deleted existing key pair from AWS"
            else
                print_error "Cannot proceed without the private key in SSM."
                exit 1
            fi
        fi
    fi
    
    # Create new key pair and capture the private key
    print_info "Creating new key pair..."
    PRIVATE_KEY=$(aws_cmd ec2 create-key-pair \
        --key-name "$KEY_NAME" \
        --query 'KeyMaterial' \
        --output text)
    
    # Store private key in SSM Parameter Store
    print_info "Storing private key in SSM Parameter Store..."
    aws_cmd ssm put-parameter \
        --name "$SSM_PARAM_NAME" \
        --description "SSH private key for ${ENGINEER_NAME}'s EC2 instances" \
        --type "SecureString" \
        --value "$PRIVATE_KEY" \
        --overwrite > /dev/null 2>&1
    
    print_success "Created EC2 key pair: $KEY_NAME"
    print_success "Private key stored in SSM: $SSM_PARAM_NAME"
    echo ""
}

# Create SSM parameter for RDS password
create_ssm_parameter() {
    print_info "Creating SSM Parameter for RDS password..."
    
    PARAM_NAME="/stitchsense/dev-${ENGINEER_NAME}/rds/password"
    
    # Check if parameter already exists
    if aws_cmd ssm get-parameter --name "$PARAM_NAME" &> /dev/null; then
        print_warning "SSM parameter already exists: $PARAM_NAME"
        read -p "Do you want to update it? (y/n): " UPDATE_PARAM
        
        if [[ "$UPDATE_PARAM" != "y" ]]; then
            print_info "Skipping SSM parameter creation"
            return
        fi
    fi
    
    # Generate password
    RDS_PASSWORD=$(generate_password)
    
    # Create or update parameter
    aws_cmd ssm put-parameter \
        --name "$PARAM_NAME" \
        --type "SecureString" \
        --value "$RDS_PASSWORD" \
        --overwrite > /dev/null 2>&1
    
    print_success "Created SSM parameter: $PARAM_NAME"
    echo ""
}

# Create Secrets Manager secret
create_secrets_manager_secret() {
    print_info "Creating Secrets Manager secret for RDS..."
    
    SECRET_NAME="stitchsense/dev-${ENGINEER_NAME}/rds"
    DB_USERNAME="stitchsense_${ENGINEER_NAME}"
    DB_NAME="stitchsense_dev_${ENGINEER_NAME}"
    
    # Get the password from SSM to keep them in sync
    RDS_PASSWORD=$(aws_cmd ssm get-parameter \
        --name "/stitchsense/dev-${ENGINEER_NAME}/rds/password" \
        --with-decryption \
        --query 'Parameter.Value' \
        --output text)
    
    # Check if secret already exists
    if aws_cmd secretsmanager describe-secret --secret-id "$SECRET_NAME" &> /dev/null; then
        print_warning "Secret already exists: $SECRET_NAME"
        read -p "Do you want to update it? (y/n): " UPDATE_SECRET
        
        if [[ "$UPDATE_SECRET" != "y" ]]; then
            print_info "Skipping Secrets Manager secret creation"
            return
        fi
        
        # Update existing secret
        aws_cmd secretsmanager update-secret \
            --secret-id "$SECRET_NAME" \
            --secret-string "{
                \"username\": \"$DB_USERNAME\",
                \"password\": \"$RDS_PASSWORD\",
                \"engine\": \"postgres\",
                \"host\": \"placeholder\",
                \"port\": 5432,
                \"dbname\": \"$DB_NAME\"
            }" > /dev/null 2>&1
        
        print_success "Updated Secrets Manager secret: $SECRET_NAME"
    else
        # Create new secret
        aws_cmd secretsmanager create-secret \
            --name "$SECRET_NAME" \
            --description "RDS credentials for dev-${ENGINEER_NAME} environment" \
            --secret-string "{
                \"username\": \"$DB_USERNAME\",
                \"password\": \"$RDS_PASSWORD\",
                \"engine\": \"postgres\",
                \"host\": \"placeholder\",
                \"port\": 5432,
                \"dbname\": \"$DB_NAME\"
            }" > /dev/null 2>&1
        
        print_success "Created Secrets Manager secret: $SECRET_NAME"
    fi
    
    echo ""
}

# Verify setup
verify_setup() {
    print_info "Verifying setup..."
    
    # Check EC2 key pair in AWS
    KEY_NAME="stitchsense-${ENGINEER_NAME}-key"
    if aws_cmd ec2 describe-key-pairs --key-names "$KEY_NAME" &> /dev/null; then
        print_success "EC2 key pair exists in AWS: $KEY_NAME"
    else
        print_error "EC2 key pair not found in AWS: $KEY_NAME"
        return 1
    fi
    
    # Check EC2 private key in SSM
    SSM_KEY_PARAM="/stitchsense/dev-${ENGINEER_NAME}/ec2/ssh_private_key"
    if aws_cmd ssm get-parameter --name "$SSM_KEY_PARAM" &> /dev/null; then
        print_success "Private key stored in SSM: $SSM_KEY_PARAM"
    else
        print_error "Private key not found in SSM: $SSM_KEY_PARAM"
        return 1
    fi
    
    # Check RDS password SSM parameter
    PARAM_NAME="/stitchsense/dev-${ENGINEER_NAME}/rds/password"
    if aws_cmd ssm get-parameter --name "$PARAM_NAME" &> /dev/null; then
        print_success "RDS password exists in SSM: $PARAM_NAME"
    else
        print_error "RDS password not found in SSM: $PARAM_NAME"
        return 1
    fi
    
    # Check Secrets Manager secret
    SECRET_NAME="stitchsense/dev-${ENGINEER_NAME}/rds"
    if aws_cmd secretsmanager describe-secret --secret-id "$SECRET_NAME" &> /dev/null; then
        print_success "Secrets Manager secret exists: $SECRET_NAME"
    else
        print_error "Secrets Manager secret not found in $SECRET_NAME"
        return 1
    fi
    
    echo ""
    return 0
}

# Generate GitHub workflow file using JSON file approach (same as staging)
generate_github_workflow() {
    print_info "Generating GitHub workflow file for ${ENGINEER_NAME}..."
    
    # Get current Git branch
    if command -v git &> /dev/null && git rev-parse --git-dir > /dev/null 2>&1; then
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
        print_info "Current Git branch: $CURRENT_BRANCH"
    else
        print_warning "Not in a Git repository or Git not installed"
        CURRENT_BRANCH="dev-${ENGINEER_NAME}"
        print_info "Will use branch: $CURRENT_BRANCH"
    fi
    
    # Find repository root
    REPO_ROOT="$(find_repo_root)"
    WORKFLOWS_DIR="${REPO_ROOT}/.github/workflows"
    
    print_info "Repository root: $REPO_ROOT"
    print_info "Workflows directory: $WORKFLOWS_DIR"
    
    # Check if .github/workflows directory exists
    if [ ! -d "$WORKFLOWS_DIR" ]; then
        print_error ".github/workflows directory not found at: $WORKFLOWS_DIR"
        print_info "Creating .github/workflows directory..."
        mkdir -p "$WORKFLOWS_DIR"
        if [ -d "$WORKFLOWS_DIR" ]; then
            print_success "Created .github/workflows directory"
        else
            print_error "Failed to create .github/workflows directory"
            return 1
        fi
    else
        print_success "Found .github/workflows directory"
    fi
    
    WORKFLOW_FILE="${WORKFLOWS_DIR}/deploy-dev-${ENGINEER_NAME}.yml"
    
    # Check if workflow already exists
    if [ -f "$WORKFLOW_FILE" ]; then
        print_warning "Workflow file already exists: $WORKFLOW_FILE"
        read -p "Do you want to overwrite it? (y/n): " OVERWRITE
        if [[ "$OVERWRITE" != "y" ]]; then
            print_info "Skipping workflow generation"
            return 0
        fi
    fi
    
    # Generate workflow using the STAGING APPROACH (JSON file + heredoc)
    cat > "$WORKFLOW_FILE" <<'EOF'
name: Build and Deploy to Dev EC2 (ENGINEER_NAME_PLACEHOLDER)
on:
  push:
    branches:
      - 'CURRENT_BRANCH_PLACEHOLDER'
    paths:
      - 'apps/**'
      - 'packages/**'
      - 'docker-compose*.yml'
      - 'Dockerfile*'

  workflow_dispatch:
    inputs:
      action:
        description: 'Action to perform'
        required: true
        default: 'deploy'
        type: choice
        options:
          - deploy
          - destroy
      image_tag:
        description: 'Docker image tag (default: commit SHA)'
        required: false
        type: string

concurrency:
  group: dev-ENGINEER_NAME_PLACEHOLDER-deployment-${{ github.ref }}
  cancel-in-progress: false

env:
  AWS_REGION: ap-southeast-1
  ECR_REGISTRY: 514145637758.dkr.ecr.ap-southeast-1.amazonaws.com
  ENGINEER_NAME: ENGINEER_NAME_PLACEHOLDER
  NODE_VERSION: '20'
  PNPM_VERSION: '10.10.0'
  PYTHON_VERSION: '3.11'
  POETRY_VERSION: '1.8.3'

permissions:
  id-token: write
  contents: read
  actions: write
  checks: write

jobs:
  build-api:
    if: github.event_name == 'push' || github.event.inputs.action != 'destroy'
    runs-on: ubuntu-latest
    outputs:
      api_image: ${{ steps.api-image.outputs.api_image }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup pnpm
        uses: pnpm/action-setup@v2
        with:
          version: ${{ env.PNPM_VERSION }}

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'pnpm'

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::514145637758:role/GitHubActions-StitchSense-DeployRole
          aws-region: ${{ env.AWS_REGION }}

      - name: Install dependencies
        run: |
          export NODE_OPTIONS="--max-old-space-size=6144"
          pnpm install --no-frozen-lockfile

          if [ -f apps/api-main/pyproject.toml ]; then
            cd apps/api-main
            poetry config virtualenvs.in-project true
            poetry install --no-interaction --no-ansi
            cd ../..
          fi

      - name: Build & push API Docker image
        id: build-push
        run: |
          ECR_REPOSITORY="stitchsense-dev-${ENGINEER_NAME}-api-main"
          IMAGE_TAG="${{ github.event.inputs.image_tag || github.sha }}"
          FULL_IMAGE_URI="${{ env.ECR_REGISTRY }}/${ECR_REPOSITORY}:${IMAGE_TAG}"

          echo "Building API image..."
          docker compose -f docker-compose.dev.yml build api-main
          docker tag stitchsense-monorepo-api-main:latest ${FULL_IMAGE_URI}

          echo "Creating ECR repository if needed..."
          aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region ${{ env.AWS_REGION }} 2>/dev/null || \
            aws ecr create-repository --repository-name "$ECR_REPOSITORY" --region ${{ env.AWS_REGION }} \
            --image-scanning-configuration scanOnPush=true --encryption-configuration encryptionType=AES256

          echo "Logging in to ECR..."
          aws ecr get-login-password --region "${{ env.AWS_REGION }}" | docker login --username AWS --password-stdin "${{ env.ECR_REGISTRY }}"

          echo "Pushing image..."
          docker push ${FULL_IMAGE_URI}

          echo "✅ Image pushed: ${FULL_IMAGE_URI}"

      - name: Set API image output
        id: api-image
        run: |
          IMAGE_URI="${{ env.ECR_REGISTRY }}/stitchsense-dev-${ENGINEER_NAME}-api-main:${{ github.event.inputs.image_tag || github.sha }}"
          echo "${IMAGE_URI}" > api-image.txt
          echo "api_image=${IMAGE_URI}" >> $GITHUB_OUTPUT

      - name: Upload API image artifact
        uses: actions/upload-artifact@v4
        with:
          name: api-image-uri
          path: api-image.txt
          retention-days: 1

  build-worker:
    if: github.event_name == 'push' || github.event.inputs.action != 'destroy'
    runs-on: ubuntu-latest
    outputs:
      worker_image: ${{ steps.worker-image.outputs.worker_image }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup pnpm
        uses: pnpm/action-setup@v2
        with:
          version: ${{ env.PNPM_VERSION }}

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'pnpm'

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::514145637758:role/GitHubActions-StitchSense-DeployRole
          aws-region: ${{ env.AWS_REGION }}

      - name: Install dependencies
        run: |
          export NODE_OPTIONS="--max-old-space-size=6144"
          pnpm install --no-frozen-lockfile

          if [ -f apps/worker-main/pyproject.toml ]; then
            cd apps/worker-main
            poetry config virtualenvs.in-project true
            poetry install --no-interaction --no-ansi
            cd ../..
          fi

      - name: Build & push Worker Docker image
        id: build-push
        run: |
          ECR_REPOSITORY="stitchsense-dev-${ENGINEER_NAME}-worker-main"
          IMAGE_TAG="${{ github.event.inputs.image_tag || github.sha }}"
          FULL_IMAGE_URI="${{ env.ECR_REGISTRY }}/${ECR_REPOSITORY}:${IMAGE_TAG}"

          echo "Building Worker image..."
          docker compose -f docker-compose.dev.yml build celery-worker-main
          docker tag stitchsense-monorepo-celery-worker-main:latest ${FULL_IMAGE_URI}

          echo "Creating ECR repository if needed..."
          aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region ${{ env.AWS_REGION }} 2>/dev/null || \
            aws ecr create-repository --repository-name "$ECR_REPOSITORY" --region ${{ env.AWS_REGION }} \
            --image-scanning-configuration scanOnPush=true --encryption-configuration encryptionType=AES256

          echo "Logging in to ECR..."
          aws ecr get-login-password --region "${{ env.AWS_REGION }}" | docker login --username AWS --password-stdin "${{ env.ECR_REGISTRY }}"

          echo "Pushing image..."
          docker push ${FULL_IMAGE_URI}

          echo "✅ Image pushed: ${FULL_IMAGE_URI}"

      - name: Set Worker image output
        id: worker-image
        run: |
          IMAGE_URI="${{ env.ECR_REGISTRY }}/stitchsense-dev-${ENGINEER_NAME}-worker-main:${{ github.event.inputs.image_tag || github.sha }}"
          echo "${IMAGE_URI}" > worker-image.txt
          echo "worker_image=${IMAGE_URI}" >> $GITHUB_OUTPUT

      - name: Upload Worker image artifact
        uses: actions/upload-artifact@v4
        with:
          name: worker-image-uri
          path: worker-image.txt
          retention-days: 1

  deploy-to-ec2:
    needs: [build-api, build-worker]
    if: |
      always() &&
      github.event.inputs.action != 'destroy' &&
      needs.build-api.result == 'success' &&
      needs.build-worker.result == 'success'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::514145637758:role/GitHubActions-StitchSense-DeployRole
          aws-region: ${{ env.AWS_REGION }}

      - name: Download API image artifact
        uses: actions/download-artifact@v4
        with:
          name: api-image-uri

      - name: Download Worker image artifact
        uses: actions/download-artifact@v4
        with:
          name: worker-image-uri

      - name: Read image URIs from artifacts
        id: images
        run: |
          API_IMAGE=$(cat api-image.txt)
          WORKER_IMAGE=$(cat worker-image.txt)

          echo "API: ${API_IMAGE}"
          echo "Worker: ${WORKER_IMAGE}"

          echo "api_image=${API_IMAGE}" >> $GITHUB_OUTPUT
          echo "worker_image=${WORKER_IMAGE}" >> $GITHUB_OUTPUT

      - name: Get Dev EC2 instance ID
        id: get-instance
        run: |
          INSTANCE_ID=$(aws ec2 describe-instances \
            --filters "Name=tag:Name,Values=stitchsense-dev-${ENGINEER_NAME}-ec2" \
                      "Name=instance-state-name,Values=running" \
            --query "Reservations[0].Instances[0].InstanceId" \
            --output text)

          if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "None" ]]; then
            echo "❌ Dev EC2 instance not found for ${ENGINEER_NAME}"
            exit 1
          fi

          echo "instance_id=$INSTANCE_ID" >> $GITHUB_OUTPUT
          echo "✅ Found Dev instance: $INSTANCE_ID"

      - name: Deploy Docker services via SSM
        run: |
          INSTANCE_ID="${{ steps.get-instance.outputs.instance_id }}"
          API_IMAGE="${{ steps.images.outputs.api_image }}"
          WORKER_IMAGE="${{ steps.images.outputs.worker_image }}"
          ENGINEER_NAME="${{ env.ENGINEER_NAME }}"
          
          echo "🚀 Deploying images:"
          echo "  API: $API_IMAGE"
          echo "  Worker: $WORKER_IMAGE"
          
          # Create a JSON file with the full SSM command structure (STAGING APPROACH)
          cat > /tmp/ssm-commands.json << 'SSEOF'
          {
            "InstanceIds": ["INSTANCE_ID_PLACEHOLDER"],
            "DocumentName": "AWS-RunShellScript",
            "TimeoutSeconds": 600,
            "Parameters": {
              "commands": [
                "#!/bin/bash",
                "set -e",
                "echo '🚀 Starting Docker deployment for dev-ENGINEER_NAME_PLACEHOLDER...'",
                "",
                "echo '📦 Fetching environment variables from SSM Parameter Store...'",
                "",
                "# Fetch parameters as JSON",
                "PARAMS_JSON=$(aws ssm get-parameters-by-path --path '/stitchsense/dev-ENGINEER_NAME_PLACEHOLDER' --recursive --with-decryption --output json)",
                "",
                "# Create .env file from SSM parameters",
                "ENV_FILE='/tmp/dev-ENGINEER_NAME_PLACEHOLDER.env'",
                "",
                "# Use jq to transform SSM parameters directly to .env format",
                "echo \"$PARAMS_JSON\" | jq -r '.Parameters[] | select(.Name | contains(\"deployment\") | not) | select(.Name | contains(\"ssh_private_key\") | not) | .Name + \"=\" + .Value' | while read -r line; do",
                "  # Extract key and value",
                "  param_name=$(echo \"$line\" | cut -d'=' -f1)",
                "  param_value=$(echo \"$line\" | cut -d'=' -f2-)",
                "  ",
                "  # Convert parameter name to env var format",
                "  env_key=$(echo \"$param_name\" | sed 's|^/stitchsense/dev-ENGINEER_NAME_PLACEHOLDER/||' | tr '/' '_' | tr '[:lower:]' '[:upper:]')",
                "  ",
                "  # Log the parameter",
                "  if [[ \"$env_key\" == *'PASSWORD'* || \"$env_key\" == *'SECRET'* || \"$env_key\" == *'KEY'* || \"$env_key\" == *'TOKEN'* ]]; then",
                "    echo \"  ✓ $env_key: [REDACTED]\"",
                "  else",
                "    echo \"  ✓ $env_key: ${param_value:0:50}...\"",
                "  fi",
                "done",
                "",
                "# Now create the actual .env file in one go using jq",
                "echo \"$PARAMS_JSON\" | jq -r '.Parameters[] | select(.Name | contains(\"deployment\") | not) | select(.Name | contains(\"ssh_private_key\") | not) | (.Name | sub(\"^/stitchsense/dev-ENGINEER_NAME_PLACEHOLDER/\"; \"\") | gsub(\"/\"; \"_\") | ascii_upcase) + \"=\" + .Value' > $ENV_FILE",
                "",
                "PARAM_COUNT=$(wc -l < $ENV_FILE)",
                "",
                "if [[ $PARAM_COUNT -eq 0 ]]; then",
                "  echo '⚠️  WARNING: No parameters found in /stitchsense/dev-ENGINEER_NAME_PLACEHOLDER'",
                "  echo 'Please ensure parameters are set in AWS Systems Manager Parameter Store'",
                "  exit 1",
                "fi",
                "",
                "echo ''",
                "echo \"✅ Loaded $PARAM_COUNT environment variables from SSM\"",
                "echo \"📄 Environment file created at: $ENV_FILE\"",
                "",
                "echo 'Logging in to ECR...'",
                "aws ecr get-login-password --region 'AWS_REGION_PLACEHOLDER' | docker login --username AWS --password-stdin 'ECR_REGISTRY_PLACEHOLDER'",
                "",
                "echo 'Pulling images...'",
                "docker pull 'API_IMAGE_PLACEHOLDER'",
                "docker pull 'WORKER_IMAGE_PLACEHOLDER'",
                "",
                "echo 'Stopping old containers...'",
                "docker stop stitchsense-api-dev-ENGINEER_NAME_PLACEHOLDER 2>/dev/null || true",
                "docker stop stitchsense-worker-dev-ENGINEER_NAME_PLACEHOLDER 2>/dev/null || true",
                "docker rm stitchsense-api-dev-ENGINEER_NAME_PLACEHOLDER 2>/dev/null || true",
                "docker rm stitchsense-worker-dev-ENGINEER_NAME_PLACEHOLDER 2>/dev/null || true",
                "",
                "echo 'Creating Docker network if not exists...'",
                "docker network create stitchsense-network 2>/dev/null || true",
                "",
                "echo 'Starting API container with environment file...'",
                "docker run -d \\",
                "  --name stitchsense-api-dev-ENGINEER_NAME_PLACEHOLDER \\",
                "  --network stitchsense-network \\",
                "  -p 8000:8000 \\",
                "  --env-file $ENV_FILE \\",
                "  --restart unless-stopped \\",
                "  'API_IMAGE_PLACEHOLDER'",
                "",
                "echo 'Waiting for API container to be ready...'",
                "sleep 10",
                "",
                "echo '🗄️  Running Alembic migrations...'",
                "echo 'Checking current migration status...'",
                "docker exec stitchsense-api-dev-ENGINEER_NAME_PLACEHOLDER alembic current || echo 'No current revision'",
                "",
                "echo 'Starting migration upgrade...'",
                "timeout 300 docker exec stitchsense-api-dev-ENGINEER_NAME_PLACEHOLDER alembic upgrade head",
                "MIGRATION_EXIT=$?",
                "",
                "if [ $MIGRATION_EXIT -eq 124 ]; then",
                "  echo '❌ Migration timed out after 5 minutes'",
                "  echo 'Checking migration logs...'",
                "  docker logs --tail 50 stitchsense-api-dev-ENGINEER_NAME_PLACEHOLDER",
                "  exit 1",
                "elif [ $MIGRATION_EXIT -ne 0 ]; then",
                "  echo '❌ Migration failed with exit code: $MIGRATION_EXIT'",
                "  echo 'Checking migration logs...'",
                "  docker logs --tail 50 stitchsense-api-dev-ENGINEER_NAME_PLACEHOLDER",
                "  exit 1",
                "fi",
                "",
                "echo '✅ Database migrations completed successfully'",
                "docker exec stitchsense-api-dev-ENGINEER_NAME_PLACEHOLDER alembic current",
                "",
                "echo 'Starting Worker container with environment file...'",
                "docker run -d \\",
                "  --name stitchsense-worker-dev-ENGINEER_NAME_PLACEHOLDER \\",
                "  --network stitchsense-network \\",
                "  --env-file $ENV_FILE \\",
                "  --restart unless-stopped \\",
                "  'WORKER_IMAGE_PLACEHOLDER' \\",
                "  celery -A src.core.celery_app worker --loglevel=info --concurrency=2 --queues=celery,default",
                "",
                "echo 'Waiting for services to stabilize...'",
                "sleep 15",
                "",
                "echo 'Container status:'",
                "docker ps --filter name=stitchsense",
                "",
                "echo 'API logs (last 20 lines):'",
                "docker logs --tail 20 stitchsense-api-dev-ENGINEER_NAME_PLACEHOLDER",
                "",
                "echo 'Worker logs (last 20 lines):'",
                "docker logs --tail 20 stitchsense-worker-dev-ENGINEER_NAME_PLACEHOLDER",
                "",
                "echo '✅ Deployment complete!'"
              ]
            }
          }
          SSEOF
          
          # Replace placeholders using sed
          sed -i "s|INSTANCE_ID_PLACEHOLDER|${INSTANCE_ID}|g" /tmp/ssm-commands.json
          sed -i "s|API_IMAGE_PLACEHOLDER|${API_IMAGE}|g" /tmp/ssm-commands.json
          sed -i "s|WORKER_IMAGE_PLACEHOLDER|${WORKER_IMAGE}|g" /tmp/ssm-commands.json
          sed -i "s|AWS_REGION_PLACEHOLDER|${{ env.AWS_REGION }}|g" /tmp/ssm-commands.json
          sed -i "s|ECR_REGISTRY_PLACEHOLDER|${{ env.ECR_REGISTRY }}|g" /tmp/ssm-commands.json
          sed -i "s|ENGINEER_NAME_PLACEHOLDER|${ENGINEER_NAME}|g" /tmp/ssm-commands.json
          
          # Send command using the JSON file
          COMMAND_ID=$(aws ssm send-command \
            --cli-input-json file:///tmp/ssm-commands.json \
            --output text \
            --query 'Command.CommandId')
          
          echo "📋 SSM Command ID: $COMMAND_ID"
          echo "⏳ Waiting for deployment to complete..."
          
          aws ssm wait command-executed \
            --command-id "$COMMAND_ID" \
            --instance-id "$INSTANCE_ID" \
            --region "${{ env.AWS_REGION }}" \
            --cli-read-timeout 300 \
            --cli-connect-timeout 300
          
          echo "📄 Command output:"
          aws ssm get-command-invocation \
            --command-id "$COMMAND_ID" \
            --instance-id "$INSTANCE_ID" \
            --region "${{ env.AWS_REGION }}" \
            --query 'StandardOutputContent' \
            --output text
          
          ERROR_OUTPUT=$(aws ssm get-command-invocation \
            --command-id "$COMMAND_ID" \
            --instance-id "$INSTANCE_ID" \
            --region "${{ env.AWS_REGION }}" \
            --query 'StandardErrorContent' \
            --output text)
          
          if [[ -n "$ERROR_OUTPUT" && "$ERROR_OUTPUT" != "None" ]]; then
            echo "⚠️  Errors detected:"
            echo "$ERROR_OUTPUT"
          fi
          
          echo "✅ Deployment command completed successfully"

  destroy-environment:
    if: github.event.inputs.action == 'destroy'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::514145637758:role/GitHubActions-StitchSense-DeployRole
          aws-region: ${{ env.AWS_REGION }}

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.9.8

      - name: Destroy infrastructure
        working-directory: terraform/envs/dev
        run: |
          terraform init
          terraform destroy -var="engineer_name=${ENGINEER_NAME}" -auto-approve

      - name: Delete workflow file
        run: |
          WORKFLOW_FILE=".github/workflows/deploy-dev-${ENGINEER_NAME}.yml"
          if [ -f "$WORKFLOW_FILE" ]; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git rm "$WORKFLOW_FILE"
            git commit -m "chore: remove workflow for dev-${ENGINEER_NAME} environment"
            git push
            echo "✅ Workflow file deleted"
          fi
EOF
    
    # Replace placeholders in the workflow file
    sed -i "s/ENGINEER_NAME_PLACEHOLDER/${ENGINEER_NAME}/g" "$WORKFLOW_FILE"
    sed -i "s|CURRENT_BRANCH_PLACEHOLDER|${CURRENT_BRANCH}|g" "$WORKFLOW_FILE"
    
    print_success "GitHub workflow created: $WORKFLOW_FILE"
    print_info "Configured to trigger on branch: $CURRENT_BRANCH"
    print_info "Uses STAGING APPROACH (JSON file + heredoc) - same as staging workflow!"
    echo ""
}

# Display next steps
display_next_steps() {
    local workflow_generated=$1
    
    echo ""
    print_success "Prerequisites setup complete! 🎉"
    echo ""
    
    print_info "Resources created:"
    echo "   ✓ EC2 Key Pair: stitchsense-${ENGINEER_NAME}-key"
    echo "   ✓ SSH Private Key (SSM): /stitchsense/dev-${ENGINEER_NAME}/ec2/ssh_private_key"
    echo "   ✓ RDS Password (SSM): /stitchsense/dev-${ENGINEER_NAME}/rds/password"
    echo "   ✓ RDS Credentials (Secrets Manager): stitchsense/dev-${ENGINEER_NAME}/rds"
    if [ "$workflow_generated" = true ]; then
        echo "   ✓ GitHub Workflow: .github/workflows/deploy-dev-${ENGINEER_NAME}.yml"
    fi
    echo ""
    
    print_info "Next steps:"
    echo "   1. Deploy infrastructure with Terraform:"
    echo "      cd terraform/envs/dev"
    if [ "$USE_PROFILE" = true ]; then
        echo "      export AWS_PROFILE=$AWS_PROFILE"
    fi
    echo "      terraform init"
    echo "      terraform apply -var=\"engineer_name=${ENGINEER_NAME}\""
    echo ""
    
    if [ "$workflow_generated" = true ]; then
        echo "   2. Commit and push the GitHub workflow:"
        echo "      git add .github/workflows/deploy-dev-${ENGINEER_NAME}.yml"
        echo "      git commit -m 'Add deployment workflow for ${ENGINEER_NAME}'"
        echo "      git push"
        echo ""
        echo "   3. The workflow will automatically deploy on push to the configured branch"
        echo ""
    fi
    
    echo "   To clean up these prerequisites later:"
    echo "      ./cleanup-secrets.sh ${ENGINEER_NAME}"
    echo ""
    
    print_info "Workflow Details:"
    echo "   • Uses the SAME approach as the staging workflow"
    echo "   • JSON file + heredoc (no complex escaping needed)"
    echo "   • Simple sed replacements for placeholders"
    echo "   • Easy to debug and maintain"
    echo ""
}

# Main execution
main() {
    print_header
    
    echo "This script creates the prerequisites needed for your dev environment:"
    echo "  • EC2 key pair (stored securely in AWS SSM)"
    echo "  • RDS password (stored in AWS SSM)"
    echo "  • RDS credentials secret (stored in AWS Secrets Manager)"
    echo "  • GitHub workflow (optional, using STAGING APPROACH)"
    echo ""
    echo "You will run Terraform manually after this completes."
    echo ""
    
    read -p "Press Enter to continue or Ctrl+C to cancel..."
    echo ""
    
    check_prerequisites
    get_engineer_name "$1"
    create_key_pair_in_ssm
    create_ssm_parameter
    create_secrets_manager_secret
    
    if ! verify_setup; then
        print_error "Setup verification failed. Please check the errors above."
        exit 1
    fi
    
    # Ask if user wants to generate GitHub workflow
    WORKFLOW_GENERATED=false
    read -p "Do you want to generate the GitHub workflow file? (y/n): " GEN_WORKFLOW
    if [[ "$GEN_WORKFLOW" == "y" ]]; then
        if generate_github_workflow; then
            WORKFLOW_GENERATED=true
        fi
    fi
    
    display_next_steps $WORKFLOW_GENERATED
}

# Run main function with optional engineer name argument
main "$@"