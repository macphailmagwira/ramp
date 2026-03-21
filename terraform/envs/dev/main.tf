########################################
# DEV ENVIRONMENT – Provider Configuration
########################################
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = "ap-southeast-1"
  # Profile removed - will use environment variables or default AWS credentials
}

########################################
# VARIABLES – Prompted at terraform apply
########################################

variable "engineer_name" {
  description = "Engineer name for resource naming (lowercase, no spaces, e.g., 'john', 'sarah')"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]+$", var.engineer_name))
    error_message = "Engineer name must be lowercase alphanumeric only (no spaces or special characters)."
  }
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "instance_type" {
  description = "EC2 instance type (t3.micro for minimal costs, t3.small for standard, t3.medium for more resources)"
  type        = string
  default     = "t3.small"

  validation {
    condition     = contains(["t3.micro", "t3.small", "t3.medium", "t3.large"], var.instance_type)
    error_message = "Instance type must be one of: t3.micro, t3.small, t3.medium, t3.large."
  }
}

variable "enable_multi_az" {
  description = "Enable multi-AZ for RDS (recommended for prod-like testing, costs more)"
  type        = bool
  default     = false
}

########################################
# LOCAL VARIABLES
########################################

locals {
  env_name = "dev-${var.engineer_name}"
  common_tags = {
    Environment = "dev"
    Engineer    = var.engineer_name
    ManagedBy   = "terraform"
    Project     = "StitchSense"
  }
}

########################################
# OUTPUTS
########################################

output "environment_info" {
  value = {
    engineer           = var.engineer_name
    api_endpoint       = "http://${module.alb.alb_dns_name}"
    appsync_endpoint   = module.appsync_api.graphql_url
    rds_proxy_endpoint = aws_db_proxy.main.endpoint
    redis_endpoint     = aws_elasticache_cluster.redis.cache_nodes[0].address
    ec2_instance_id    = module.ec2.instance_id
  }
  description = "Dev environment information"
}

output "alb_dns_name" {
  value       = module.alb.alb_dns_name
  description = "ALB DNS name"
}

output "fastapi_endpoint" {
  value       = "http://${module.alb.alb_dns_name}"
  description = "FastAPI endpoint URL"
}

output "nat_gateway_public_ips" {
  value       = module.vpc.nat_gateway_public_ips
  description = "Public IPs of NAT Gateways"
}

########################################
# SSM PARAMETERS FOR STATIC CONFIG
########################################

resource "aws_ssm_parameter" "cognito_region" {
  name        = "/stitchsense/${local.env_name}/COGNITO_REGION"
  description = "Cognito region for ${var.engineer_name}"
  type        = "String"
  value       = "ap-southeast-1"

  tags = local.common_tags
}

resource "aws_ssm_parameter" "environment" {
  name        = "/stitchsense/${local.env_name}/ENVIRONMENT"
  description = "Environment name for ${var.engineer_name}"
  type        = "String"
  value       = "STAGING"

  tags = local.common_tags
}

resource "aws_ssm_parameter" "api_main_port" {
  name        = "/stitchsense/${local.env_name}/API_MAIN_PORT"
  description = "API main port for ${var.engineer_name}"
  type        = "String"
  value       = "8000"

  tags = local.common_tags
}

########################################
# VPC CONFIGURATION
########################################

module "vpc" {
  source = "../../modules/vpc"

  vpc_name             = "stitchsense-${local.env_name}-vpc"
  cidr_block           = "10.${10 + (sum([for c in split("", var.engineer_name) : index(split("", "abcdefghijklmnopqrstuvwxyz0123456789"), lower(c))]) % 240)}.0.0/16"
  enable_dns_hostnames = true

