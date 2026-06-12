provider "hcloud" {
  token = var.hcloud_token
}

# Hetzner Object Storage is S3-compatible; the AWS provider talks to it via a
# custom endpoint. The skip_* flags disable AWS-only preflight checks.
provider "aws" {
  region                      = var.object_storage_region
  access_key                  = var.object_storage_access_key
  secret_key                  = var.object_storage_secret_key
  skip_credentials_validation = true
  skip_region_validation      = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    s3 = var.object_storage_endpoint
  }
}

provider "gandi" {
  personal_access_token = var.gandi_pat
}
