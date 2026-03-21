########################################
# AppSync API Outputs
########################################

output "id" {
  description = "The ID of the AppSync GraphQL API"
  value       = aws_appsync_graphql_api.main.id
}

output "graphql_api_id" {
  description = "The ID of the AppSync GraphQL API (alias for backward compatibility)"
  value       = aws_appsync_graphql_api.main.id
}

output "graphql_api_arn" {
  description = "The ARN of the AppSync GraphQL API"
  value       = aws_appsync_graphql_api.main.arn
}

output "graphql_endpoint" {
  description = "The GraphQL endpoint URL"
  value       = aws_appsync_graphql_api.main.uris["GRAPHQL"]
}

output "graphql_api_name" {
  description = "The name of the AppSync GraphQL API"
  value       = aws_appsync_graphql_api.main.name
}

########################################
# DataSource Outputs
########################################

output "fastapi_datasource_name" {
  description = "The name of the FastAPI HTTP datasource"
  value       = var.enable_http_datasource ? aws_appsync_datasource.fastapi_http[0].name : null
}

output "fastapi_datasource_arn" {
  description = "The ARN of the FastAPI HTTP datasource"
  value       = var.enable_http_datasource ? aws_appsync_datasource.fastapi_http[0].arn : null
}

########################################
# Resolver Outputs (for debugging and validation)
########################################

output "resolvers_summary" {
  description = "Summary of all dynamically loaded AppSync resolvers"
  value = {
    total_count = length(local.resolvers)
    
    by_feature = {
      for feature in distinct([for r in local.resolvers : r.feature]) :
      feature => length([for r in local.resolvers : r if r.feature == feature])
    }
    
    by_type = {
      queries   = length([for r in local.resolvers : r if r.type == "Query"])
      mutations = length([for r in local.resolvers : r if r.type == "Mutation"])
    }
  }
}

output "resolver_fields" {
  description = "List of all resolver fields organized by type"
  value = {
    queries = sort([
      for r in local.resolvers : r.field if r.type == "Query"
    ])
    mutations = sort([
      for r in local.resolvers : r.field if r.type == "Mutation"
    ])
  }
}

output "resolver_details" {
  description = "Detailed information about each resolver (for debugging)"
  value = [
    for key, resolver in local.resolvers : {
      field   = resolver.field
      type    = resolver.type
      feature = resolver.feature
      vtl_files = {
        request  = basename(resolver.request_vtl)
        response = basename(resolver.response_vtl)
      }
    }
  ]
}