  public_subnets = [
    { az = "ap-southeast-1a", cidr = "10.${10 + (sum([for c in split("", var.engineer_name) : index(split("", "abcdefghijklmnopqrstuvwxyz0123456789"), lower(c))]) % 240)}.1.0/24" },
    { az = "ap-southeast-1b", cidr = "10.${10 + (sum([for c in split("", var.engineer_name) : index(split("", "abcdefghijklmnopqrstuvwxyz0123456789"), lower(c))]) % 240)}.4.0/24" }
  ]

  private_subnets = [
    { az = "ap-southeast-1a", cidr = "10.${10 + (sum([for c in split("", var.engineer_name) : index(split("", "abcdefghijklmnopqrstuvwxyz0123456789"), lower(c))]) % 240)}.2.0/24" },
    { az = "ap-southeast-1b", cidr = "10.${10 + (sum([for c in split("", var.engineer_name) : index(split("", "abcdefghijklmnopqrstuvwxyz0123456789"), lower(c))]) % 240)}.3.0/24" }
  ]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = local.common_tags
}

########################################
# SECURITY GROUPS
########################################

# Web tier security group (ALB)
module "security_group_web" {
  source      = "../../modules/security_groups"
  name        = "stitchsense-${local.env_name}-web-sg"
  description = "Security group for web tier (ALB)"
  vpc_id      = module.vpc.vpc_id

  ingress = [
    {
      from_port       = 80
      to_port         = 80
      protocol        = "tcp"
      security_groups = []
      cidr_blocks     = ["0.0.0.0/0"]
    },
    {
      from_port       = 8000
      to_port         = 8000
      protocol        = "tcp"
      security_groups = []
      cidr_blocks     = ["0.0.0.0/0"]
    }
  ]

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-web-sg"
  })
}

# App tier security group (EC2)
module "security_group_app" {
  source      = "../../modules/security_groups"
  name        = "stitchsense-${local.env_name}-app-sg"
  description = "Security group for app tier (EC2)"
  vpc_id      = module.vpc.vpc_id

  ingress = [
    {
      from_port       = 8000
      to_port         = 8000
      protocol        = "tcp"
      security_groups = [module.security_group_web.security_group_id]
      cidr_blocks     = []
    }
  ]

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-app-sg"
  })
}

# Database tier security group
module "security_group_db" {
  source      = "../../modules/security_groups"
  name        = "stitchsense-${local.env_name}-db-sg"
  description = "Security group for database tier"
  vpc_id      = module.vpc.vpc_id

  ingress = [
    {
      from_port       = 5432
      to_port         = 5432
      protocol        = "tcp"
      security_groups = [
        module.security_group_app.security_group_id,
        aws_security_group.rds_proxy.id
      ]
      cidr_blocks = []
    }
  ]

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-db-sg"
  })
}

# SSM Endpoints security group
resource "aws_security_group" "ssm_endpoints" {
  name        = "stitchsense-${local.env_name}-ssm-endpoints-sg"
  description = "Allow HTTPS from app instances to SSM VPC endpoints"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [module.security_group_app.security_group_id]
    description     = "Allow SSM traffic from app instances"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-ssm-endpoints-sg"
  })
}

# Redis security group
resource "aws_security_group" "redis" {
  name        = "stitchsense-${local.env_name}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.security_group_app.security_group_id]
    description     = "Allow Redis from app tier"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-redis-sg"
  })
}

# RDS Proxy security group
resource "aws_security_group" "rds_proxy" {
  name        = "stitchsense-${local.env_name}-rds-proxy-sg"
  description = "Security group for RDS Proxy"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.security_group_app.security_group_id]
    description     = "Allow PostgreSQL from app tier"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-rds-proxy-sg"
  })
}

########################################
# VPC ENDPOINTS FOR SSM
########################################

resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = module.vpc.vpc_id
  vpc_endpoint_type   = "Interface"
  service_name        = "com.amazonaws.ap-southeast-1.ssm"
  subnet_ids          = module.vpc.private_subnet_ids
  security_group_ids  = [aws_security_group.ssm_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-ssm-endpoint"
  })
}

