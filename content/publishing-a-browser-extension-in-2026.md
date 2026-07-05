---
title: Some notes on actually publishing a browser extension in 2026
slug: publishing-a-browser-extension-in-2026
date: 2026-07-05
kind: essay
tags: [software-engineering]
status: published
---

This week I finally sat down and did something I've been meaning to do for ages: build and publish a browser extension. Maybe that doesn't sound thrilling, but I wanted to get my hands dirty with TypeScript, figure out what actually separates manifest V2 from V3, and see what it's like to ship software when you don't control the gates. I needed to make something real, something I might actually use, and something I could come back to and improve later.

My idea isn't new or flashy, but it's useful to me. I use RSS all the time, mostly with [Newsboat](https://newsboat.org/) in the terminal, to keep up with people I actually want to hear from. I'm talking about blogs like [Simon Willison's](https://simonwillison.net/), [Lorin Hochstein's](https://surfingcomplexity.blog/), and [Daniel Stenberg's](https://daniel.haxx.se/blog/). Their writing keeps me interested and makes me think. There are plenty of RSS readers out there, including browser extensions, but they all expect you to keep track of every single feed URL. Why can't my bookmarks menu just tell me when there's something new to read?

So I set out to see if I could make that work. I built [Feedmark](https://codeberg.org/jasonbirchall/feedmark) because I wanted a simple RSS reader that just uses a bookmarks folder as the subscription list. One place to manage, one source of truth. I don't want to juggle a bookmarks list and a separate feed list.

I decided it should:

- Use my current list of bookmarks as a source of truth (as mentioned)
- Attempt to find the feed from the blog homepage. Many authors put the feed URL in their HTML headers, so this was fairly easy to find.
- Never trust a feed on a different domain from the blog itself. Auto-following a cross-origin feed is an easy way to invite trouble, XSS included.

I knew I wanted to upload this extension to multiple browser extension stores. I was curious to see the differences in platform ease of use, where the tooling starts and ends, and how verbose and developer-friendly each ecosystem is. [Firefox AMO](https://addons.mozilla.org/) was the obvious choice for me as Firefox is my daily driver. [Google Chrome Web Store](https://chromewebstore.google.com/) was my next choice as [most people use Chrome](https://gs.statcounter.com/browser-market-share/desktop/worldwide).

I've worked on all sorts of platforms over the years, so I pay close attention to how clear the docs are, whether the tooling actually helps from start to finish, and how painful it is to debug when things go wrong. I was curious to see how two browser giants moderate third-party code from completely unknown developers. I'm not here to judge them (yet!). This post just walks through exactly how I published to each store, how I tried to automate the steps, and what I'd change if I started from scratch.

I checked all of this against the official pages in July 2026. This stuff changes fast. One of the stores swapped out its entire publishing API just last year. If you're reading this later, trust the links, not me. This post is just the map.

## Before either store

Four things to sort out before you touch a submission form:

**AMO requires a data-collection declaration inside `manifest.json`.** Since November 2025, [new extensions are refused signing without one](https://blog.mozilla.org/addons/2025/10/23/data-collection-consent-changes-for-new-firefox-extensions/). If your extension collects nothing, the whole declaration is:

```json
"browser_specific_settings": {
  "gecko": {
    "data_collection_permissions": { "required": ["none"] }
  }
}
```

I put this in the manifest, not a policy page, because Firefox checks it during install. The install dialogue shows exactly what you declared. Since Feedmark doesn't collect data, I set it to 'none'. That privacy claim stays with the extension. If your extension does collect data, check the [data-consent docs](https://extensionworkshop.com/documentation/develop/firefox-builtin-data-consent/) for the full list of values.

**If you want a single manifest for both browsers, set a minimum Chrome version.** Firefox wants `background.scripts`, Chrome wants `background.service_worker`. I tested this: you can include both, but Chrome only ignores the Firefox one from version 121 onwards. Older versions just refuse to load the extension. Set [`"minimum_chrome_version": "121"`](https://developer.chrome.com/docs/extensions/reference/manifest/minimum-chrome-version) so the store blocks incompatible users up front. I only found this behaviour documented on [MDN's background page](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background), not in Google's docs. There is no war in Ba Sing Se.

You'll probably need a hosted privacy policy. Google treats any website content your extension stores locally as ['user data'](https://developer.chrome.com/docs/webstore/program-policies/user-data-faq). If your extension fetches and saves anything, as mine did, you need a policy URL. You can't just link to a Git repo, but you can use a static page on GitHub Pages or something similar. I used [a single HTML file](https://codeberg.org/jasonbirchall/feedmark/src/branch/main/store/privacy-policy.html) on Codeberg Pages. Copy my structure if you want.

**Your zip file needs `manifest.json` at the root.** Don't zip the build directory itself; zip its contents. I messed this up and wasted more time than I want to admit.

```sh
# wrong: everything ends up under dist/ inside the archive
zip -r extension.zip dist/

# right: cd in first, so manifest.json lands at the archive root
(cd dist && zip -r ../extension.zip .)
```

Check before you upload. The first column of paths should start with your files, no directory prefix.

```sh
unzip -l extension.zip
# ...
#      989  07-03-2026 15:53   manifest.json <- at the root, good
```

Both stores are picky about [version number format](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/version): dot-separated numbers, no leading zeros, no suffixes.

## AMO

1. You'll need a Mozilla account, then set up 2FA. [That's mandatory for extension developers](https://blog.mozilla.org/addons/2021/03/11/two-factor-authentication-required-for-extension-developers/). Only TOTP apps work here. [Mozilla accounts don't support WebAuthn](https://support.mozilla.org/en-US/kb/secure-firefox-account-two-step-authentication), so if you use a hardware key, it has to go through its authenticator applet, not the touch flow. I tend to lean into hardware tokens where I can, but in this instance, it wasn't possible. Ooh, don't forget to save your backup codes.

2. Accept the Developer Agreement in the [Developer Hub](https://addons.mozilla.org/developers/) before you do anything else. If you skip this, the API will just refuse your submissions, and it'll no doubt confuse you as to why. This is the classic first-CI-run failure. Start a manual submission following the [submission guide](https://extensionworkshop.com/documentation/publish/submitting-an-add-on/), accept the agreement when it appears, then abandon the upload.

3. If your code is bundled or minified (TypeScript through Rollup counts here), you need to prepare a source package. [The rules](https://extensionworkshop.com/documentation/publish/source-code-submission/) require your complete source code, the lock file, and a README that lists the exact tool versions and the commands to build your extension. The reviewer will follow your README and diff the result against your submitted file, expecting zero differences. Test this yourself first. I use [a make target called `verify-build`](https://codeberg.org/jasonbirchall/feedmark/src/branch/main/Makefile) that rebuilds from a clean git archive and runs `diff -r`. It lives in the CI, so every push proves the build is reproducible before Mozilla ever checks it. [My README](https://codeberg.org/jasonbirchall/feedmark/src/branch/main/BUILDING.md) is a working example of what the reviewer package should contain. The default build box runs Node 24. If you need something else, say so in your README.

4. Get your API credentials from the [API key management page](https://addons.mozilla.org/developers/addon/api/key/). You'll see a JWT issuer like `user:12345:67` and a long hex secret. Store these in your CI secret store. The [auth docs](https://mozilla.github.io/addons-server/topics/api/auth.html) explain the details if you want to dig in. There's no OIDC or trusted-publishing option, so the secret sticks around for a long time. I'm not a fan, but that's a topic for another day.

5. Submit with [web-ext](https://extensionworkshop.com/documentation/develop/web-ext-command-reference/). Coming from a platform background, pushing the developer tooling left feels like the right thing to do. Use:

    ```sh
    web-ext sign \
      --source-dir=dist \
      --channel=listed \
      --amo-metadata=amo-metadata.json \
      --upload-source-code=source.zip \
      --approval-timeout=0
    ```

Use the credentials in Actions secrets `WEB_EXT_API_KEY` and `WEB_EXT_API_SECRET`. [My release workflow](https://codeberg.org/jasonbirchall/feedmark/src/branch/main/.forgejo/workflows/release.yml) wires the whole thing into a tag-triggered pipeline: version guard, tests, reproducibility proof, then the sign step with the secrets scoped to it alone. I use Forgejo Actions, but it reads just like GitHub Actions. The metadata JSON is required on your first submission. At minimum, you need [categories](https://mozilla.github.io/addons-server/topics/api/categories.html), a summary, and a license from [the approved list](https://mozilla.github.io/addons-server/topics/api/licenses.html).

```json
{
    "categories": ["feeds-news-blogging"],
    "summary": { "en-US": "One sentence about what it does." },
    "version": { "license": "Apache-2.0" }
}
```

([Mine, with the approval notes included](https://codeberg.org/jasonbirchall/feedmark/src/branch/main/amo-metadata.json), if you want a complete one to start from.)

Not many people mention this, but the version object also takes [`"approval_notes"`](https://mozilla.github.io/addons-server/topics/api/addons.html). Only Mozilla reviewers see this field. I use it to explain the data-collection declaration and the broad host permission, so every future submission includes the explanation automatically.

6. `--approval-timeout=0` makes the command fire-and-forget. It returns as soon as AMO accepts the upload. Validation, signing, and review all happen on their side. If you submit source code, it goes to a smaller admin pool and can take longer. Mine still came back within a day.

Afterwards, fill in the listing in the Developer Hub by hand: description, support site, and the privacy policy link if you have one. web-ext's metadata file can carry some of these fields too, but I haven't wired that up yet.

Things that bit me: `Error decoding signature` from the api. A classic bad paste :/. And version numbers are consumed on upload, so if a submission dies after uploading, bump the patch number rather than retrying the same version.

## Chrome Web Store

1. Choose the Google account deliberately; [its email is permanent](https://developer.chrome.com/docs/webstore/register). You can't change it later; migrating means creating a new account and transferring the item. Enable [2-Step Verification](https://developer.chrome.com/docs/webstore/program-policies/two-step-verification) before anything else (hardware security keys work fine here).

2. Register and pay the one-time $5 fee; I guess this helps prevent spam accounts. Verify a contact email in the [dashboard's Account page](https://developer.chrome.com/docs/webstore/set-up-account), and make the EU Digital Services Act [trader declaration](https://developer.chrome.com/docs/webstore/program-policies/trader-disclosure). For a free personal extension, non-trader is the natural answer; trader details get displayed publicly to EU users. I found this difficult to understand at first.

3. The first upload is manual, by design. The current API ([v2](https://developer.chrome.com/docs/webstore/using-api)) can update extensions but cannot create one. So it's [the dashboard](https://chrome.google.com/webstore/devconsole) → Add new item → your zip, per the [publish guide](https://developer.chrome.com/docs/webstore/publish). If you request broad host permissions, an "in-depth review" warning appears at upload. That's expected; don't try to make it go away by weakening the extension.

4. In the [store listing tab](https://developer.chrome.com/docs/webstore/cws-dashboard-listing), fill in the description, category, and language. For assets, follow the [image specs](https://developer.chrome.com/docs/webstore/images): a 128px icon (Google wants 96×96 artwork with 16px transparent padding), at least one screenshot at exactly 1280×800 or 640×400. I found this to be a little strict and had to reach for a conversion tool. The screenshot spec says JPEG or 24-bit PNG without alpha. macOS screenshots have an alpha channel, so the form will reject them. Just export as JPEG and the form will accept it.

5. The [privacy tab](https://developer.chrome.com/docs/webstore/cws-dashboard-privacy) is worth taking your time on. You need a single-purpose statement, a written justification for each permission, a remote-code declaration, the data-usage checkboxes, and your privacy policy URL. I recommend drafting the justifications in a file first. [Mine is public](https://codeberg.org/jasonbirchall/feedmark/src/branch/main/store/chrome-listing.md), with one section per dashboard field. The broad-host-permission justification matters most, since a human reviewer will read it. For data usage, [locally-stored website content counts as collected](https://developer.chrome.com/docs/webstore/program-policies/user-data-faq), so answer honestly and certify all three disclosures.

6. Distribution tab: visibility, pricing (free), regions. There's also a deferred-publishing toggle — approval then doesn't auto-publish, and you get 30 days to press the button yourself. Tick it if you care about the go-live moment.

7. Submit and then wait. The [review process page](https://developer.chrome.com/docs/webstore/review-process) says (as of April 2026) that queues are long. If you request broad host permissions and use a new developer account, expect to wait weeks. Resubmitting won't speed things up. The only official word is that reviews can take even longer after a rejection. I imagine I'll be waiting for a review for a while. Safety first.

8. For updates later, automate against [API v2 only](https://developer.chrome.com/docs/webstore/using-api). [API v1 shuts down on 15 October 2026](https://developer.chrome.com/blog/cws-api-v2), but most CI actions still target it. Manifest V3 is the extension format, not the publishing API version. The store's publishing API has its own version numbers, and the current one is v2. For CI authentication, Google recommends a [service account](https://developer.chrome.com/docs/webstore/service-accounts). You create it in a Google Cloud project, then register it in the dashboard's Account page. You can register at most one per publisher, and it is shared by all your extensions. The older OAuth refresh-token flow still works if you do not want to use Google Cloud.

## The order matters

If I had to do this again without notes, I'd still start with AMO. The validator replied in minutes and signing took a day, so my artefact got debugged while Chrome's queue was still warming up. By the time Chrome asked for screenshots and justifications, the extension was already live somewhere real. That's useful, and a big morale boost.

And what would I change? I'd have the privacy policy and the screenshots ready before opening Chrome's forms, instead of scrambling for them mid-submission. I'd paste the API secrets more carefully. And I'd bump the manifest version before pushing the tag; I forgot once, and the only thing between me and a broken release was the version guard in my pipeline. Build that guard before your first release, not after.

## The whole thing, as a checklist

1. Put the data-collection declaration and `minimum_chrome_version` in your manifest.

2. Host a privacy policy somewhere stable.

3. Build a zip with `manifest.json` at the root.

4. AMO: create the Mozilla account, set up TOTP 2FA, accept the Developer Agreement.

5. AMO: generate API credentials and store them as CI secrets.

6. AMO: write the source package README and prove your build reproduces.

7. AMO: submit with `web-ext sign` (metadata JSON needed the first time).

8. AMO: fill in the listing in the Developer Hub.

9. Chrome: pick the Google account carefully (the email is permanent), enable 2FA, pay the $5, verify a contact email, declare trader status.

10. Chrome: make the assets — screenshots at exactly 1280×800 or 640×400, JPEG.

11. Chrome: upload by hand in the dashboard, then work through the listing, privacy and distribution tabs.

12. Chrome: submit, then wait. Automate later updates against API v2.

## The four pages I kept open

- [web-ext command reference](https://extensionworkshop.com/documentation/develop/web-ext-command-reference/); every sign flag, including the metadata schema

- [AMO source code submission](https://extensionworkshop.com/documentation/publish/source-code-submission/); the rules and the reviewer's build environment

- [CWS privacy tab guide](https://developer.chrome.com/docs/webstore/cws-dashboard-privacy); what each privacy field wants

- [CWS API v2 guide](https://developer.chrome.com/docs/webstore/using-api); endpoints and auth for the automation you'll write later
