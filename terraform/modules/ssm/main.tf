data "aws_ssm_parameter" "ssm_parameters" {
  for_each        = var.parameters
  name            = each.value
  with_decryption = true
}