resource "aws_vpc_endpoint" "ssmmessages" {
  vpc_id              = module.vpc.vpc_id
  vpc_endpoint_type   = "Interface"
  service_name        = "com.amazonaws.ap-southeast-1.ssmmessages"
  subnet_ids          = module.vpc.private_subnet_ids
  security_group_ids  = [aws_security_group.ssm_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-ssmmessages-endpoint"
  })
}

resource "aws_vpc_endpoint" "ec2messages" {
  vpc_id              = module.vpc.vpc_id
  vpc_endpoint_type   = "Interface"
  service_name        = "com.amazonaws.ap-southeast-1.ec2messages"
  subnet_ids          = module.vpc.private_subnet_ids
  security_group_ids  = [aws_security_group.ssm_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-ec2messages-endpoint"
  })
}

########################################
# ELASTICACHE REDIS
########################################

resource "aws_elasticache_subnet_group" "redis" {
  name        = "stitchsense-${local.env_name}-redis-subnet-group"
  subnet_ids  = module.vpc.private_subnet_ids
  description = "Subnet group for ${var.engineer_name}'s ElastiCache Redis"

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-redis-subnet-group"
  })
}

resource "aws_ssm_parameter" "redis_host" {
  name        = "/stitchsense/${local.env_name}/REDIS_HOST"
  description = "Redis host for ${var.engineer_name}"
  type        = "String"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address

  tags = local.common_tags
}

resource "aws_ssm_parameter" "redis_port" {
  name        = "/stitchsense/${local.env_name}/REDIS_PORT"
  description = "Redis port for ${var.engineer_name}"
  type        = "String"
  value       = tostring(aws_elasticache_cluster.redis.port)

  tags = local.common_tags
}

resource "aws_ssm_parameter" "redis_url" {
  name        = "/stitchsense/${local.env_name}/REDIS_URL"
  description = "Redis URL for ${var.engineer_name}"
  type        = "String"
  value       = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.port}"

  tags = local.common_tags
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "stitchsense-${var.engineer_name}-redis"
  engine               = "redis"
  engine_version       = "6.x"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis6.x"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  az_mode            = "single-az"
  maintenance_window = "sun:05:00-sun:06:00"

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-redis"
    Role = "celery-redbeat"
  })
}

# SSM parameters for Redis
resource "aws_ssm_parameter" "redis_endpoint" {
  name        = "/stitchsense/${local.env_name}/redis_endpoint"
  description = "Redis endpoint for ${var.engineer_name}"
  type        = "String"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address

  tags = local.common_tags
}


resource "aws_ssm_parameter" "redis_redbeat_url" {
  name        = "/stitchsense/${local.env_name}/redis_redbeat_url"
  description = "Redis URL for RedBeat scheduler"
  type        = "String"
  value       = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.port}/1"

  tags = local.common_tags
}

########################################
# SQS QUEUES FOR CELERY
########################################

resource "aws_sqs_queue" "celery_default" {
  name                       = "stitchsense-${local.env_name}-celery-default"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 1209600
  receive_wait_time_seconds  = 10
  visibility_timeout_seconds = 3600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.celery_default_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(local.common_tags, {
    Name    = "stitchsense-${local.env_name}-celery-default"
    Purpose = "celery-broker"
  })
}

resource "aws_sqs_queue" "celery_default_dlq" {
  name                      = "stitchsense-${local.env_name}-celery-default-dlq"
  message_retention_seconds = 1209600

  tags = merge(local.common_tags, {
    Name    = "stitchsense-${local.env_name}-celery-default-dlq"
    Purpose = "celery-dlq"
  })
}

resource "aws_sqs_queue" "celery_priority" {
  name                       = "stitchsense-${local.env_name}-celery-priority"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 1209600
  receive_wait_time_seconds  = 10
  visibility_timeout_seconds = 1800

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.celery_priority_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(local.common_tags, {
    Name    = "stitchsense-${local.env_name}-celery-priority"
    Purpose = "celery-broker-priority"
  })
}

