########################################
# PRODUCTION – provider
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
  region  = "ap-southeast-1"
}


provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}


output "alb_dns_name" {
  value       = module.alb.alb_dns_name
  description = "ALB DNS name"
}

output "fastapi_direct_endpoint" {
  value       = "http://${module.alb.alb_dns_name}:8000"
  description = "Direct FastAPI endpoint (for testing only - use port 80 for production)"
}

output "fastapi_endpoint" {
  value       = "http://${module.alb.alb_dns_name}"
  description = "FastAPI endpoint URL used by AppSync (ALB on port 80)"
}

########################################
# VPC + SG
########################################

module "vpc" {
  source = "../../modules/vpc"

  vpc_name             = "stitchsense-production-http"
  cidr_block           = "10.2.0.0/16"
  enable_dns_hostnames = true

  public_subnets = [
    { az = "ap-southeast-1a", cidr = "10.2.1.0/24" },
    { az = "ap-southeast-1b", cidr = "10.2.4.0/24" }
  ]

  private_subnets = [
    { az = "ap-southeast-1a", cidr = "10.2.2.0/24" },
    { az = "ap-southeast-1b", cidr = "10.2.3.0/24" }
  ]

  enable_nat_gateway  = true
  single_nat_gateway  = true

  tags = {
    Environment = "production"
  }
}

# Add these outputs at the end of your main.tf file
output "nat_gateway_public_ips" {
  value       = module.vpc.nat_gateway_public_ips
  description = "Public IPs of NAT Gateways for whitelisting"
}

output "nat_gateway_ids" {
  value       = module.vpc.nat_gateway_ids
  description = "NAT Gateway IDs"
}



module "security_group_production_web" {
  source      = "../../modules/security_groups"
  name        = "stitchsense-production-web-sg"
  description = "Production Security group for web tier"
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

  tags = {
    Name = "stitchsense-production-web-sg"
  }
}

# App SG: EC2 app servers behind ALB
module "security_group_production_app" {
  source      = "../../modules/security_groups"
  name        = "stitchsense-production-app-sg"
  description = "Production Security group for app tier"
  vpc_id      = module.vpc.vpc_id

  ingress = [
    {
      from_port       = 8000
      to_port         = 8000
      protocol        = "tcp"
      security_groups = [module.security_group_production_web.security_group_id]
      cidr_blocks     = []
    }
  ]

  tags = {
    Name = "stitchsense-production-app-sg"
  }
}

module "security_group_production_db" {
  source      = "../../modules/security_groups"
  name        = "stitchsense-production-db-sg"
  description = "Production Security group for database tier"
  vpc_id      = module.vpc.vpc_id

  ingress = [
    {
      from_port       = 5432
      to_port         = 5432
      protocol        = "tcp"
      security_groups = [
        module.security_group_production_app.security_group_id,
        aws_security_group.rds_proxy.id
      ]
      cidr_blocks     = []
    }
  ]

  tags = {
    Name = "stitchsense-production-db-sg"
  }
}

########################################
# SSM Endpoints SG - for VPC endpoints
########################################

resource "aws_security_group" "ssm_endpoints_production" {
  name        = "stitchsense-production-ssm-endpoints-sg"
  description = "Allow HTTPS from app instances to SSM VPC endpoints"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [module.security_group_production_app.security_group_id]
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




  tags = {
    Name        = "stitchsense-production-ssm-endpoints-sg"
    Environment = "production"
  }
}




########################################
# VPC Endpoints for SSM
########################################

resource "aws_vpc_endpoint" "ssm_production" {
  vpc_id              = module.vpc.vpc_id
  vpc_endpoint_type   = "Interface"
  service_name        = "com.amazonaws.ap-southeast-1.ssm"
  subnet_ids          = module.vpc.private_subnet_ids
  security_group_ids  = [aws_security_group.ssm_endpoints_production.id]
  private_dns_enabled = true

  tags = {
    Name        = "stitchsense-production-ssm-endpoint"
    Environment = "production"
  }
}

