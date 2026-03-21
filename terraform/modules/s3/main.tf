resource "aws_s3_bucket" "this" {
  for_each = { for bucket_name in var.bucket_names : bucket_name => bucket_name }
  bucket   = each.value
}
