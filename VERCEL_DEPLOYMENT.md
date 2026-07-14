# Deploy frontend on Vercel Hobby

The frontend is a full Next.js application with server-side API routes. Deploy
it as a Vercel project, not as a static export. The backend remains on Render.

## Create the project

1. In Vercel, choose **Add New > Project** and import
   `marlervius/skoleverksted`.
2. Set **Root Directory** to `MateMaTeX/frontend`.
3. Keep the detected **Next.js** framework and default build settings.
4. Select the Hobby plan for the test phase.
5. Add these environment variables for Production and Preview:

```env
NEXT_PUBLIC_API_URL=https://skoleverksted-api.onrender.com
BACKEND_INTERNAL_URL=https://skoleverksted-api.onrender.com
MATE_API_KEY=<same generated value as the Render backend>
```

Use the actual Render hostname if it differs. `MATE_API_KEY` is server-only and
must never be prefixed with `NEXT_PUBLIC_`.

The checked-in `vercel.json` enables Fluid Compute and places server functions
in Frankfurt, close to the Render backend. Long proxy routes explicitly allow
the Hobby maximum of 300 seconds. Heavy AI and PDF work still runs on Render.

## Connect CORS after the first deploy

Vercel assigns the public frontend URL after creation. Copy the production URL
and update the Render backend environment:

```env
FRONTEND_URL=https://your-project.vercel.app
ALLOWED_ORIGINS=https://your-project.vercel.app
```

Then redeploy/restart the Render backend. Fag, Norsk and the shared project API
call Render directly from the browser and therefore require the exact origin.
Vercel preview URLs are not included automatically; use the production URL for
end-to-end testing unless a specific preview origin is added to
`ALLOWED_ORIGINS` as a comma-separated additional value.

## Smoke test

After both deployments are live:

1. Open the Vercel production URL and switch between all three modules.
2. Create a ThemePack and confirm that the project appears under Projects.
3. Start one small generation in Fag, Norsk and Matematikk.
4. Confirm that `/health/ready` on Render returns HTTP 200.

Hobby is intended for personal/non-commercial testing and has usage limits.
Reassess the plan before organizational school use.
