terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
  # Uncomment to use S3 backend (replace with your values):
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "argus-for-athena/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "argus-for-athena"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Separate provider for ACM — must be us-east-1 for CloudFront
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "argus-for-athena"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