resource "aws_vpc_endpoint" "ssmmessages_production" {
  vpc_id              = module.vpc.vpc_id
  vpc_endpoint_type   = "Interface"
  service_name        = "com.amazonaws.ap-southeast-1.ssmmessages"
  subnet_ids          = module.vpc.private_subnet_ids
  security_group_ids  = [aws_security_group.ssm_endpoints_production.id]
  private_dns_enabled = true

  tags = {
    Name        = "stitchsense-production-ssmmessages-endpoint"
    Environment = "production"
  }
}

resource "aws_vpc_endpoint" "ec2messages_production" {
  vpc_id              = module.vpc.vpc_id
  vpc_endpoint_type   = "Interface"
  service_name        = "com.amazonaws.ap-southeast-1.ec2messages"
  subnet_ids          = module.vpc.private_subnet_ids
  security_group_ids  = [aws_security_group.ssm_endpoints_production.id]
  private_dns_enabled = true

  tags = {
    Name        = "stitchsense-production-ec2messages-endpoint"
    Environment = "production"
  }
}




#######################################
# SES - Email Service
########################################

#module "ses" {
#  source = "../../modules/ses"

#  domain                  = "stitchsense.ai"
#  configuration_set_name  = "stitchsense-production-emails"
#  environment             = "production"

# Route53 DNS records
#  create_route53_records  = true
#  route53_zone_id         = "Z0695564227B1XIS89WTI"

  # Email templates
#  email_templates = {
#    user-invite-template = {
#      subject = "You're invited to join {{tenant_name}} on StitchSense"
#      html    = file("${path.module}/../../modules/ses/templates/user_invite.html")
#    }
#  }

  # Verified emails
#  verified_emails = ["noreply@stitchsense.ai"]

#  tags = {
#    Environment = "production"
#    Project     = "StitchSense"
#  }
#}

# IAM permissions for EC2
#module "ses_iam" {
#  source = "../../modules/ses/iam"

#  name_prefix         = "stitchsense-production"
#  ses_identity_arns   = [module.ses.domain_identity_arn]
#  iam_role_names      = [module.iam.role_name]

#  restrict_from_addresses = true
#  allowed_from_addresses  = ["noreply@stitchsense.ai"]

#  tags = {
#    Environment = "production"
#  }
#}


# Store in SSM for app to use
#resource "aws_ssm_parameter" "ses_from_email" {
#  name        = "/stitchsense/production/SES_FROM_EMAIL"
#  description = "SES from email address"
#  type        = "String"
#  value       = "noreply@stitchsense.ai"
#
#  tags = {
#    Environment = "production"
#  }
#}

#resource "aws_ssm_parameter" "ses_configuration_set" {
#  name        = "/stitchsense/production/SES_CONFIGURATION_SET"
#  description = "SES configuration set name"
#  type        = "String"
#  value       = module.ses.configuration_set_name
#
#  tags = {
#    Environment = "production"
#  }
#}


########################################
# ELASTICACHE REDIS – Security Group
########################################

resource "aws_security_group" "redis" {
  name        = "stitchsense-production-redis-sg"
  description = "Security group for ElastiCache Redis - access from app tier"
  vpc_id      = module.vpc.vpc_id

  # Allow Redis from app/worker SG
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.security_group_production_app.security_group_id]
    description     = "Allow Redis from app tier (EC2 / Celery workers)"
  }

  # Egress to anywhere (standard)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "stitchsense-production-redis-sg"
    Environment = "production"
  }
}


########################################
# ELASTICACHE REDIS – Subnet Group
########################################

resource "aws_elasticache_subnet_group" "redis" {
  name       = "stitchsense-production-redis-subnet-group"
  subnet_ids = module.vpc.private_subnet_ids

  description = "Subnet group for StitchSense ElastiCache Redis"

  tags = {
    Name        = "stitchsense-production-redis-subnet-group"
    Environment = "production"
  }
}


