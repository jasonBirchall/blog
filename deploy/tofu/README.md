# Infrastructure (OpenTofu) — N6.1

Manages the Hetzner VPS, its firewall (80/443 only — SSH is Tailscale-only),
the Object Storage bucket (Litestream replicas + remote state), and Gandi DNS.

This is a **scaffold**: it has not been `tofu plan`'d against a real account.
Fill the checklist below, then `tofu fmt && tofu validate && tofu plan` and read
every line of the plan before applying.

## Files

- `versions.tf` — provider/version pins and the S3 backend (partial config).
- `providers.tf` — hcloud, aws-against-Hetzner-S3, gandi.
- `variables.tf` — every input; secrets are `sensitive`.
- `main.tf` — server, firewall, bucket (+versioning/lifecycle), DNS.
- `outputs.tf` — server IPs, bucket name.
- `terraform.tfvars.example` — copy to `terraform.tfvars` (git-ignored) and fill.

## Values you must confirm/fill (the TODOs)

- [ ] **Server:** `server_type` (`cx22`, cost-optimised x86 — see section
      below), `server_location` (hel1?), `server_image` (`debian-12`).
- [ ] **Object Storage:** `object_storage_endpoint`, `bucket_name`, and the
      access/secret keys.
- [ ] **DNS zone:** `dns_zone`.
- [ ] **Proton mail records (DO NOT DISTURB):** `proton_mx_records`,
      `proton_spf_record`, `proton_dmarc_record`, `proton_dkim_cnames` — paste
      the real values from Gandi, and import the existing records (below).
- [ ] **Secrets:** `hcloud_token`, `gandi_pat`, Object Storage keys — via
      `terraform.tfvars` or `TF_VAR_*`. The `tailscale_auth_key` is supplied at
      apply time once N6.2's cloud-init template exists.

## First-apply bootstrap (the bucket holds its own state)

The S3 backend wants to live in the bucket this module creates — a
chicken-and-egg. On a first-ever apply:

1. Comment out the `backend "s3"` block in `versions.tf` (local state).
2. `tofu init && tofu apply` to create the bucket (and the rest).
3. Restore the backend block, create `backend.hcl` (git-ignored):
   ```hcl
   bucket     = "jasonbirchall-blog"
   key        = "tofu/blog.tfstate"
   region     = "hel1"
   access_key = "..."
   secret_key = "..."
   endpoints  = { s3 = "https://hel1.your-objectstorage.com" }
   ```
4. `tofu init -backend-config=backend.hcl -migrate-state`.

If the bucket already exists, skip steps 1–2 and just init with the backend.

## Importing the Proton mail records (do this before the first apply)

The MX/SPF/DKIM/DMARC records already exist in Gandi. Importing them means tofu
adopts them rather than recreating (and briefly dropping) them:

```sh
tofu import 'gandi_livedns_record.mx[0]'    "<zone>/@/MX"
tofu import 'gandi_livedns_record.spf[0]'   "<zone>/@/TXT"
tofu import 'gandi_livedns_record.dmarc[0]' "<zone>/_dmarc/TXT"
tofu import 'gandi_livedns_record.dkim["protonmail._domainkey"]' "<zone>/protonmail._domainkey/CNAME"
# ...repeat for protonmail2/3._domainkey
```

After importing, `tofu plan` MUST show **no change** to those records. If it
shows a diff, the variable values don't match reality — fix the values, do not
apply. **Definition of done:** plan clean, and a test mail still arrives.

## Cost-optimised instance type

`server_type` defaults to `cx22`, a cost-optimised shared-vCPU **x86** instance
(Intel CX line; the AMD CPX line is an equivalent alternative). Staying on x86:

- **The container stack runs unchanged** — no arm64 image audit, no cross-arch
  build concerns. (Hetzner's Arm64 CAX line is cheaper still, but every image
  would then need an arm64 build.)
- **Start small, resize in place.** `cx22` is 4 GB; `cx22 -> cx32` (8 GB) is an
  in-place reboot, not a rebuild, if the observability stack wants headroom.

## Note on the existing sandbox box

Per the plan, the hand-created box is a disposable sandbox for working out the
quadlet/rootless/Tailscale edges. It is destroyed and replaced by the server
this module provisions (cloud-init only runs at creation). It must never quietly
become production.
