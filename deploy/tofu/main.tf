# --- Firewall: public internet sees 80/443 only. SSH is Tailscale-only (N6.2),
# so there is deliberately no inbound 22. ICMP allowed for diagnostics. ---

resource "hcloud_firewall" "web" {
  name = "${var.server_name}-web"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

# --- The VPS. cloud-init (N6.2) carries the whole bootstrap recipe and is
# templated with the Tailscale auth key at apply time. user_data stays null
# until N6.2 creates the template, so this module plans cleanly today. ---

resource "hcloud_server" "blog" {
  name         = var.server_name
  server_type  = var.server_type
  location     = var.server_location
  image        = var.server_image
  firewall_ids = [hcloud_firewall.web.id]

  user_data = fileexists(var.cloud_init_template) ? templatefile(var.cloud_init_template, {
    tailscale_auth_key = var.tailscale_auth_key
    service_user       = var.service_user
    ssh_authorized_key = var.ssh_authorized_key
  }) : null

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  labels = {
    role       = "blog"
    managed_by = "opentofu"
  }
}

# --- Object Storage: Litestream replicas + tofu remote state. Versioning and a
# non-current expiry lifecycle per the plan. ---

resource "aws_s3_bucket" "data" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {} # applies to all objects in the bucket

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_retention_days
    }
  }
}

# --- DNS: apex A/AAAA point at the box. ---

resource "gandi_livedns_record" "apex_a" {
  zone   = var.dns_zone
  name   = "@"
  type   = "A"
  ttl    = 3600
  values = [hcloud_server.blog.ipv4_address]
}

resource "gandi_livedns_record" "apex_aaaa" {
  zone   = var.dns_zone
  name   = "@"
  type   = "AAAA"
  ttl    = 3600
  values = [hcloud_server.blog.ipv6_address]
}

# --- DNS: Proton mail records. DO NOT DISTURB. ---
# These already exist in the zone. IMPORT them into state before the first apply
# (see README) and keep the values below matching reality exactly, so `tofu
# plan` reports no change. A mistake here silently breaks mail delivery.

resource "gandi_livedns_record" "mx" {
  count  = length(var.proton_mx_records) > 0 ? 1 : 0
  zone   = var.dns_zone
  name   = "@"
  type   = "MX"
  ttl    = 10800
  values = var.proton_mx_records
}

resource "gandi_livedns_record" "spf" {
  count  = var.proton_spf_record != "" ? 1 : 0
  zone   = var.dns_zone
  name   = "@"
  type   = "TXT"
  ttl    = 10800
  values = [var.proton_spf_record]
}

resource "gandi_livedns_record" "dmarc" {
  count  = var.proton_dmarc_record != "" ? 1 : 0
  zone   = var.dns_zone
  name   = "_dmarc"
  type   = "TXT"
  ttl    = 10800
  values = [var.proton_dmarc_record]
}

resource "gandi_livedns_record" "dkim" {
  for_each = var.proton_dkim_cnames
  zone     = var.dns_zone
  name     = each.key
  type     = "CNAME"
  ttl      = 10800
  values   = [each.value]
}