########################################
# ELASTICACHE REDIS – Cluster
########################################


resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "stitchsense-production-redis"
  engine               = "redis"
  engine_version       = "6.x"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis6.x"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  az_mode           = "single-az"
  maintenance_window = "sun:05:00-sun:06:00"

  tags = {
    Name        = "stitchsense-production-redis"
    Environment = "production"
    Role        = "celery-redbeat"
  }
}



########################################
# ELASTICACHE REDIS – SSM Parameters
########################################

resource "aws_ssm_parameter" "redis_endpoint" {
  name        = "/stitchsense/production/redis_endpoint"
  description = "Primary endpoint for ElastiCache Redis for Celery/RedBeat"
  type        = "String"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address

  tags = {
    Environment = "production"
  }
}

resource "aws_ssm_parameter" "redis_port" {
  name        = "/stitchsense/production/redis_port"
  description = "Port for ElastiCache Redis"
  type        = "String"
  value       = aws_elasticache_cluster.redis.port

  tags = {
    Environment = "production"
  }
}

########################################
# SQS QUEUE FOR S3 EVENTS
########################################

# Main queue for S3 event notifications
resource "aws_sqs_queue" "s3_events" {
  name                      = "stitchsense-production-s3-events"
  delay_seconds             = 0
  max_message_size          = 262144  # 256 KB
  message_retention_seconds = 345600  # 4 days
  receive_wait_time_seconds = 20      # Long polling
  visibility_timeout_seconds = 300    # 5 minutes

  # Dead letter queue configuration
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.s3_events_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "stitchsense-production-s3-events"
    Environment = "production"
    Purpose     = "s3-event-notifications"
  }
}

# Dead Letter Queue for failed S3 event processing
resource "aws_sqs_queue" "s3_events_dlq" {
  name                      = "stitchsense-production-s3-events-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "stitchsense-production-s3-events-dlq"
    Environment = "production"
    Purpose     = "s3-events-dlq"
  }
}

# SQS Queue Policy to allow S3 to send notifications
resource "aws_sqs_queue_policy" "s3_events" {
  queue_url = aws_sqs_queue.s3_events.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowS3ToSendMessage"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.s3_events.arn
        Condition = {
          ArnLike = {
            "aws:SourceArn" = "arn:aws:s3:::stitchsense-production-*"
          }
        }
      }
    ]
  })
}

########################################
# SSM PARAMETERS FOR S3 EVENTS QUEUE
########################################

resource "aws_ssm_parameter" "s3_events_queue_url" {
  name        = "/stitchsense/production/S3_EVENTS_QUEUE_URL"
  description = "SQS queue URL for S3 event notifications"
  type        = "String"
  value       = aws_sqs_queue.s3_events.url

  tags = {
    Environment = "production"
  }
}

resource "aws_ssm_parameter" "s3_events_queue_arn" {
  name        = "/stitchsense/production/S3_EVENTS_QUEUE_ARN"
  description = "SQS queue ARN for S3 event notifications"
  type        = "String"
  value       = aws_sqs_queue.s3_events.arn

  tags = {
    Environment = "production"
  }
}



########################################
# OUTPUTS
########################################

output "s3_events_queue_url" {
  value       = aws_sqs_queue.s3_events.url
  description = "S3 events SQS queue URL"
}

output "s3_events_queue_arn" {
  value       = aws_sqs_queue.s3_events.arn
  description = "S3 events SQS queue ARN"
}


########################################
# EC2 – single Nginx + Docker compose
########################################

module "iam" {
  source = "../../modules/iam"
  env    = "production"
}


module "ec2" {
  source               = "../../modules/ec2"
  ami                  = "ami-0062e0576ebcaa2a9"
  instance_type        = "t3.medium"
  key_name             = "stitchsense-production-key"
  availability_zone    = "ap-southeast-1a"
  iam_instance_profile = module.iam.profile
  user_data = templatefile("../../scripts/ec2_startup_script_production.sh.tmpl", {
  IMAGE_TAG    = var.image_tag
  ENVIRONMENT  = "production"
  AWS_REGION   = var.aws_region
  ECR_REGISTRY = module.ecr.registry
})

