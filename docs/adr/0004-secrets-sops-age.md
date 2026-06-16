# ADR-0004: Secrets via sops + age, committed as ciphertext

- Status: Accepted
- Date: 2026-06-16

## Context

The constitution requires that secrets never enter the repo and that `gitleaks`
passes. The original baseline delivered them two ways: a root-owned
`/etc/blog/env` (mode 600) on the box, and Codeberg Actions secrets for CI.

The pull-based redesign (ADR-0003) removes CI from the deploy path, so Codeberg
Actions secrets are no longer where runtime secrets live. We still need a
**reproducible, versioned** way to (a) feed `TF_VAR_*` to OpenTofu at apply time
and (b) land runtime secrets on a freshly provisioned box — without plaintext on
disk or in git history, and without standing up a separate secret store.

## Decision

**One sops-encrypted file, committed as ciphertext.**

1. `deploy/secrets/secrets.sops.yaml` is committed. sops encrypts the *values* to
   an age recipient; the YAML keys stay readable, so the artifact is ciphertext
   and `gitleaks` passes. A pre-commit hook (`scripts/check-sops-encrypted.sh`)
   refuses to commit the file if it lacks `ENC[` markers.
2. The **age private key lives offline** (password manager / printout), never in
   the repo; `deploy/secrets/.gitignore` blocks `keys.txt`/`*.agekey`.
3. At use time, nothing plaintext touches disk: `sops exec-env` injects `TF_VAR_*`
   for the duration of `tofu plan`/`apply`; on the box, provisioning decrypts and
   creates podman secrets plus `~/.config/blog/deploy.env` (mode 600).

The key prefix routes each value: `TF_VAR_*` → OpenTofu on the laptop; the rest
→ podman secrets / `deploy.env` on the box.

## Consequences

- Secrets are versioned and reviewed alongside the code that consumes them — no
  separate secret manager, no server-only file to keep in sync by hand.
- The age private key is the single point of value: lose it and every secret is
  unrecoverable; leak it and every secret is exposed. Mitigated by an offline
  backup. This is the one thing to guard.
- Rotation is edit → re-encrypt → re-apply/re-provision; there is no out-of-band
  distribution step.
- `gitleaks` and the `sops-encrypted` pre-commit hook are the guardrails against a
  plaintext slip reaching history.
- Reversible: re-encrypt to new recipients, or move to a hosted secret manager
  later — the consuming code reads environment variables either way, so the blast
  radius of a change is small.
- Supersedes the security-baseline bullet placing secrets in `/etc/blog/env` and
  Codeberg Actions secrets.
