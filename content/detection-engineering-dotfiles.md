---
title: Trying out detection engineering
slug: trying-out-detection-engineering
date: 2026-07-25
kind: essay
tags: [software-engineering]
status: published
---

_Detection engineering at laptop scale, with auditd, Sigma, and Atomic Red Team._

This week I did something slightly odd to my dotfiles repo: I taught it to detect attacks against itself.

I'd been reading about detection engineering for a while, Sigma rules, ATT&CK mappings, purple-team write-ups. I keep being told my next role will involve detection engineering aspects as well as detection-as-code. I wanted to try it out, but on what...?

Reading about Sigma is not the same as debugging why a rule doesn't fire. I know from experience that the gap between "I understand this concept" and "I have made this work at 11pm" is where all the real knowledge lives. So I wanted a lab I fully own, with telemetry I can read, rules I wrote myself, and a way to prove they work. The smallest honest version of that turned out to be my laptop.

I chose my [dotfiles](https://github.com/jasonbirchall/dotfiles). If you look at what a dotfiles repo manages: `~/.ssh`, shell rc files, systemd user units. Now look at the ATT&CK persistence techniques for Linux that don't need root: SSH authorized keys ([T1098.004](https://attack.mitre.org/techniques/T1098/004/)), shell configuration modification ([T1546.004](https://attack.mitre.org/techniques/T1546/004/)), systemd user services ([T1543.002](https://attack.mitre.org/techniques/T1543/002/)). It's the same list. The repo that installs those files already knows exactly what they should look like, so it's the natural home for the machinery that notices when they change. Detection as code, in the most literal sense: the rules, the tests, and the linting all live in version control next to the files they defend.

## The shape of the thing

Have a nosey around the dotfiles using the link above.

There are two halves: 1. collection is dumb, 2. detection is opinionated.

Collection is a handful of auditd file watches on the persistence surfaces:

```
## SSH — keys, authorized_keys, config (directory watches are recursive)
-w @HOME@/.ssh -p wa -k ssh-tamper

## Shell rc files (bash)
-w @HOME@/.bashrc -p wa -k rc-tamper
-w @HOME@/.bash_profile -p wa -k rc-tamper
-w @HOME@/.profile -p wa -k rc-tamper

## systemd user units
-w @HOME@/.config/systemd/user -p wa -k systemd-user-tamper
```

`-p wa` means writes and attribute changes. Deliberately no `r` — every ssh and git invocation reads these files, and watching reads would drown the log in noise. (The `@HOME@` placeholder is rendered at install time; audit rules are system-wide and know nothing about `~`.) There are also watches on `/etc/audit` itself, because the first thing a competent attacker does to an audit setup is turn it off.

Detection is seven [Sigma](https://sigmahq.io/) rules that turn those raw audit records into named, ATT&CK-tagged alerts. Nothing here ships to a SIEM, it's going to alert on a laptop. [Zircolite](https://github.com/wagga40/Zircolite) reads `/var/log/audit/audit.log` directly, matches my rules against it, and writes findings to `~/.local/state/sigma-scan/`. I love a good Makefile operation, so `make sigma-scan` is the whole pipeline end-to-end.

There is a sigma-ci that runs as a pre-commit hook, so a rule that doesn't parse can't land in the repo. That's part of the detection-as-code principle.

## One rule, end to end

Here's the highest-severity rule, the one watching `authorized_keys`:

```yaml
title: SSH authorized_keys Written Or Deleted
status: experimental
description: >
    A PATH record under the ssh-tamper watch touched an authorized_keys file.
    Adding a key here grants persistent remote access, so this fires on any
    writer — including tools allowlisted by the companion SYSCALL rules.
references:
    - https://attack.mitre.org/techniques/T1098/004/
tags:
    - attack.persistence
    - attack.t1098.004
logsource:
    product: linux
    service: auditd
detection:
    selection:
        type: PATH
        name|contains: authorized_keys
    filter_parent_dir:
        nametype: PARENT
    condition: selection and not filter_parent_dir
falsepositives:
    - Deliberately adding a key for a new machine
level: high
```

Two things I like about Sigma after actually using it. First, the rule is honest about its own weaknesses: the `falsepositives` block is a first-class field, not a comment, and it's the first thing I read when an alert fires. Second, the ATT&CK tags mean my little seven-rule laptop setup can be as verbose as you like it. When the rule fires I'm not looking at "file changed", I'm looking at "persistence, T1098.004" — and every write-up, mitigation note, and threat report about that technique is one search away in the Mitre lookup. An alert without a clear instruction isn't useful in my opinion.

One gotcha worth knowing if you try this: I write rules directly against the field names Zircolite flattens auditd records into (`type`, `key`, `comm`, `name`). There's no pySigma pipeline translating generic field names in the middle. That keeps the setup simple. What you see in the YAML is what matches the log, but it does couple the rules to Zircolite's flattening. I decided I'd rather have rules I can trace by eye than portability I don't currently need.

## The tests are where the learning happened

A rule that parses is not a rule that works. So every rule has a test: a script that performs the malicious action, runs the scan, and asserts the rule matched an event produced _after_ the trigger fired. Where [Atomic Red Team](https://github.com/redcanaryco/atomic-red-team) has an atomic for the technique, the test is adapted from it, and carries the atomic's ID in its metadata. `make sigma-test` runs the lot; cleanup runs on an `EXIT` trap, so a test that dies half-way still restores whatever it touched.

This is the part I'd defend hardest. Writing the tests taught me two things about my own machine that I would have got completely wrong from the rule text alone.

**The obvious `.bashrc` attack doesn't work here.** Atomic Red Team's T1546.004 atomic does the classic move: `echo 'evil' >> ~/.bashrc`. On my machine that fails with `EACCES` and produces _no audit event at all_. My rc files are [home-manager](https://github.com/nix-community/home-manager) symlinks into the read-only nix store; there's no writable inode to append to, and a syscall that fails at permission check before touching the watched file never reaches the audit subsystem. If I'd shipped the stock atomic as my test, it would have failed, and my first guess would have been a broken rule rather than a mispointed attack. The real tamper vector on a nix-managed home is replacing the symlink: `rm ~/.bashrc` and drop a hostile file in its place, and it's the `rm` that trips the watch. So that's what my test does. It's a more honest test than the official atomic, _for this machine_. (It also means the nix store is quietly doing prevention while auditd does detection, which I hadn't fully appreciated until the test forced me to trace the syscall path.)

**The stock systemd atomic tests the wrong threat.** Atomic Red Team's T1543.002 atomic writes a unit to `/etc/systemd/system` — system-wide, root-owned. But if an attacker already has root, my laptop is lost; the game here is catching persistence _before_ privilege escalation. The place an unprivileged attacker plants a unit is `~/.config/systemd/user`, so that's where my watch is, and my test overrides the atomic's path to match. Same technique ID, different location, and the difference is the entire point.

Neither of these is a criticism of Atomic Red Team. The atomics are generic by design. The lesson is that detections and their tests are local. You can import a technique catalogue; you can't import knowledge of your own domain.

## What I deliberately didn't do

Zircolite bundles roughly 180 community Sigma rules for Linux. I'm running none of them. That was the hardest restraint to hold, because turning them on feels like progress. Look ma, 180 detections! I'd be running rules I didn't write, over telemetry I'm mostly not collecting, with false-positive profiles I don't know. I already know from a dry look at the set that at least two would misfire immediately on this machine: "Disable System Firewall" (I stop firewalld routinely) and "Use Of Hidden Paths Or Files" (it would re-detect my own dotfile watches, which has a certain poetry to it, but no).

So the current phase is deliberately small: seven rules I fully understand, over file-watch telemetry only. I want to learn the false-positive rhythm of my own machine. What home-manager activation looks like in the audit log, what a package upgrade looks like, on a set where I can explain every alert. The next step, when I'm ready, is enabling execve auditing, which by my count lights up about three-quarters of the bundled ruleset at once. I don't know yet what that does to log volume on this box. That's a future post, probably.

The thing I keep coming back to is how well the whole discipline scales down. Detection engineering sounds like something you need a SIEM, a team, and a budget for. It turns out the loop: pick a technique, collect the telemetry, write the rule, attack yourself, watch it fire, fits on one laptop, in one repo, next to the config it protects. The tooling is free and the attacks are scripted. The only expensive part is the thing you actually wanted: knowing, specifically and testably, what your own machine looks like when something is wrong.