  root_volume_size      = 30
  root_volume_type      = "gp3"
  delete_on_termination = true

  security_group_ids = [
    module.security_group_production_app.security_group_id
  ]

  subnet_id = element(module.vpc.public_subnet_ids, 0)

  tags = {
    Environment = "production"
    Name        = "stitchsense-production-ec2"
  }
}


########################################
# ALB - internal
########################################


module "alb" {
  source = "../../modules/alb"

  name            = "stitchsense-production-alb"
  vpc_id          = module.vpc.vpc_id
  subnets         = module.vpc.public_subnet_ids

  security_groups = [module.security_group_production_web.security_group_id]

  internal        = false

  target_groups   = {
    api = {
      port              = 8000
      protocol          = "HTTP"
      health_check_path = "/api/v1/health"
    }
  }

  # later add HTTPS with ACM here if you want the ALB to be TLS-terminating
  cert_arn    = null
  allow_http  = true
  environment = "production"
}



########################################
# ACM for *.production.stitchsense.ai
########################################

module "acm_production" {
  source = "../../modules/acm"

  certificates = {
    production = {
      domain_name               = "stitchsense.ai"
      subject_alternative_names = ["*.stitchsense.ai"]
      validation_method         = "DNS"
    }
  }

  route53_zone_id = "Z0695564227B1XIS89WTI"
}


output "production_acm_arn" {
  value = module.acm_production.certificate_arns["production"]
}


########################################
# APPSYNC – HTTP datasource -> production EC2 via FQDN
########################################

########################################
# COGNITO with User Pool Groups
########################################

module "cognito_production" {
  source           = "../../modules/cognito"
  user_pool_name   = "stitchsense-production-user-pool"
  app_client_name  = "stitchsense-production-app-client"
  generate_secret  = true
  app_url          = "https://app.stitchsense.ai/"

  # User Pool Groups Configuration
  user_pool_groups = [
    {
      name        = "SuperAdmin"
      description = "Super Administrator with full system access"
      precedence  = 1
    },
    {
      name        = "Admin"
      description = "Administrator with elevated privileges"
      precedence  = 2
    },
    {
      name        = "GeneralExec"
      description = "General Executive"
      precedence  = 3
    },
    {
      name        = "MerchandisingExec"
      description = "Merchandising Executive"
      precedence  = 4
    },
    {
      name        = "MerchandisingManager"
      description = "Merchandising Manager"
      precedence  = 5
    },
    {
      name        = "Merchandiser"
      description = "Merchandiser"
      precedence  = 6
    },
    {
      name        = "OperationsExec"
      description = "Operations Executive"
      precedence  = 7
    },
    {
      name        = "OperationsManager"
      description = "Operations Manager"
      precedence  = 8
    },
    {
      name        = "ProductionPlanner"
      description = "Production Planner"
      precedence  = 9
    },
    {
      name        = "SectorManager"
      description = "Sector Manager"
      precedence  = 10
    },
    {
      name        = "LineManager"
      description = "Line Manager"
      precedence  = 11
    },
    {
      name        = "QCStation"
      description = "Quality Control Station"
      precedence  = 12
    },
    {
      name        = "WorkfloorDisplay"
      description = "Workfloor Display Access"
      precedence  = 13
    }
  ]

  tags = {
    Project     = "StitchSense"
    Environment = "production"
    Owner       = "DevOps"
  }
}

resource "aws_iam_role_policy" "ec2_cognito_user_management" {
  name = "stitchsense-production-ec2-cognito-policy"
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
        Resource = module.cognito_production.user_pool_arn
      }
    ]
  })
}

