terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    bucket         = "stitchsense-terraform-state"
    key            = "stitchsense/staging/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "stitchsense-terraform-locks"
    encrypt        = true
  }

}

