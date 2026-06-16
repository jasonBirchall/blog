# ADR-0003: Pull-based deploy, Tailscale-only access, no fail2ban

- Status: Accepted
- Date: 2026-06-16

## Context

The original Phase 6 plan assumed a **push** deploy: CI on Codeberg holds a
restricted SSH key, connects to the VPS on every merge to `main`, pulls, and
reloads gunicorn. That shape implies three things the revised design wants to be
rid of:

- a standing credential on a CI runner that can reach the box,
- a public SSH listener (hence `fail2ban` to blunt brute-force noise),
- a dedicated deploy user scoped to `content/`.

Revised Phase 6 runs the whole site as rootless Podman on a single VPS, with
Tailscale already present for administration.

## Decision

**The box pulls; nothing pushes to it.**

1. A user-scope systemd timer (N6.6) runs `deploy/deploy.sh` every two minutes:
   `git fetch origin main`, and when it moves, `podman build`, a fatal one-shot
   (`migrate` + `sync_content`), restart the app, best-effort `snapshot_posts`,
   then ping a heartbeat. No credential on any CI runner can reach the box.
2. **SSH listens only on the Tailscale interface** (`ListenAddress` = tailnet IP,
   N6.2), with root login and password auth disabled and `tailscale up
   --ssh=false`. There is no SSH listener on the public interface.
3. **`fail2ban` is intentionally omitted.** With no public SSH and Caddy as the
   only public listener, there is no SSH brute-force surface for it to defend.
   Proxy-level abuse is Caddy's concern, and the constitution forbids logging IPs
   anyway, so IP-banning would conflict with the privacy posture.
4. The unprivileged **service user owns and `git reset --hard`s its own
   checkout** — there is no separate deploy user with `content/`-only write.

### Deploy integrity

Because the box trusts whatever `origin/main` resolves to, that tip is the entire
trust anchor. `deploy.sh` verifies it before touching the working tree, rather
than trusting it blindly:

- **Re-assert the canonical remote** (`git remote set-url origin …`) every run, so
  a tampered `.git/config` self-heals back to Codeberg before the fetch.
- **Fast-forward only** (`git merge-base --is-ancestor HEAD origin/main`): the box
  only ever moves *forward* on `main`. A force-push or history rewrite — which
  `git reset --hard` would otherwise follow backwards — is refused.
- **Signature gate** (`git verify-commit`): the tip must carry a valid signature
  from an allowed key (`gpg.ssh.allowedSignersFile` on the box), enforcing the
  constitution's signed-commits rule *at the edge* rather than by convention.

Each gate failure refuses the deploy, leaves the old image serving, and pings the
heartbeat `/fail`.

## Consequences

- Smaller attack surface: no standing box credential in CI, no public SSH to
  brute-force.
- A failed build or `sync_content` aborts before the app is touched, so the
  previous image keeps serving; failures surface via the deploy heartbeat (N6.7),
  not via an SSH session.
- Push immediacy is lost: commit→live is bounded by the 2-minute poll plus the
  build (~4 min worst case), inside the "live within five minutes" SLO.
- Administration depends on Tailscale being up. If the tailnet is unreachable the
  site still serves (Caddy is public) but the box is not administrable until
  restored; the provider's serial console is the break-glass path. Acceptable for
  a personal blog.
- The integrity gates narrow the trust surface to "the forge plus the signing
  key": moving a ref is no longer enough to deploy — an attacker must produce a
  commit signed by an allowed key. The irreducible residual risk is a compromised
  Codeberg account *or* signing key; no pull deploy can close that.
- The signature gate is fail-closed: if `gpg.ssh.allowedSignersFile` is unset or
  the key is missing, every deploy is refused (and alerts) rather than shipping
  unverified code. Provisioning must configure it — see `deploy/systemd/README.md`.
- Reversible: re-introducing a push deploy means adding a restricted SSH key, a
  listener, and a CI step — at which point this ADR is superseded.
- Supersedes the security-baseline bullets that described a CI-held SSH key, a
  `content/`-only deploy user, and `fail2ban`.
