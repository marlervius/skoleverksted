# Norskverksted

Norskverksted is the independently hosted language product at
https://norskverksted.vercel.app. Skoleverksted continues to serve all three
modules at its existing URLs. Both products use the same repository and
Render backend; there is no copied generation engine or second data store.

## Frontend project

Create the Vercel project `norskverksted` in the same team as Skoleverksted,
connect `marlervius/skoleverksted`, use production branch `main`, select Next.js,
and set root directory `MateMaTeX/frontend`. Use the default build settings.
Set the non-secret environment variable `NEXT_PUBLIC_SITE_EDITION=norsk` for
Production and Preview. `NEXT_PUBLIC_API_URL` may point to
`https://skoleverksted-api.onrender.com`; this is also the production default.
No mathematics proxy secret is required by the language frontend.

Leave `NEXT_PUBLIC_SITE_EDITION` unset on the existing Skoleverksted projects.
Changing this public build variable requires a rebuild. Do not share `.vercel`
link state between the projects when deploying from the CLI.

The standalone site exposes `/`, `/verksted`, and `/personvern`. `/norsk`
redirects to `/verksted` while retaining query parameters. Other application
pages and local API proxy routes return HTTP 404. Static Next.js assets remain
available. This is product routing; backend access control remains authoritative.

## Backend and pilot access

The shared backend's explicit production CORS allowlist includes
`https://norskverksted.vercel.app`; no wildcard is needed. Keep the existing
Render service, access code, model configuration and export controls.
Custom or preview domains need their own explicit CORS origin before use.

The landing page and privacy notice are public. The workspace still requires
the shared pilot access code. Each frontend origin has its own browser storage
and login session. Server-side jobs and files still belong to the shared pilot
workspace. This release does not introduce customer accounts, tenant isolation,
billing, or a commercial hosting plan; the privacy page states that limitation.

## Verify and publish

Run frontend tests, lint, TypeScript and production builds for both editions.
For local language preview, set `NEXT_PUBLIC_SITE_EDITION=norsk` and run
`npm run dev` from `MateMaTeX/frontend`. Clear that variable when previewing
the complete Skoleverksted. Run backend CORS, access-gate and smoke regression
tests as well as the existing language/export tests.

After pushing the verified branch and merging to `main`, wait for GitHub CI,
both existing Vercel projects, the new Norskverksted project, and Render.
The production smoke workflow checks the new site's pages and ensures that
Fag, Matematikk, shared history and mathematics proxies remain unavailable on
the language host. It also continues to check all three Skoleverksted modules
and the backend access gate. `SMOKE_LANGUAGE_FRONTEND_URL` overrides the new
site's URL for testing. Signed-in smoke uses the existing optional
`SMOKE_ACCESS_CODE`; do not weaken the gate when that secret is unavailable.
