#!/bin/bash

# ==================================================
# STITCHSENSE DEV ENVIRONMENT CLEANUP SCRIPT
# ==================================================
# Removes EC2 key pair, RDS password SSM parameter,
# RDS Secrets Manager secret, and GitHub workflow file
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

# Build AWS command with or without profile
aws_cmd() {
    if [ "$USE_PROFILE" = true ]; then
        aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
    else
        aws --region "$AWS_REGION" "$@"
    fi
}

# Check AWS credentials
check_credentials() {
    if aws sts get-caller-identity --profile "$AWS_PROFILE" &> /dev/null; then
        USE_PROFILE=true
    elif aws sts get-caller-identity &> /dev/null; then
        USE_PROFILE=false
    else
        print_error "AWS credentials not configured"
        exit 1
    fi
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

# Get engineer name
if [ -z "$1" ]; then
    echo "Usage: $0 <engineer_name>"
    exit 1
fi

ENGINEER_NAME="$1"

echo ""
print_info "Cleaning up resources for engineer: $ENGINEER_NAME"
echo ""

check_credentials

# Delete RDS password from SSM
print_info "Deleting RDS password from SSM..."
SSM_PARAM="/stitchsense/dev-${ENGINEER_NAME}/rds/password"

if aws_cmd ssm get-parameter --name "$SSM_PARAM" &> /dev/null; then
    aws_cmd ssm delete-parameter --name "$SSM_PARAM" > /dev/null 2>&1
    print_success "Deleted SSM parameter: $SSM_PARAM"
else
    print_warning "SSM parameter not found: $SSM_PARAM"
fi

echo ""

# Delete EC2 SSH private key from SSM
print_info "Deleting EC2 SSH private key from SSM..."
SSH_KEY_PARAM="/stitchsense/dev-${ENGINEER_NAME}/ec2/ssh_private_key"

if aws_cmd ssm get-parameter --name "$SSH_KEY_PARAM" &> /dev/null; then
    aws_cmd ssm delete-parameter --name "$SSH_KEY_PARAM" > /dev/null 2>&1
    print_success "Deleted SSM parameter: $SSH_KEY_PARAM"
else
    print_warning "SSM parameter not found: $SSH_KEY_PARAM"
fi

echo ""

# Delete Secrets Manager Secret
print_info "Deleting RDS secret from Secrets Manager..."
SECRET_NAME="stitchsense/dev-${ENGINEER_NAME}/rds"

if aws_cmd secretsmanager describe-secret --secret-id "$SECRET_NAME" &> /dev/null; then
    aws_cmd secretsmanager delete-secret \
        --secret-id "$SECRET_NAME" \
        --force-delete-without-recovery > /dev/null 2>&1
    print_success "Deleted Secrets Manager secret: $SECRET_NAME"
else
    print_warning "Secret not found: $SECRET_NAME"
fi

echo ""

# Delete EC2 Key Pair
print_info "Deleting EC2 key pair..."
KEY_NAME="stitchsense-${ENGINEER_NAME}-key"

if aws_cmd ec2 describe-key-pairs --key-names "$KEY_NAME" &> /dev/null; then
    aws_cmd ec2 delete-key-pair --key-name "$KEY_NAME" > /dev/null 2>&1
    print_success "Deleted EC2 key pair: $KEY_NAME"
else
    print_warning "Key pair not found: $KEY_NAME"
fi

echo ""

# Delete GitHub Workflow File
print_info "Deleting GitHub workflow file..."
REPO_ROOT="$(find_repo_root)"
WORKFLOW_FILE="${REPO_ROOT}/.github/workflows/deploy-dev-${ENGINEER_NAME}.yml"

print_info "Repository root: $REPO_ROOT"
print_info "Looking for workflow file: $WORKFLOW_FILE"

# Check if .github/workflows directory exists
if [ ! -d "${REPO_ROOT}/.github/workflows" ]; then
    print_error ".github/workflows directory not found at: ${REPO_ROOT}/.github/workflows"
    print_info "Please verify the repository structure"
else
    print_success "Found .github/workflows directory"
    
    # List matching workflow files for debugging
    MATCHING_FILES=$(find "${REPO_ROOT}/.github/workflows" -name "deploy-dev-${ENGINEER_NAME}.yml" 2>/dev/null || true)
    if [ -n "$MATCHING_FILES" ]; then
        print_info "Found matching workflow file(s):"
        echo "$MATCHING_FILES"
    fi
    
    if [ -f "$WORKFLOW_FILE" ]; then
        rm -f "$WORKFLOW_FILE"
        if [ ! -f "$WORKFLOW_FILE" ]; then
            print_success "Deleted workflow file: deploy-dev-${ENGINEER_NAME}.yml"
            
            # Check if file is tracked by git and stage the deletion
            if git -C "$REPO_ROOT" ls-files --error-unmatch ".github/workflows/deploy-dev-${ENGINEER_NAME}.yml" &> /dev/null; then
                git -C "$REPO_ROOT" rm ".github/workflows/deploy-dev-${ENGINEER_NAME}.yml" 2>/dev/null || true
                print_success "github workflow file deleted"
            fi
        else
            print_error "Failed to delete workflow file"
        fi
    else
        print_warning "Workflow file not found: deploy-dev-${ENGINEER_NAME}.yml"
        
        # Show what files do exist
        print_info "Available workflow files:"
        ls -la "${REPO_ROOT}/.github/workflows/" 2>/dev/null | grep "deploy-dev" || print_info "No deploy-dev-*.yml files found"
    fi
fi

echo ""
print_success "Cleanup complete for engineer: $ENGINEER_NAME"
echo ""
print_info "Next steps:"
echo "  1. Verify deletion: git status"
echo "  2. Commit the changes: git commit -m 'Remove dev environment for ${ENGINEER_NAME}'"
echo "  3. Push to repository: git push"
echo ""