# 6. Do not embed the Electricity Maps web app

Date: 2026-08-22 · Status: Accepted

## Context

The brief asks for "an experimental integration point for the existing Electricity Maps web
experience where legally/technically appropriate". `PROJECT_CONTEXT.md` section 13 already
cautions against making an iframe or redirect a core dependency without verifying
feasibility.

It was verified. On 22 August 2026, `https://app.electricitymaps.com/` responds with:

    Content-Security-Policy: frame-ancestors 'self' https://*.alignedup.com/ https://*.teamaligned.com/

Our origin is not in that list, so the browser will refuse to render the app in a frame. No
official embed widget or oEmbed endpoint was found either.

Separately, `electricitymaps-contrib` — which contains the zone geometries — is AGPL-3.0.
Pulling that GeoJSON into a hosted web app is arguably network-copyleft territory.

## Decision

1. **No iframe.** The integration point is a set of deep links that open the relevant
   Electricity Maps view in a new tab, alongside our own rendering of the same data.
2. **No `electricitymaps-contrib` geometry.** If this project ever needs boundaries, use
   Natural Earth (public domain).
3. The API Playground and Developer Hub remain useful as *developer* reference surfaces.
   They are not part of the product.

## Consequences

- Goal 4 of the brief is met in a form that actually works in a browser, rather than one
  that fails silently behind a CSP error in the console.
- We render everything ourselves, which we were going to do anyway.
- Worth saying out loud at the event: having checked the framing headers and the licence
  before building is the kind of thing that distinguishes a project from a prototype.

## Reverse this if

Electricity Maps adds our origin to `frame-ancestors`, or ships an embed product. Re-check
the header before assuming; it is one `curl -I` away.