resource "aws_sqs_queue" "celery_priority_dlq" {
  name                      = "stitchsense-${local.env_name}-celery-priority-dlq"
  message_retention_seconds = 1209600

  tags = merge(local.common_tags, {
    Name    = "stitchsense-${local.env_name}-celery-priority-dlq"
    Purpose = "celery-dlq"
  })
}

# SSM parameters for SQS
resource "aws_ssm_parameter" "sqs_default_queue_url" {
  name        = "/stitchsense/${local.env_name}/sqs/default_queue_url"
  description = "SQS default queue URL"
  type        = "String"
  value       = aws_sqs_queue.celery_default.url

  tags = local.common_tags
}

resource "aws_ssm_parameter" "sqs_priority_queue_url" {
  name        = "/stitchsense/${local.env_name}/sqs/priority_queue_url"
  description = "SQS priority queue URL"
  type        = "String"
  value       = aws_sqs_queue.celery_priority.url

  tags = local.common_tags
}

########################################
# IAM ROLES AND POLICIES
########################################




module "iam" {
  source = "../../modules/iam"
  env    = local.env_name
}

resource "aws_iam_role_policy" "ec2_cognito_user_management" {
  name = "stitchsense-${local.env_name}-ec2-cognito-policy"
  role = module.iam.role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CognitoUserManagement"
        Effect = "Allow"
        Action = [
          "cognito-idp:AdminCreateUser",
          "cognito-idp:AdminSetUserPassword",
          "cognito-idp:AdminUpdateUserAttributes",
          "cognito-idp:AdminDeleteUser",
          "cognito-idp:AdminGetUser",
          "cognito-idp:AdminEnableUser",
          "cognito-idp:AdminDisableUser",
          "cognito-idp:ListUsers",
          "cognito-idp:AdminAddUserToGroup",
          "cognito-idp:AdminRemoveUserFromGroup"
        ]
        Resource = module.cognito.user_pool_arn
      }
    ]
  })
}

# SQS access policy
resource "aws_iam_role_policy" "ec2_sqs_access" {
  name = "stitchsense-${local.env_name}-ec2-sqs-policy"
  role = module.iam.role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ChangeMessageVisibility",
          "sqs:PurgeQueue"
        ]
        Resource = [
          aws_sqs_queue.celery_default.arn,
          aws_sqs_queue.celery_default_dlq.arn,
          aws_sqs_queue.celery_priority.arn,
          aws_sqs_queue.celery_priority_dlq.arn
        ]
      }
    ]
  })
}

# SSM Parameter Store access policy
resource "aws_iam_role_policy" "ec2_ssm_parameter_store_access" {
  name = "stitchsense-${local.env_name}-ec2-ssm-parameter-store-policy"
  role = module.iam.role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath",
          "ssm:DescribeParameters"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.ap-southeast-1.amazonaws.com"
          }
        }
      }
    ]
  })
}

########################################
# EC2 INSTANCE
########################################

module "ec2" {
  source               = "../../modules/ec2"
  ami                  = "ami-0062e0576ebcaa2a9"
  instance_type        = var.instance_type
  key_name             = "stitchsense-${var.engineer_name}-key"
  availability_zone    = "ap-southeast-1a"
  iam_instance_profile = module.iam.profile

  user_data = templatefile("../../scripts/ec2_startup_script_dev.sh.tmpl", {
    IMAGE_TAG    = var.image_tag
    ENVIRONMENT  = local.env_name
    AWS_REGION   = var.aws_region
    ECR_REGISTRY = module.ecr.registry
  })

  root_volume_size      = 20
  root_volume_type      = "gp3"
  delete_on_termination = true

  security_group_ids = [module.security_group_app.security_group_id]
  subnet_id          = element(module.vpc.public_subnet_ids, 0)

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-ec2"
  })
}

