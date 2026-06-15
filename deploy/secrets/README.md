# Secrets — sops + age

One encrypted file holds every secret. sops encrypts the *values* (keys stay
readable), so the file is committed and `gitleaks` stays green. The age private
key lives **offline** — that single key is the thing to guard.

## One-time setup

1. Install the tools (`sops`, `age`).
2. Generate your age key and note the public key it prints:
   ```sh
   age-keygen -o ~/.config/sops/age/keys.txt
   # Public key: age1....
   ```
3. Put that **public** key in the repo's `.sops.yaml` (replace the placeholder).
4. **Back up the private key offline** (`~/.config/sops/age/keys.txt`): a
   password manager or a printed copy kept somewhere separate. Lose it and every
   secret is unrecoverable; leak it and every secret is exposed. It must never
   enter the repo.

## Create the encrypted file

```sh
cp secrets.sops.yaml.example secrets.sops.yaml
$EDITOR secrets.sops.yaml                 # paste the real values
sops --encrypt --in-place secrets.sops.yaml
git add deploy/secrets/secrets.sops.yaml  # commits the ciphertext
```

The pre-commit hook refuses to commit it if it is not encrypted.

## Day to day

- **Edit:** `make secrets-edit` (decrypts in your editor, re-encrypts on save).
- **Run tofu:** `make tofu-plan` / `make tofu-apply` — sops injects the `TF_VAR_*`
  values as environment variables for the duration of the command; nothing
  plaintext touches disk.
- **Rotate a secret:** edit the file, re-apply tofu and/or re-provision the box
  (full procedure in the runbook, N7.4).

## What goes where

- `TF_VAR_*` keys → consumed by OpenTofu on your laptop.
- the rest (`django_secret_key`, `proton_smtp_token`, `healthchecks_ping_url`) →
  become podman secrets on the box at provision time (N6.3).
- Non-secret tofu inputs (box type/region, bucket name, DNS zone, the *public*
  Proton DNS record values) do **not** belong here — keep them as `variables.tf`
  defaults or a committed `*.auto.tfvars`.