resource "aws_iam_user_policy" "backend_user_cognito" {
  name = "stitchsense-backend-cognito-policy"
  user = "stitchsense-backend"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "cognito-idp:AdminCreateUser",
        "cognito-idp:AdminSetUserPassword",
        "cognito-idp:AdminAddUserToGroup",
        "cognito-idp:AdminDeleteUser",
        "cognito-idp:AdminGetUser",
        "cognito-idp:AdminDisableUser"
      ]
      Resource = module.cognito_production.user_pool_arn
    }]
  })
}

########################################
# CloudWatch Log Group for AppSync
########################################

resource "aws_cloudwatch_log_group" "appsync" {
  name              = "/aws/appsync/apis/${module.appsync_api.id}"
  retention_in_days = 30

  tags = {
    Environment = "production"
    Project     = "StitchSense"
  }
}

########################################
# APPSYNC with HTTP DataSource to FastAPI
########################################

module "appsync_api" {
  source = "../../modules/appsync"

  api_name             = "stitchsense-production-appsync"
  cognito_user_pool_id = module.cognito_production.user_pool_id
  xray_enabled         = true
  aws_region           = "ap-southeast-1"


  # Enable HTTP datasource for FastAPI
  enable_http_datasource   = true
  fastapi_endpoint         = "http://${module.alb.alb_dns_name}"
  appsync_service_role_arn = module.iam.appsync_service_role_arn

  # CloudWatch Logging
  enable_logging           = true
  field_log_level          = "ERROR"
  cloudwatch_logs_role_arn = module.iam.appsync_service_role_arn
  exclude_verbose_content  = true

  tags = {
    Project     = "StitchSense"
    Environment = "production"
    Owner       = "DevOps"
  }
}

output "appsync_log_group" {
  value       = aws_cloudwatch_log_group.appsync.name
  description = "CloudWatch log group for AppSync API"
}

resource "aws_lb_target_group_attachment" "production_ec2" {
  target_group_arn = module.alb.target_group_arns["api"]
  target_id        = module.ec2.instance_id
  port             = 8000
}



########################################
# ACM for AppSync
########################################



resource "aws_acm_certificate" "appsync_production_us_east_1" {
  provider          = aws.us_east_1
  domain_name       = "api.stitchsense.ai"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "api-stitchsense-ai"
    Environment = "production"
  }
}

# DNS validation records (will be created in your existing Route53 zone)
resource "aws_route53_record" "appsync_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.appsync_production_us_east_1.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id = "Z0695564227B1XIS89WTI"
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]

  allow_overwrite = true
}

# Wait for validation to complete
resource "aws_acm_certificate_validation" "appsync_production_us_east_1" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.appsync_production_us_east_1.arn
  validation_record_fqdns = [for record in aws_route53_record.appsync_cert_validation : record.fqdn]
}

########################################
# APPSYNC CUSTOM DOMAIN
########################################

resource "aws_appsync_domain_name" "production" {
  domain_name     = "api.stitchsense.ai"
  certificate_arn = aws_acm_certificate_validation.appsync_production_us_east_1.certificate_arn

  depends_on = [
    aws_acm_certificate_validation.appsync_production_us_east_1
  ]
}

resource "aws_appsync_domain_name_api_association" "production" {
  api_id      = module.appsync_api.id
  domain_name = aws_appsync_domain_name.production.domain_name
}


# Route53 record for AppSync custom domain
resource "aws_route53_record" "api_production" {
  zone_id = "Z0695564227B1XIS89WTI"
  name    = "api.stitchsense.ai"
  type    = "A"

  alias {
    name                   = aws_appsync_domain_name.production.appsync_domain_name
    zone_id                = aws_appsync_domain_name.production.hosted_zone_id
    evaluate_target_health = false
  }
}



output "appsync_custom_domain" {
  value       = "https://api.stitchsense.ai/graphql"
  description = "AppSync custom domain URL"
}


########################################
# PRODUCTION SERVICES
########################################