########################################
# APPLICATION LOAD BALANCER
########################################

module "alb" {
  source = "../../modules/alb"

  name            = "stitchsense-${local.env_name}-alb"
  vpc_id          = module.vpc.vpc_id
  subnets         = module.vpc.public_subnet_ids
  security_groups = [module.security_group_web.security_group_id]
  internal        = false

  target_groups = {
    api = {
      port              = 8000
      protocol          = "HTTP"
      health_check_path = "/api/v1/health"
    }
  }

  cert_arn    = null
  allow_http  = true
  environment = local.env_name
}

resource "aws_lb_target_group_attachment" "ec2" {
  target_group_arn = module.alb.target_group_arns["api"]
  target_id        = module.ec2.instance_id
  port             = 8000
}

########################################
# RDS DATABASE
########################################

# Reference or create RDS password - UPDATED PATH
data "aws_ssm_parameter" "rds_password" {
  name = "/stitchsense/dev-${var.engineer_name}/rds/password"
}

########################################
# SSM PARAMETERS FOR RDS
########################################

resource "aws_ssm_parameter" "rds_database_url" {
  name        = "/stitchsense/${local.env_name}/DATABASE_URL"
  description = "RDS Database URL for ${var.engineer_name}"
  type        = "SecureString"
  value       = "postgresql+asyncpg://stitchsense_${var.engineer_name}:${data.aws_ssm_parameter.rds_password.value}@${replace(module.rds.db_instance_endpoint, ":5432", "")}:5432/stitchsense_dev_${var.engineer_name}?ssl=require"

  tags = local.common_tags

  depends_on = [module.rds]
}

resource "aws_ssm_parameter" "rds_db_name" {
  name        = "/stitchsense/${local.env_name}/DB_NAME"
  description = "RDS Database Name for ${var.engineer_name}"
  type        = "String"
  value       = "stitchsense_dev_${var.engineer_name}"

  tags = local.common_tags
}

resource "aws_ssm_parameter" "rds_db_user" {
  name        = "/stitchsense/${local.env_name}/DB_USER"
  description = "RDS Database User for ${var.engineer_name}"
  type        = "String"
  value       = "stitchsense_${var.engineer_name}"

  tags = local.common_tags
}

resource "aws_ssm_parameter" "rds_db_password" {
  name        = "/stitchsense/${local.env_name}/DB_PASSWORD"
  description = "RDS Database Password for ${var.engineer_name}"
  type        = "SecureString"
  value       = data.aws_ssm_parameter.rds_password.value

  tags = local.common_tags
}

resource "aws_ssm_parameter" "rds_db_host" {
  name        = "/stitchsense/${local.env_name}/DB_HOST"
  description = "RDS Database Host (direct connection) for ${var.engineer_name}"
  type        = "String"
  value       = replace(module.rds.db_instance_endpoint, ":5432", "")

  tags = local.common_tags

  depends_on = [module.rds]
}

resource "aws_ssm_parameter" "rds_db_port" {
  name        = "/stitchsense/${local.env_name}/DB_PORT"
  description = "RDS Database Port for ${var.engineer_name}"
  type        = "String"
  value       = "5432"

  tags = local.common_tags
}

########################################
# UPDATE SECRETS MANAGER WITH RDS ENDPOINT
########################################

