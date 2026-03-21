########################################
# EC2 IAM Role
########################################

# Create the IAM role for EC2
resource "aws_iam_role" "ec2_role" {
  name               = "stitchsense-${var.env}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  description        = "EC2 role for ${var.env} environment"
}

# Assume role policy allowing EC2 to assume this role
data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# Attach managed policies (optional: e.g., SSM, CloudWatch)
resource "aws_iam_role_policy_attachment" "ssm" {
  for_each = toset(
    concat(
      [
        "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
      ],
      var.additional_policy_arns
    )
  )

  role       = aws_iam_role.ec2_role.name
  policy_arn = each.value
}

# Create an instance profile for the EC2 module
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "stitchsense-${var.env}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# ECR Access for EC2
resource "aws_iam_role_policy" "ec2_ecr_access" {
  name = "stitchsense-${var.env}-ec2-ecr-access"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}

########################################
# AppSync VPC Role (existing)
########################################

resource "aws_iam_role" "appsync_vpc" {
  name = "stitchsense-${var.env}-appsync-vpc-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "appsync.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name        = "stitchsense-${var.env}-appsync-vpc-role"
    Environment = var.env
  }
}

resource "aws_iam_role_policy" "appsync_vpc" {
  name = "stitchsense-${var.env}-appsync-vpc-policy"
  role = aws_iam_role.appsync_vpc.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "ec2:DescribeNetworkInterfaces",
          "ec2:CreateNetworkInterface",
          "ec2:DeleteNetworkInterface",
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

########################################
# AppSync Service Role for HTTP DataSource & CloudWatch Logs
########################################

resource "aws_iam_role" "appsync_service_role" {
  name = "stitchsense-${var.env}-appsync-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "appsync.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name        = "stitchsense-${var.env}-appsync-service-role"
    Environment = var.env
  }
}

# Inline policy for CloudWatch Logs
resource "aws_iam_role_policy" "appsync_cloudwatch_logs" {
  name = "appsync-cloudwatch-logs-policy"
  role = aws_iam_role.appsync_service_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Attach AWS managed policy for AppSync CloudWatch Logs
resource "aws_iam_role_policy_attachment" "appsync_cloudwatch_logs_managed" {
  role       = aws_iam_role.appsync_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppSyncPushToCloudWatchLogs"
}