data "aws_ssm_parameter" "rds_production_password" {
  name = "/stitchsense/production/rds/password"
}


module "rds_production" {
  source = "../../modules/rds"

  db_identifier                       = "stitchsense-production-db"
  allocated_storage                   = 100
  instance_class                      = "db.t3.small"
  engine                              = "postgres"
  backup_window                       = "03:00-04:00"
  backup_retention_period             = 7
  maintenance_window                  = "sun:04:00-sun:05:00"
  multi_az                            = true
  engine_version                      = "15.12"
  auto_minor_version_upgrade          = true
  license_model                       = "postgresql-license"
  publicly_accessible                 = false
  storage_type                        = "gp3"
  port                                = 5432
  storage_encrypted                   = true
  kms_key_id                          = "arn:aws:kms:ap-southeast-1:514145637758:key/345ecb8c-7bae-412f-91df-d7a143e953dc"
  copy_tags_to_snapshot               = true
  monitoring_interval                 = 0
  iam_database_authentication_enabled = false
  subnet_group_name                   = "stitchsense-production-db-subnet"
  subnet_ids                          = module.vpc.public_subnet_ids
  vpc_security_group_ids              = [module.security_group_production_db.security_group_id]
  db_name                             = "stitchsense_production"
  username                            = "stitchsense_production"
  password                            = data.aws_ssm_parameter.rds_production_password.value
  deletion_protection                 = true
  skip_final_snapshot                 = false


}

########################################
# IAM POLICY FOR SSM PARAMETER STORE ACCESS
########################################

resource "aws_iam_role_policy" "ec2_ssm_parameter_store_access" {
  name = "stitchsense-production-ec2-ssm-parameter-store-policy"
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

module "ssm" {
  source = "../../modules/ssm"

  parameters = {
    deploy_key     = "/stitchsense/deploy-key/private"
    api_secret_key = "/stitchsense/prod/api_secret_key"
    database_url   = "/stitchsense/prod/database_url"
    db_host        = "/stitchsense/prod/db_host"
    ecr_registry   = "/stitchsense/prod/ecr_registry"
    db_password    = "/stitchsense/prod/db_password"
    redis_password = "/stitchsense/prod/redis_password"
    s3_bucket      = "/stitchsense/prod/s3_bucket"
    rds_endpoint   = "/stitchsense/prod/rds_endpoint"
    rds_password   = "/stitchsense/rds/password"
    rds_production_password = "/stitchsense/production/rds/password"
    jwt_secret     = "/stitchsense/prod/jwt_secret"
  }
}

module "secrets_manager" {
  source = "../../modules/secrets_manager"

  secrets = {
    rds_dev        = { name = "stitchsense/rds/master-dev" }
    rds_production = { name = "stitchsense_production_db" }
    ssh_private    = { name = "/stitchsense/ssh/ec2-production-private-key" }
    ssh_public     = { name = "/stitchsense/ssh/ec2-production-public-key" }
  }
}


module "sns_production" {
  source = "../../modules/sns"
  topics = [
  ]
}

module "sqs_production" {
  source = "../../modules/sqs"
  queues = [
  ]
}

########################################
# ECR
########################################

module "ecr" {
  source = "../../modules/ecr"
  region = "ap-southeast-1"


  repositories = [
    "stitchsense-production-api-main",
    "stitchsense-production-worker-main"
  ]
}


########################################
# RDS Proxy for Production
########################################

# Reference the existing Secrets Manager secret for production
data "aws_secretsmanager_secret" "rds_master_production" {
  name = "stitchsense_production_db"
}

data "aws_secretsmanager_secret_version" "rds_master_production" {
  secret_id = data.aws_secretsmanager_secret.rds_master_production.id
}

# IAM Role for RDS Proxy
resource "aws_iam_role" "rds_proxy" {
  name = "stitchsense-production-rds-proxy-role"

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

  tags = {
    Name        = "stitchsense-production-rds-proxy-role"
    Environment = "production"
  }
}

# IAM Policy for RDS Proxy to access Secrets Manager
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
        Resource = data.aws_secretsmanager_secret.rds_master_production.arn
      }
    ]
  })
}

