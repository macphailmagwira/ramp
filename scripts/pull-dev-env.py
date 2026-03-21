#!/usr/bin/env python3
"""
Fetch .env for the dev environment from AWS SSM Parameter Store.
Usage: python scripts/sync-envs-dev.py <app-name>
Supported apps: api-main, worker-main
"""

import boto3
import os
import sys

# Supported apps
SUPPORTED_APPS = ["api-main", "worker-main"]

# AWS SSM client
ssm = boto3.client("ssm")

# SSM path prefix - same for all apps
SSM_PATH_PREFIX = "/stitchsense/dev/"

# Output directory - relative to monorepo root
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apps", "api-main")

def fetch_parameters(path_prefix):
    """Fetch all parameters from SSM under the given path prefix."""
    params = {}
    next_token = None
    while True:
        kwargs = {
            "Path": path_prefix,
            "Recursive": True,
            "WithDecryption": True,
            "MaxResults": 10
        }
        if next_token:
            kwargs["NextToken"] = next_token

        response = ssm.get_parameters_by_path(**kwargs)
        for p in response.get("Parameters", []):
            # Take the last segment of the name as the key
            key = p["Name"].split("/")[-1]
            params[key] = p["Value"]

        next_token = response.get("NextToken")
        if not next_token:
            break

    return params

def write_env_file(params, file_path):
    """Write parameters to .env file."""
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, "w") as f:
        for k, v in params.items():
            f.write(f"{k}={v}\n")
    print(f"✓ .env file written to {file_path}")

def main():
    # Check if app name is provided
    if len(sys.argv) < 2:
        print("Error: App name required")
        print(f"Usage: {sys.argv[0]} <app-name>")
        print(f"Supported apps: {', '.join(SUPPORTED_APPS)}")
        sys.exit(1)
    
    app_name = sys.argv[1]
    
    # Validate app name
    if app_name not in SUPPORTED_APPS:
        print(f"Error: Unsupported app '{app_name}'")
        print(f"Supported apps: {', '.join(SUPPORTED_APPS)}")
        sys.exit(1)
    
    print(f"Fetching parameters for {app_name} from {SSM_PATH_PREFIX}...")
    
    # Fetch parameters from the shared dev path
    params = fetch_parameters(SSM_PATH_PREFIX)
    if not params:
        print(f"Warning: No parameters found in SSM at {SSM_PATH_PREFIX}")
        return
    
    print(f"Found {len(params)} parameters")
    
    # Build output file path - always .env in apps/api-main/
    output_file = os.path.join(OUTPUT_DIR, ".env")
    
    # Write .env file
    write_env_file(params, output_file)
    print(f"Full path: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    main()