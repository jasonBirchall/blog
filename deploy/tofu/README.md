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

> Note: To actually do anything in tofu, you'll need to perform the following
> and manually fill in the details below

```bash
cp terraform.tfvars.example terraform.tfvars
# These won't be committed to git so you'll need to do it again on another machine.
```

## Values you must confirm/fill (the TODOs)

- [ ] **Server:** `server_type` (`cx22`, cost-optimised x86 — see section
      below), `server_location` (hel1?), `server_image` (`debian-12`).
- [ ] **Object Storage:** `object_storage_endpoint`, `bucket_name`, and the
      access/secret keys.
- [ ] **DNS zone:** `dns_zone`. Only the apex A/AAAA are managed (see below);
      mail records stay in Gandi, unmanaged.
- [ ] **Secrets:** supplied from sops as `TF_VAR_*` via `make tofu-plan` /
      `make tofu-apply` — not in `terraform.tfvars`. See `deploy/secrets/`.

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

## DNS: only the apex A/AAAA are managed

Mail (Proton MX/SPF/DKIM/DMARC, plus the `protonmail-verification` TXT that
shares the apex TXT with SPF) and `www` are **left in Gandi, unmanaged**. The
apex TXT is multi-valued; having tofu own it risks rewriting it to a single value
and breaking mail. So tofu manages only `apex_a` / `apex_aaaa`.

Those apex records already point at the box we're importing, so importing them
makes the plan a **no-op** for DNS (the record value already equals the box IP) —
no cutover, no downtime:

```sh
tofu import gandi_livedns_record.apex_a    "jasonbirchall.dev/@/A"
tofu import gandi_livedns_record.apex_aaaa "jasonbirchall.dev/@/AAAA"
```

After import, `tofu plan` MUST show **no change** to the apex. A diff means the
imported server's IP and the record don't line up — stop and check before apply.
**Definition of done:** plan clean, the site still loads, mail untouched.

## Instance type — adopting the existing CPX22

`server_type` is `cpx22`, the **AMD cost-optimised** shared-vCPU x86 box already
running. We import it rather than create a new one, so there is no new charge and
it keeps its current pricing.

- **It must match the real box.** For the import to plan clean, `server_type` has
  to equal the box's actual type — confirm with `hcloud server describe <name>`
  (the `Type` field). A mismatch shows up as a resize in the plan.
- **x86 keeps the stack unchanged** — no arm64 image audit. (Hetzner's Arm64 CAX
  line is cheaper still, but every image would then need an arm64 build.)
- **Resize in place later.** `cpx22 -> cpx32` is an in-place reboot, not a rebuild.

## Adopting the existing box (import)

We import the running CPX22 into state instead of recreating it — `import` writes
its real ID into state and creates nothing, so no new server, no new charge, and
the box keeps its current pricing.

1. Make `server_name` / `server_type` / `server_location` match the box exactly
   (`hcloud server describe <name>`).
2. `cp import.tf.example import.tf`, fill the numeric server ID, then `tofu plan`
   (expect the 3 imports, 0 to change, 0 to destroy; the firewall/bucket show as
   adds), `tofu apply`, `rm import.tf`. `prevent_destroy` hard-errors before any
   rebuild, so the box is safe even if a force-new attribute slips through.
3. The box is bootstrapped out of band (run N6.2's cloud-init steps by hand),
   since `user_data` only applies at creation.

**Firewall lock-out warning:** `hcloud_firewall.web` allows 80/443 only — no
inbound 22 (SSH is Tailscale-only by design). If you reach the box over public SSH
today, do **not** let that firewall attach until Tailscale SSH is verified on the
box, or add a temporary `in tcp 22` rule scoped to your IP — otherwise applying
locks you out.
