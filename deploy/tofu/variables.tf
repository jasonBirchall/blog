# --- Credentials (supply via a git-ignored *.tfvars or TF_VAR_* env) ---

variable "hcloud_token" {
  description = "Hetzner Cloud API token."
  type        = string
  sensitive   = true
}

variable "gandi_pat" {
  description = "Gandi Personal Access Token with LiveDNS scope."
  type        = string
  sensitive   = true
}

variable "object_storage_access_key" {
  description = "Hetzner Object Storage access key."
  type        = string
  sensitive   = true
}

variable "object_storage_secret_key" {
  description = "Hetzner Object Storage secret key."
  type        = string
  sensitive   = true
}

variable "tailscale_auth_key" {
  description = "Tagged (tag:server), single-use, short-lived Tailscale auth key, injected into cloud-init at apply time. Never committed."
  type        = string
  sensitive   = true
  default     = "" # TODO: supply at apply time once N6.2's cloud-init exists.
}

# --- Server (TODO: confirm against the existing box in the Hetzner console) ---

variable "server_name" {
  description = "Hetzner Cloud server name."
  type        = string
  default     = "blog"
}

variable "server_type" {
  # The already-running box is a CPX22 (AMD, cost-optimised shared-vCPU x86) that
  # we import rather than recreate (see README). For the import to plan cleanly,
  # this MUST match the box's real type exactly — confirm with
  # `hcloud server describe <name>` (the Type field). x86 keeps the container
  # stack unchanged (no arm64 image audit).
  description = "Hetzner server type. Must match the imported box's real type."
  type        = string
  default     = "cpx22"
}

variable "server_location" {
  description = "Hetzner location."
  type        = string
  default     = "hel1" # Helsinki. TODO: confirm.
}

variable "server_image" {
  # The running box is debian-13. image is in the server's ignore_changes (an
  # adopted box's image is immutable/force-new), so this is documentation only.
  description = "Hetzner image."
  type        = string
  default     = "debian-13"
}

variable "service_user" {
  description = "Single non-root service user created by cloud-init (N6.2)."
  type        = string
  default     = "blog"
}

variable "ssh_authorized_key" {
  description = "Your laptop's SSH public key (e.g. ssh-ed25519 AAAA...), for admin over the tailnet."
  type        = string
}

variable "cloud_init_template" {
  description = "Path to N6.2's cloud-init template (.tftpl). Left ungenerated until N6.2; user_data is null until the file exists."
  type        = string
  default     = "../cloud-init.yaml.tftpl"
}

# --- Object Storage ---

variable "object_storage_endpoint" {
  description = "Hetzner Object Storage S3 endpoint URL, e.g. https://hel1.your-objectstorage.com."
  type        = string
}

variable "object_storage_region" {
  description = "Region label for the S3 endpoint."
  type        = string
  default     = "hel1"
}

variable "bucket_name" {
  description = "Object Storage bucket for Litestream replicas and tofu state."
  type        = string
}

# --- DNS (Gandi LiveDNS) ---

variable "dns_zone" {
  description = "Apex domain managed in Gandi LiveDNS, e.g. jasonbirchall.dev."
  type        = string
}

# Mail records (Proton MX/SPF/DKIM/DMARC) are intentionally not managed by tofu —
# they live in Gandi and are left untouched. See main.tf's DNS section.
