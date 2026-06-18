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

- `TF_VAR_*` keys → consumed by OpenTofu on your laptop. The two object-storage
  keys are **also** needed on the box (Litestream) — see below.
- `django_secret_key`, `proton_smtp_token`, and the object-storage keys →
  **podman secrets** on the box (app / alertmanager / litestream quadlets, N6.3).
- `healthchecks_ping_url` → `~/.config/blog/deploy.env` (read by `deploy.sh`, N6.6).
- `watchdog_healthchecks_url` → rendered into `alertmanager.yml` (N6.7).
- Non-secret tofu inputs (box type/region, bucket name, DNS zone, the *public*
  Proton DNS values) do **not** belong here — keep them in `terraform.tfvars`.

## On the box — create the podman secrets (N6.3)

The age key never goes on the box. Decrypt each value **locally** and pipe it
over SSH straight into `podman secret create`, so the plaintext only exists in
the SSH tunnel and then in podman's secret store — never a file, never shell
history. Run as `blog` (rootless secrets are per-user); `ssh blog` already is.

```sh
# from the repo root on your laptop. Maps sops key -> podman secret name.
while read -r sops_key pod_name; do
  sops -d --extract "[\"$sops_key\"]" deploy/secrets/secrets.sops.yaml | tr -d '\n' \
    | ssh blog "podman secret create $pod_name -"
done <<'EOF'
django_secret_key                django_secret_key
proton_smtp_token                proton_smtp_token
TF_VAR_object_storage_access_key object_storage_access_key
TF_VAR_object_storage_secret_key object_storage_secret_key
EOF

ssh blog 'podman secret ls'        # expect the 4 names
```

- `--extract '["…"]'` pulls one value; `tr -d '\n'` strips the trailing newline
  (an extra `\n` in a token breaks auth); the trailing `-` makes podman read from
  stdin, so the value never lands in argv.
- The podman names must match the `Secret=` lines in `deploy/quadlets/*.container`.

The deploy heartbeat is a file, not a podman secret (mode 600):

```sh
{ printf 'HEALTHCHECKS_PING_URL='; \
  sops -d --extract '["healthchecks_ping_url"]' deploy/secrets/secrets.sops.yaml | tr -d '\n'; \
  printf '\n'; } \
  | ssh blog 'install -d -m700 ~/.config/blog && umask 177 && cat > ~/.config/blog/deploy.env'
```

`watchdog_healthchecks_url` is rendered into `alertmanager.yml` (N6.7).

## Rotating a box secret

podman won't overwrite an existing secret, so remove then re-create, and restart
the consumer:

```sh
ssh blog 'podman secret rm django_secret_key'
sops -d --extract '["django_secret_key"]' deploy/secrets/secrets.sops.yaml | tr -d '\n' \
  | ssh blog 'podman secret create django_secret_key -'
ssh blog 'systemctl --user restart app'    # pick up the new value
```
