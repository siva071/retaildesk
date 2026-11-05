# Deploying RetailDesk — 100% Free Tier

Architecture when deployed:

```
 Vercel  ── serves the static UI (app/static/)
    │  browser calls the API cross-origin (CORS is enabled)
    ▼
 Render  ── runs the FastAPI backend (free web service)
    │
    ▼
 Neon    ── free PostgreSQL database
```

You need three free accounts: [neon.tech](https://neon.tech),
[render.com](https://render.com), [vercel.com](https://vercel.com), and this
project pushed to your GitHub (all three connect to GitHub).

---

## Step 1 — Database on Neon (free PostgreSQL)

1. Sign up at **neon.tech** → **New Project**.
2. Name it `retaildesk`, pick a region close to you (e.g. AWS Asia / Mumbai
   or Singapore), create the project.
3. On the project dashboard, find **Connection string**. It looks like:
   `postgresql://user:password@ep-something.aws.neon.tech/neondb?sslmode=require`
4. Copy it and keep it aside — you'll paste it into Render in Step 2.
   **You don't need to edit it.** RetailDesk automatically converts
   `postgresql://` (or `postgres://`) into the `postgresql+psycopg2://`
   form SQLAlchemy needs, and passes `sslmode=require` through.

> Tables are created automatically the first time the app starts
> (`Base.metadata.create_all`), so there is no migration step.

## Step 2 — Backend on Render (free web service)

1. Push this repo to your GitHub first.
2. Render dashboard → **New → Web Service** → connect the repo.
   (Or **New → Blueprint** and Render reads `render.yaml` from the repo —
   then you only need to fill in `DATABASE_URL`.)
3. Settings:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
     (this is also in the `Procfile`)
   - **Instance type:** Free
4. **Environment variables** (Render → Environment):
   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | the Neon connection string from Step 1 (paste as-is) |
   | `SECRET_KEY` | a long random string (or let Render generate one) |
   | `ALLOWED_ORIGINS` | `*` for the demo — or your Vercel URL later for tighter security |
5. Deploy. When it's live you'll get a URL like
   `https://retaildesk-api.onrender.com`.
   Check it: open `https://<your-url>/api/health` → `{"status":"ok",...}`,
   and `https://<your-url>/docs` for the Swagger UI.

> ⚠️ **Render free-tier sleep caveat (honest note):** free web services
> spin down after ~15 minutes without traffic. The **first request after
> that takes ~30–50 seconds** while the service wakes up; afterwards it's
> fast again. If a recruiter's first click feels slow, that's the free
> tier, not the app. Opening the `/api/health` link once "warms it up".

## Step 3 — Seed the hosted database (one time)

The hosted DB starts empty. Run the seed **once** from your own computer,
pointing it at Neon:

```bash
# in the retaildesk/ folder, with dependencies installed:
DATABASE_URL='postgresql://user:password@ep-....aws.neon.tech/neondb?sslmode=require' python seed.py
```

That creates the demo store, products, customers and sample bills in Neon.
(Same `DATABASE_URL` value you gave Render. Re-running is safe — the seed
exits if the demo data already exists.)

Demo logins afterwards: owner `demo@retaildesk.in / demo1234`,
staff `staff@retaildesk.in / staff1234`.

## Step 4 — Frontend on Vercel

Option A (simplest): **skip Vercel entirely** — FastAPI already serves the
UI. Your Render URL *is* the full app (UI + API, same origin). Done.

Option B (split hosting, UI on Vercel):

1. In `app/static/config.js`, set the API base to your Render URL:
   ```js
   window.API_BASE = "https://retaildesk-api.onrender.com";
   ```
   and commit/push that change.
2. Vercel dashboard → **Add New → Project** → import the same repo.
3. Set **Root Directory** to `app/static` (that's the folder with
   `index.html`). Framework preset: **Other**. No build command, no
   environment variables.
4. Deploy → you get `https://retaildesk-xxxx.vercel.app`. Open it and log
   in with the demo credentials. The page loads from Vercel; every API
   call goes to Render (this works because the backend enables CORS via
   `ALLOWED_ORIGINS`).
5. Optional tightening: back in Render, set `ALLOWED_ORIGINS` to exactly
   your Vercel URL instead of `*`, and redeploy.

> Why it works without code changes: all asset paths in the UI are
> relative and every fetch goes through the single `API_BASE` value —
> `""` (same-origin) for FastAPI-served, the Render URL for Vercel.

## Updating later

- **Code change:** push to GitHub → Render and Vercel auto-redeploy.
- **Reset demo data:** Neon dashboard → your database → delete the tables
  (or drop/recreate the DB), restart the Render service (tables recreate
  on boot), re-run Step 3.
- **Real use:** change `SECRET_KEY`, change the demo passwords (or delete
  the demo users), and set `ALLOWED_ORIGINS` to your real frontend origin.
