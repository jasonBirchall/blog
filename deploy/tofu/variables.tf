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
  # Cost-optimised shared-vCPU x86 line: CX (Intel) or CPX (AMD). cx22 is
  # 2 vCPU / 4 GB / 40 GB. Staying x86 keeps the container stack unchanged (no
  # arm64 image audit). Resizing within a line (e.g. cx22 -> cx32, 8 GB) is an
  # in-place reboot, not a rebuild — start small and grow if the observability
  # stack needs headroom. (CAX/Arm64 is cheaper still but would need arm64 images.)
  description = "Hetzner server type (cost-optimised x86 shared vCPU: CX/CPX)."
  type        = string
  default     = "cx22"
}

variable "server_location" {
  description = "Hetzner location."
  type        = string
  default     = "hel1" # Helsinki. TODO: confirm.
}

variable "server_image" {
  description = "Hetzner image."
  type        = string
  default     = "debian-12"
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

variable "noncurrent_retention_days" {
  description = "Days to keep non-current (versioned) objects before expiry."
  type        = number
  default     = 30
}

# --- DNS (Gandi LiveDNS) ---

variable "dns_zone" {
  description = "Apex domain managed in Gandi LiveDNS, e.g. jasonbirchall.dev."
  type        = string
}

# Proton mail records — DO NOT DISTURB. Import the EXISTING records into state
# before the first apply, then set these to match reality exactly so plan is a
# no-op. See README. TODO: paste the real values.
variable "proton_mx_records" {
  description = "Proton MX records, e.g. [\"10 mail.protonmail.ch.\", \"20 mailsec.protonmail.ch.\"]."
  type        = list(string)
  default     = []
}

variable "proton_spf_record" {
  description = "Proton SPF TXT value, e.g. \"v=spf1 include:_spf.protonmail.ch ~all\"."
  type        = string
  default     = ""
}

variable "proton_dmarc_record" {
  description = "DMARC TXT value, e.g. \"v=DMARC1; p=quarantine\"."
  type        = string
  default     = ""
}

variable "proton_dkim_cnames" {
  description = "Proton DKIM CNAMEs as { name => target }, e.g. { \"protonmail._domainkey\" = \"...\" } (Proton usually issues three)."
  type        = map(string)
  default     = {}
}
