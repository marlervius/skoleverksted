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

Norskverksted is temporarily open without a code. The standalone frontend asks
for `/api/platform/access/status?module=norsk`, and only the explicitly listed
language generation routes and new `open-<UUID>` job capability links are open.
Existing pilot job IDs, private project bindings, the shared job index and all
other modules still require the pilot code. Source checks, teacher approval,
export gates and generation rate limits still apply. Do not publish job links
containing private work: anyone with an open job link can read or approve it.

To restore the code, set the non-secret backend setting `NORSK_OPEN_ACCESS=0`
and redeploy Render. No secret needs to change; the frontend will ask for the
code again from the server's status response. Also update the landing/privacy
copy and change the smoke assertions for the deliberate closed-pilot state.
Each frontend origin has its own browser storage. This release does not add
customer accounts, billing or a commercial hosting plan.

## Verify and publish

Language generation uses three bounded AI roles in the existing Python truth
pipeline: a claim mapper inventories decoded document nodes, a source researcher
discovers authoritative pages whose snapshots are fetched independently, and a
corrector checks those snapshots and proposes anchored corrections. The mapper's
obligations cannot be silently omitted or reclassified by the corrector. Both
must explicitly cover every non-empty document leaf. Agreement alone never
approves facts: unavailable sources, missing obligations, cancellation and time
limits retain the existing fail-closed behavior. Corrected candidates go through
all three roles again before source approval, followed by the teacher's approval
of the exact revision. Other modules keep their existing verification flows.

The roles reuse the configured Google model and credentials; no new service or
secret is needed. Compared with the previous research-and-assessment flow, each
language audit round adds one inventory model call. The existing overall time,
retry and revision budgets still apply. Progress reports identify each role.
Offline regression coverage is in
`Skoleverksted/backend/tests/test_language_fact_crew.py`; these tests make no
paid model calls. A real model quality evaluation remains a separate manual run.

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
