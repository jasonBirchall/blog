#!/usr/bin/env bash
# Refuse to commit a *.sops.yaml that is not actually sops-encrypted, so a
# plaintext secrets file can never slip into history. pre-commit passes the
# matched files as arguments.
set -euo pipefail

status=0
for file in "$@"; do
  if ! grep -q 'ENC\[' "$file"; then
    echo "error: $file is not sops-encrypted (no ENC[...] markers found)." >&2
    echo "       encrypt it first: sops --encrypt --in-place $file" >&2
    status=1
  fi
done
exit "$status"
