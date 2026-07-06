# Secrets — sops + age

One encrypted file holds every secret. sops encrypts the _values_ (keys stay
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

## Adding a machine (or a second key)

The gotcha up front: you can only add a recipient from a machine that can
already decrypt the file. `sops updatekeys` re-encrypts the data key for every
recipient, and to do that sops has to decrypt it first. A brand-new machine with
no key can't bootstrap itself — the new key gets added _by_ an old one.

So the new machine generates a key and hands its **public** half to a machine
that already has access:

1. On the new machine, make a key and note the public half:

    ```sh
    age-keygen -o ~/.config/sops/age/keys.txt   # Public key: age1newkey…
    ```

2. Add it to `.sops.yaml` next to the existing one — recipients are
   comma-separated:

    ```yaml
    creation_rules:
        - path_regex: deploy/secrets/.*\.sops\.ya?ml$
          age: >-
              age1oldkey…,
              age1newkey…
    ```

3. On a machine that can already decrypt (or after restoring the old private key
   there), reconcile the file to the new recipient list and commit both:

    ```sh
    sops updatekeys deploy/secrets/secrets.sops.yaml
    git add .sops.yaml deploy/secrets/secrets.sops.yaml
    git commit -m "secrets: add <machine> key"
    ```

Editing `.sops.yaml` on its own changes nothing — it only governs _new_
encryptions and what `updatekeys` reconciles to. Until `updatekeys` runs, the
file is still sealed to the old recipient only.

Removing a key (lost laptop, leaked key) is the same dance: delete its line from
`.sops.yaml`, `sops updatekeys`, commit. The old key can no longer open the
re-encrypted file — but treat everything it ever saw as compromised and rotate
those secret _values_ too.

## What goes where

- `TF_VAR_*` keys → consumed by OpenTofu on your laptop. The two object-storage
  keys are **also** needed on the box (Litestream) — see below.
- `django_secret_key`, `proton_smtp_token`, `wakatime_api_key`, and the
  object-storage keys → **podman secrets** on the box (app / alertmanager /
  litestream quadlets, N6.3; `wakatime_api_key` for the daily sync one-shot, N.7).
- `healthchecks_ping_url` → `~/.config/blog/deploy.env` (read by `deploy.sh`, N6.6).
- `watchdog_healthchecks_url` → rendered into `alertmanager.yml` (N6.7).
- Non-secret tofu inputs (box type/region, bucket name, DNS zone, the _public_
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
wakatime_api_key                 wakatime_api_key
TF_VAR_object_storage_access_key object_storage_access_key
TF_VAR_object_storage_secret_key object_storage_secret_key
EOF

ssh blog 'podman secret ls'        # expect the 5 names
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
