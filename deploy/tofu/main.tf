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

  # We adopt the already-running CPX22 via `tofu import` (see README), so never
  # let a plan replace it — replacement means a new box at new pricing plus data
  # loss. prevent_destroy turns any such plan into a hard error. user_data and
  # image are force-new attributes the running box won't match (it predates this
  # cloud-init), so ignore them rather than trigger a rebuild.
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [user_data, image]
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

# Mail records are deliberately NOT managed here. The Proton MX/SPF/DKIM/DMARC
# records — and the protonmail-verification TXT that shares the apex TXT with the
# SPF value — already exist in Gandi, work, and have a high blast radius.
# Managing them in tofu risks rewriting a multi-value TXT and breaking mail, so
# they stay in Gandi, untouched. Only the apex A/AAAA above are tofu's to own;
# import the existing ones before the first apply (see README) so the apply is a
# clean value update (the go-live cutover), not a create/conflict.