resource "null_resource" "update_secrets_manager" {
  depends_on = [module.rds]

  triggers = {
    # Trigger on RDS endpoint change
    rds_endpoint = module.rds.db_instance_endpoint
    # Also trigger if password changes
    rds_password = data.aws_ssm_parameter.rds_password.value
  }

  provisioner "local-exec" {
    command = <<-EOT
      # Get the RDS endpoint without port
      RDS_HOST=$(echo "${module.rds.db_instance_endpoint}" | sed 's/:5432//')

      # Update Secrets Manager with correct credentials
      aws secretsmanager update-secret \
        --secret-id stitchsense/dev-${var.engineer_name}/rds \
        --secret-string "{
          \"username\": \"stitchsense_${var.engineer_name}\",
          \"password\": \"${data.aws_ssm_parameter.rds_password.value}\",
          \"engine\": \"postgres\",
          \"host\": \"$RDS_HOST\",
          \"port\": 5432,
          \"dbname\": \"stitchsense_dev_${var.engineer_name}\"
        }" \
        --region ${var.aws_region}

      echo "✅ Secrets Manager updated with RDS endpoint: $RDS_HOST"
    EOT
  }
}


module "rds" {
  source = "../../modules/rds"

  db_identifier                       = "stitchsense-${var.engineer_name}-db"
  allocated_storage                   = 20
  instance_class                      = "db.t3.micro"
  engine                              = "postgres"
  backup_window                       = "03:00-04:00"
  backup_retention_period             = 1
  maintenance_window                  = "sun:04:00-sun:05:00"
  multi_az                            = var.enable_multi_az
  engine_version                      = "15.12"
  auto_minor_version_upgrade          = true
  license_model                       = "postgresql-license"
  publicly_accessible                 = false
  storage_type                        = "gp2"
  port                                = 5432
  storage_encrypted                   = true
  kms_key_id                          = "arn:aws:kms:ap-southeast-1:514145637758:key/345ecb8c-7bae-412f-91df-d7a143e953dc"
  copy_tags_to_snapshot               = false
  monitoring_interval                 = 0
  iam_database_authentication_enabled = false
  subnet_group_name                   = "stitchsense-${local.env_name}-db-subnet"
  subnet_ids                          = module.vpc.public_subnet_ids
  vpc_security_group_ids              = [module.security_group_db.security_group_id]
  db_name                             = "stitchsense_dev_${var.engineer_name}"
  username                            = "stitchsense_${var.engineer_name}"
  password                            = data.aws_ssm_parameter.rds_password.value
  deletion_protection                 = false
  skip_final_snapshot                 = true
}

########################################
# RDS PROXY
########################################

# UPDATED PATH
data "aws_secretsmanager_secret" "rds_master" {
  name = "stitchsense/dev-${var.engineer_name}/rds"
}

data "aws_secretsmanager_secret_version" "rds_master" {
  secret_id = data.aws_secretsmanager_secret.rds_master.id
}

resource "aws_iam_role" "rds_proxy" {
  name = "stitchsense-${local.env_name}-rds-proxy-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-rds-proxy-role"
  })
}

resource "aws_iam_role_policy" "rds_proxy_secrets" {
  name = "rds-proxy-secrets-policy"
  role = aws_iam_role.rds_proxy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = data.aws_secretsmanager_secret.rds_master.arn
      }
    ]
  })
}

resource "aws_db_proxy" "main" {
  name          = "stitchsense-${var.engineer_name}-proxy"
  engine_family = "POSTGRESQL"

  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = data.aws_secretsmanager_secret.rds_master.arn
  }

  role_arn               = aws_iam_role.rds_proxy.arn
  vpc_subnet_ids         = module.vpc.private_subnet_ids
  vpc_security_group_ids = [aws_security_group.rds_proxy.id]

  require_tls   = false
  debug_logging = false

  tags = merge(local.common_tags, {
    Name = "stitchsense-${local.env_name}-rds-proxy"
  })
}

resource "aws_db_proxy_default_target_group" "main" {
  db_proxy_name = aws_db_proxy.main.name

  connection_pool_config {
    max_connections_percent      = 100
    max_idle_connections_percent = 50
    connection_borrow_timeout    = 120
  }
}

resource "aws_db_proxy_target" "main" {
  db_proxy_name          = aws_db_proxy.main.name
  target_group_name      = aws_db_proxy_default_target_group.main.name
  db_instance_identifier = module.rds.db_instance_id
}

