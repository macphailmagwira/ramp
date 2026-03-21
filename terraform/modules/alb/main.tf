# ALB
resource "aws_lb" "this" {
  name               = var.name
  internal           = var.internal      # <- make internal configurable
  load_balancer_type = "application"
  security_groups    = var.security_groups
  subnets            = var.subnets

  tags = {
    Name        = var.name
    Environment = var.environment
  }
}

# Target groups remain the same
resource "aws_lb_target_group" "this" {
  for_each = var.target_groups

  name     = "${var.name}-${each.key}"
  port     = each.value.port
  protocol = upper(each.value.protocol)
  vpc_id   = var.vpc_id

  health_check {
    path                = each.value.health_check_path != null ? each.value.health_check_path : "/api/v1/health"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    matcher             = "200-399"
  }

  tags = {
    Name        = "${var.name}-${each.key}"
    Environment = var.environment
  }
}

# HTTPS listener only if cert ARN is provided
resource "aws_lb_listener" "https" {
  count             = var.cert_arn != null ? 1 : 0
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = var.cert_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this["api"].arn
  }
}

# Optional HTTP listener
resource "aws_lb_listener" "http" {
  count             = var.allow_http ? 1 : 0
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this["api"].arn
  }
}