# Security Group for RDS Proxy
resource "aws_security_group" "rds_proxy" {
  name        = "stitchsense-production-rds-proxy-sg"
  description = "Security group for RDS Proxy"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.security_group_production_app.security_group_id]
    description     = "Allow PostgreSQL from app tier"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "stitchsense-production-rds-proxy-sg"
    Environment = "production"
  }
}

# RDS Proxy
resource "aws_db_proxy" "main" {
  name          = "stitchsense-production-rds-proxy"
  engine_family = "POSTGRESQL"

  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = data.aws_secretsmanager_secret.rds_master_production.arn
  }

  role_arn       = aws_iam_role.rds_proxy.arn
  vpc_subnet_ids = module.vpc.private_subnet_ids
  vpc_security_group_ids = [aws_security_group.rds_proxy.id]

  require_tls    = true
  debug_logging  = false

  tags = {
    Name        = "stitchsense-production-rds-proxy"
    Environment = "production"
  }
}

# RDS Proxy Target Group
resource "aws_db_proxy_default_target_group" "main" {
  db_proxy_name = aws_db_proxy.main.name

  connection_pool_config {
    max_connections_percent      = 100
    max_idle_connections_percent = 50
    connection_borrow_timeout    = 120
  }
}

# RDS Proxy Target

resource "aws_db_proxy_target" "main" {
  db_proxy_name          = aws_db_proxy.main.name
  target_group_name      = aws_db_proxy_default_target_group.main.name
  db_instance_identifier = "stitchsense-production-db"
  depends_on = [module.rds_production]

}

# Store RDS Proxy endpoint in SSM
resource "aws_ssm_parameter" "rds_proxy_endpoint" {
  name        = "/stitchsense/production/rds_proxy_endpoint"
  description = "RDS Proxy endpoint for production"
  type        = "String"
  value       = aws_db_proxy.main.endpoint

  tags = {
    Environment = "production"
  }
}

# Output the proxy endpoint
output "rds_proxy_endpoint" {
  value       = aws_db_proxy.main.endpoint
  description = "RDS Proxy endpoint for production"
}


########################################
# S3 BUCKET DATA SOURCE
########################################

data "aws_s3_bucket" "data_uploads" {
  bucket = "stitchsense-production-uploads"
}

output "s3_data_uploads_bucket" {
  value       = data.aws_s3_bucket.data_uploads.id
  description = "S3 bucket for data uploads"
}


########################################
# SQS DEFAULT QUEUE FOR CELERY TASKS
########################################

# Main queue for general Celery tasks (file processing, etc.)
resource "aws_sqs_queue" "celery_default" {
  name                      = "stitchsense-production-celery-default"
  delay_seconds             = 0
  max_message_size          = 262144  # 256 KB
  message_retention_seconds = 345600  # 4 days
  receive_wait_time_seconds = 20      # Long polling
  visibility_timeout_seconds = 3600   # 1 hour (matches celery config)

  # Dead letter queue configuration
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.celery_default_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "stitchsense-production-celery-default"
    Environment = "production"
    Purpose     = "celery-tasks"
  }
}

# Dead Letter Queue for failed Celery task processing
resource "aws_sqs_queue" "celery_default_dlq" {
  name                      = "stitchsense-production-celery-default-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "stitchsense-production-celery-default-dlq"
    Environment = "production"
    Purpose     = "celery-tasks-dlq"
  }
}

########################################
# SSM PARAMETERS FOR CELERY DEFAULT QUEUE
########################################

resource "aws_ssm_parameter" "celery_default_queue_url" {
  name        = "/stitchsense/production/SQS_DEFAULT_QUEUE_URL"
  description = "SQS queue URL for Celery default tasks (file processing, etc.)"
  type        = "String"
  value       = aws_sqs_queue.celery_default.url

  tags = {
    Environment = "production"
  }
}

