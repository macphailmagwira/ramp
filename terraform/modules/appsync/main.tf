########################################
# AppSync GraphQL API
########################################

resource "aws_appsync_graphql_api" "main" {
  name                = var.api_name
  authentication_type = "AMAZON_COGNITO_USER_POOLS"

  user_pool_config {
    aws_region     = var.aws_region
    default_action = "ALLOW"
    user_pool_id   = var.cognito_user_pool_id
  }

  xray_enabled = var.xray_enabled

  # Load schema from file in the environment directory
  schema = file("${path.module}/schema.graphql")

  # CloudWatch Logging Configuration
  dynamic "log_config" {
    for_each = var.enable_logging ? [1] : []
    content {
      cloudwatch_logs_role_arn = var.cloudwatch_logs_role_arn
      field_log_level          = var.field_log_level
      exclude_verbose_content  = var.exclude_verbose_content
    }
  }

  tags = var.tags
}

########################################
# HTTP DataSource for FastAPI via ALB
########################################

resource "aws_appsync_datasource" "fastapi_http" {
  count = var.enable_http_datasource ? 1 : 0

  api_id           = aws_appsync_graphql_api.main.id
  name             = "FastAPIDataSource"
  type             = "HTTP"
  service_role_arn = var.appsync_service_role_arn

  http_config {
    endpoint = var.fastapi_endpoint
  }
}

########################################
# DYNAMIC RESOLVER LOADING
########################################

locals {
  # Discover all VTL request files in the resolvers directory structure
  # Format: {feature}/{type}/{resolver_name}_request.vtl
  resolver_files = fileset("${path.module}/resolvers", "**/*_request.vtl")
  
  # Parse each VTL file and create resolver configuration
  resolvers = {
    for file in local.resolver_files :
    file => {
      # Extract feature name (e.g., "tenant" from "tenant/queries/get_tenant_request.vtl")
      feature = element(split("/", file), 0)
      
      # Extract type (Query or Mutation)
      type = element(split("/", file), 1) == "queries" ? "Query" : "Mutation"
      
      # Extract snake_case resolver name (e.g., "get_tenant" from "get_tenant_request.vtl")
      snake_name = replace(element(split("/", file), 2), "_request.vtl", "")
      
      # Convert snake_case to camelCase for GraphQL field name
      # get_tenant -> getTenant, provision_tenant -> provisionTenant
      field = join("", [
        for i, part in split("_", replace(element(split("/", file), 2), "_request.vtl", "")) :
        i == 0 ? part : title(part)
      ])
      
      # Full paths to VTL templates
      request_vtl  = "${path.module}/resolvers/${file}"
      response_vtl = "${path.module}/resolvers/${replace(file, "_request.vtl", "_response.vtl")}"
    }
  }
}

########################################
# Create All Resolvers Dynamically
########################################

resource "aws_appsync_resolver" "all" {
  for_each = local.resolvers

  api_id      = aws_appsync_graphql_api.main.id
  type        = each.value.type
  field       = each.value.field
  data_source = var.enable_http_datasource ? aws_appsync_datasource.fastapi_http[0].name : null

  request_template  = file(each.value.request_vtl)
  response_template = file(each.value.response_vtl)

  depends_on = [
    aws_appsync_datasource.fastapi_http
  ]
}