#!/bin/bash
set -e

echo "Checking required tools..."

# Docker
docker --version || { echo "Docker not found"; exit 1; }
docker info > /dev/null 2>&1 || { echo "Docker daemon not running"; exit 1; }

# Node.js via nvm
source ~/.nvm/nvm.sh
nvm use || { echo "Node version not set via .nvmrc"; exit 1; }

# Python
python3 --version | grep -E "3\.(11|12)" || { echo "Python 3.11+ required"; exit 1; }

# AWS CLI
aws --version || { echo "AWS CLI not found"; exit 1; }

echo "All tools verified!"