resource "aws_ssm_parameter" "celery_default_queue_arn" {
  name        = "/stitchsense/production/SQS_DEFAULT_QUEUE_ARN"
  description = "SQS queue ARN for Celery default tasks"
  type        = "String"
  value       = aws_sqs_queue.celery_default.arn

  tags = {
    Environment = "production"
  }
}

########################################
# IAM POLICY FOR EC2 TO ACCESS CELERY DEFAULT QUEUE
########################################

resource "aws_iam_role_policy" "ec2_celery_default_sqs_access" {
  name = "stitchsense-production-ec2-celery-default-sqs-policy"
  role = module.iam.role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:SendMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = [
          aws_sqs_queue.celery_default.arn,
          aws_sqs_queue.celery_default_dlq.arn
        ]
      }
    ]
  })
}

########################################
# UPDATE EXISTING S3 EVENTS IAM POLICY TO INCLUDE SendMessage
########################################

# Note: Update your existing ec2_s3_events_sqs_access policy to include SendMessage
# This allows the s3-events consumer task to dispatch tasks to the default queue

resource "aws_iam_role_policy" "ec2_s3_events_sqs_access" {
  name = "stitchsense-production-ec2-s3-events-sqs-policy"
  role = module.iam.role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:SendMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = [
          aws_sqs_queue.s3_events.arn,
          aws_sqs_queue.s3_events_dlq.arn,
          aws_sqs_queue.celery_default.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::stitchsense-production-*",
          "arn:aws:s3:::stitchsense-production-*/*"
        ]
      }
    ]
  })
}

########################################
# OUTPUTS
########################################

output "celery_default_queue_url" {
  value       = aws_sqs_queue.celery_default.url
  description = "Celery default tasks SQS queue URL"
}

output "celery_default_queue_arn" {
  value       = aws_sqs_queue.celery_default.arn
  description = "Celery default tasks SQS queue ARN"
}

output "celery_default_queue_dlq_url" {
  value       = aws_sqs_queue.celery_default_dlq.url
  description = "Celery default tasks DLQ URL"
}


########################################
# LAMBDA - S3 to Celery Transformer
########################################

module "lambda_s3_celery_transformer" {
  source = "../../modules/lambda"

  function_name      = "stitchsense-production-s3-celery-transformer"
  runtime            = "python3.11"
  timeout            = 30
  memory_size        = 256
  log_retention_days = 14

  # SQS configuration
  target_queue_url = aws_sqs_queue.s3_events.url
  target_queue_arn = aws_sqs_queue.s3_events.arn

  # S3 trigger configuration
  enable_s3_trigger       = true
  create_s3_notification  = true
  s3_bucket_id           = data.aws_s3_bucket.data_uploads.id
  s3_bucket_arn          = data.aws_s3_bucket.data_uploads.arn
  s3_events              = ["s3:ObjectCreated:*"]
  #s3_filter_prefix       = "uploads/"
  # s3_filter_suffix     = ".csv"  # Uncomment to only trigger on CSV files

  # Additional environment variables (optional)
  environment_variables = {
    ENVIRONMENT = "production"
    LOG_LEVEL   = "INFO"
  }

  tags = {
    Name        = "stitchsense-production-s3-celery-transformer"
    Environment = "production"
    Purpose     = "s3-to-celery-bridge"
    ManagedBy   = "terraform"
  }
}

########################################
# OUTPUTS
########################################

output "lambda_function_name" {
  value       = module.lambda_s3_celery_transformer.function_name
  description = "Lambda function name for S3 to Celery transformation"
}

output "lambda_function_arn" {
  value       = module.lambda_s3_celery_transformer.function_arn
  description = "Lambda function ARN"
}

output "lambda_log_group" {
  value       = module.lambda_s3_celery_transformer.log_group_name
  description = "CloudWatch log group for Lambda"
}
