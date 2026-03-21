output "parameters" {
  value = { for k, v in data.aws_ssm_parameter.ssm_parameters : k => v.value }
}