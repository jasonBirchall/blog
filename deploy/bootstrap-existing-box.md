# Manually bootstrapping the existing box (N6.2 by hand)

`cloud-init` only runs at **creation**, and this box (CPX22, created 2026-06-03)
predates `deploy/cloud-init.yaml.tftpl`. So apply that same recipe by hand. This
runbook is a faithful translation of the cloud-init; keep them in sync.

## ⚠️ Read first — how not to lock yourself out

The recipe ends by binding `sshd` to the **tailnet address only** — after that,
`sshd` no longer listens on the public IP, and later `tofu apply` drops public
port 22 at the firewall too. So:

- **Keep your current public-SSH (root) session open the entire time.** Do not
  close it until tailnet SSH is proven.
- **Open a second terminal** to test tailnet SSH before the lock-down step.
- **Break-glass fallback:** the Hetzner Cloud Console has a web VNC console
  (Server → Console) and a Rescue system. If you do lock yourself out, that's how
  you get back in to fix `sshd_config.d/`. Know where it is *before* you start.
- **Tailnet ACL:** confirm your laptop is allowed to reach `tag:server:22` over
  the tailnet (default ACLs allow it; if you've tightened them, add the rule).

## Inputs

- `service_user` = `blog`
- Your SSH **public** key (the same one in `ssh_authorized_key`).
- A fresh **Tailscale auth key** — tagged `tag:server`, single-use, pre-authorized,
  short expiry (login.tailscale.com → Settings → Keys).

Run steps 1–5 and 7 as **root** (or `sudo`). Step 6 is from your **laptop**.
After step 7 you reach the box as **`blog`** over the tailnet — run steps 8–9
there (with `sudo` only where noted).

## 1. Packages

```sh
apt update && apt upgrade -y
# passt provides `pasta` — Podman 5's default rootless network backend (without
# it, `podman run` fails with "could not find pasta").
apt install -y git podman aardvark-dns uidmap passt slirp4netns fuse-overlayfs \
               unattended-upgrades apt-listchanges curl ca-certificates
```

## 2. Service user (`blog`) with your key and passwordless sudo

```sh
id blog >/dev/null 2>&1 || useradd -m -s /bin/bash blog
printf 'blog ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/blog
chmod 440 /etc/sudoers.d/blog
passwd -l blog                                  # lock password (keys only)
install -d -m 700 -o blog -g blog /home/blog/.ssh
printf '%s\n' 'ssh-ed25519 AAAA... you@laptop' >> /home/blog/.ssh/authorized_keys  # <-- your pubkey
chmod 600 /home/blog/.ssh/authorized_keys
chown -R blog:blog /home/blog/.ssh
```

## 3. Sysctl: rootless low ports + non-local bind for sshd

`ip_unprivileged_port_start` lets rootless containers bind 80/443 (Caddy).
`ip_nonlocal_bind` lets `sshd` bind `ListenAddress=<tailnet IP>` (step 7) even
before `tailscale0` has that address at boot — **without it, a reboot leaves
`sshd` unable to start and you're locked out** (recover via the Hetzner console:
reset root password → web Console → remove `20-tailnet-only.conf` → restart ssh).

```sh
cat > /etc/sysctl.d/99-rootless-ports.conf <<'EOF'
net.ipv4.ip_unprivileged_port_start=80
net.ipv4.ip_nonlocal_bind=1
EOF
sysctl --system
```

## 4. Unattended upgrades

```sh
cat > /etc/apt/apt.conf.d/52unattended-upgrades-local <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:30";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF
systemctl enable --now unattended-upgrades
```

## 5. Tailscale

```sh
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --ssh=false --hostname=blog --auth-key='tskey-auth-...'   # <-- your key
tailscale ip -4        # note the 100.x.y.z address — call it TS_IP below
```

`--ssh=false` is deliberate: we use plain `sshd` over the tailnet, not Tailscale
SSH (decision: ADR-0003 / N6.2).

## 6. ⚠️ VERIFY tailnet SSH — from your laptop, BEFORE locking down

In a **new** terminal on your laptop (leave the root session open!):

```sh
ssh blog@TS_IP          # must succeed with your key
```

**Do not continue until this works.** If it fails, fix it (key in step 2, ACL,
`tailscale status`) while you still have public SSH.

## 7. ⚠️ SSH hardening + bind to the tailnet (the lock-down step)

Only after step 6 passes. This is what removes public SSH.

```sh
cat > /etc/ssh/sshd_config.d/10-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
AuthenticationMethods publickey
EOF

# Bind sshd to the tailnet address only.
printf 'ListenAddress %s\n' "$(tailscale ip -4)" > /etc/ssh/sshd_config.d/20-tailnet-only.conf

sshd -t && systemctl restart ssh      # sshd -t MUST pass before the restart
```

`PermitRootLogin no` means root SSH is gone after this — you operate as `blog`
from now on (step 2 gave it sudo + your key). After the restart, **re-verify**
`ssh blog@TS_IP` from your laptop before closing the fallback session.

## 8. Rootless Podman: linger + auto-update

Run **as the `blog` user** — after step 7 you reach the box as `blog` over the
tailnet, so run these in that session. Do **not** use `sudo -iu blog`:
`systemctl --user` needs your live login's D-Bus / `XDG_RUNTIME_DIR`, which the
sudo wrapper doesn't provide (you'd get "Failed to connect to user scope bus").

```sh
sudo loginctl enable-linger blog       # this part needs root; blog has NOPASSWD sudo
echo "$XDG_RUNTIME_DIR"                 # expect /run/user/<uid>; if empty, reconnect `ssh blog` and retry
systemctl --user enable --now podman-auto-update.timer
```

## 9. Verify rootless Podman works as `blog`

As the `blog` user (no sudo):

```sh
podman info | head
podman run --rm hello-world
```

## Done — the box is now N6.2-equivalent

Now safe to:
- `tofu import` + `apply` (the firewall attaches; public 22 drops, tailnet SSH stays).
- Lay down the app stack: podman secrets (N6.3), quadlets (N6.4/N6.5), the deploy
  timer (N6.6), observability (N6.7) — all as the `blog` user under
  `~/.config/containers/systemd/` and `~/.config/systemd/user/`.

If you ever rebuild from scratch, the canonical recipe is the cloud-init itself
(it runs automatically on a fresh box); this doc is only for adopting one that
already exists.