resource "aws_ssm_parameter" "rds_proxy_endpoint" {
  name        = "/stitchsense/${local.env_name}/rds_proxy_endpoint"
  description = "RDS Proxy endpoint"
  type        = "String"
  value       = aws_db_proxy.main.endpoint

  tags = local.common_tags
}


########################################
# ECR REPOSITORIES
########################################

module "ecr" {
  source = "../../modules/ecr"
  region = var.aws_region

  repositories = [
    "stitchsense-${local.env_name}-api-main",
    "stitchsense-${local.env_name}-worker-main"
  ]
}

########################################
# COGNITO USER POOL
########################################

module "cognito" {
  source          = "../../modules/cognito"
  user_pool_name  = "stitchsense-${local.env_name}-user-pool"
  app_client_name = "stitchsense-${local.env_name}-app-client"
  generate_secret = true
  app_url         = "https://app-dev.stitchsense.ai/"

  user_pool_groups = [
    {
      name        = "SuperAdmin"
      description = "Super Administrator"
      precedence  = 1
    },
    {
      name        = "Admin"
      description = "Administrator"
      precedence  = 2
    },
    {
      name        = "Developer"
      description = "Developer"
      precedence  = 3
    }
  ]

  tags = local.common_tags
}


resource "aws_ssm_parameter" "cognito_user_pool_id" {
  name        = "/stitchsense/${local.env_name}/COGNITO_USER_POOL_ID"
  description = "Cognito User Pool ID for ${var.engineer_name}"
  type        = "String"
  value       = module.cognito.user_pool_id

  tags = local.common_tags
}

resource "aws_ssm_parameter" "cognito_user_pool_client_id" {
  name        = "/stitchsense/${local.env_name}/COGNITO_APP_CLIENT_ID"
  description = "Cognito User Pool Client ID for ${var.engineer_name}"
  type        = "String"
  value       = module.cognito.user_pool_client_id

  tags = local.common_tags
}

########################################
# APPSYNC API
########################################

resource "aws_cloudwatch_log_group" "appsync" {
  name              = "/aws/appsync/apis/${module.appsync_api.id}"
  retention_in_days = 7

  tags = local.common_tags
}

module "appsync_api" {
  source = "../../modules/appsync"

  api_name             = "stitchsense-${local.env_name}-appsync"
  cognito_user_pool_id = module.cognito.user_pool_id
  xray_enabled         = false
  aws_region           = var.aws_region

  enable_http_datasource   = true
  fastapi_endpoint         = "http://${module.alb.alb_dns_name}"
  appsync_service_role_arn = module.iam.appsync_service_role_arn

  enable_logging           = true
  field_log_level          = "ALL"
  cloudwatch_logs_role_arn = module.iam.appsync_service_role_arn
  exclude_verbose_content  = false

  tags = local.common_tags
}

########################################
# ADDITIONAL OUTPUTS
########################################

output "sqs_queue_urls" {
  value = {
    default      = aws_sqs_queue.celery_default.url
    default_dlq  = aws_sqs_queue.celery_default_dlq.url
    priority     = aws_sqs_queue.celery_priority.url
    priority_dlq = aws_sqs_queue.celery_priority_dlq.url
  }
  description = "SQS queue URLs for Celery broker"
}

output "redis_redbeat_endpoint" {
  value       = "${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.port}"
  description = "ElastiCache Redis endpoint for RedBeat scheduler"
}

output "celery_configuration" {
  value = {
    broker_url     = "sqs://"
    redbeat_url    = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.port}/1"
    default_queue  = aws_sqs_queue.celery_default.name
    priority_queue = aws_sqs_queue.celery_priority.name
  }
  description = "Celery configuration summary"
}

output "appsync_log_group" {
  value       = aws_cloudwatch_log_group.appsync.name
  description = "CloudWatch log group for AppSync API"
}
