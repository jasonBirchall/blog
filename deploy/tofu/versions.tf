terraform {
  required_version = ">= 1.7"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    gandi = {
      source  = "go-gandi/gandi"
      version = "~> 2.3"
    }
  }

  # State lives in the Hetzner Object Storage bucket (S3-compatible), encrypted
  # at rest by the bucket. The connection details are partial config supplied at
  # `tofu init` time via -backend-config (see README.md) so no secrets land here.
  # Bootstrap note: this module also CREATES the bucket — see README for the
  # local-state-then-migrate sequence on a first-ever apply.
  backend "s3" {
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    use_path_style              = true
    encrypt                     = true
  }
}
