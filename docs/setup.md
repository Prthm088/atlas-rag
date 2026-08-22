# Setup

This is the only account/credential work required after the code is complete. None of the server-only values belongs in the frontend environment or Git.

## 1. Prerequisites and free accounts

- Node.js 22.13 or newer.
- Python 3.10 or newer (3.12 is used in CI and containers).
- Docker Desktop for the container path.
- Free projects/accounts at Supabase, Google AI Studio, Render, and Cloudflare.

Supabase supplies authentication, PostgreSQL/pgvector, and private object storage. Render runs FastAPI plus the durable ingestion loop. Cloudflare serves the frontend. Gemini performs embeddings and generation.

## 2. Create and migrate Supabase

Create a Supabase project and keep its database password. From the repository root:

```bash
npx supabase@2.111.0 login
npx supabase@2.111.0 link --project-ref YOUR_PROJECT_REF
npx supabase@2.111.0 db push
```

`db push` applies `supabase/migrations/202608210001_initial.sql`, including pgvector, tables, indexes, RLS, and the private `documents` bucket. The same SQL can be pasted into the Supabase SQL editor if the CLI is unavailable.

From Project Settings, collect:

- Project URL.
- Publishable/anon key (safe for the browser).
- Service-role key (backend only; never expose it in a `NEXT_PUBLIC_` variable).
- Shared Supavisor session-pooler connection string on port 5432. Convert its scheme to `postgresql+asyncpg://` for FastAPI.

## 3. Create a Gemini key

Create a free Google AI Studio API key. It is backend-only. Defaults are:

- Generation: `gemini-3.6-flash`
- Embeddings: `gemini-embedding-001`
- Vector size: 768

Changing the embedding model or dimensions requires a new migration and a full re-index.

## 4. Configure local files

Create `.env.local` at the repository root from `.env.example`:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
NEXT_PUBLIC_STORAGE_BUCKET=documents
NEXT_PUBLIC_TURNSTILE_SITE_KEY=
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

Create `backend/.env` from `backend/.env.example` and replace every placeholder. For local processes, `DATABASE_URL` can use the hosted Supavisor URL. Keep `APP_ENV=development`, `CORS_ORIGINS=http://localhost:3000`, and `TRUSTED_HOSTS=localhost,127.0.0.1`.

Install and run:

```powershell
npm install --global npm@11.6.2
npm ci
python -m venv backend/.venv
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"

# terminal 1
cd backend
.venv\Scripts\python.exe -m uvicorn atlas.main:app --reload --port 8000

# terminal 2, repository root
npm run dev
```

Open `http://localhost:3000`. The API health endpoint is `http://localhost:8000/api/v1/health`.

## 5. Optional fully local Supabase + Docker mode

The Supabase CLI itself uses Docker and provides local Auth, PostgreSQL/pgvector, and Storage:

```bash
npx supabase@2.111.0 start -x logflare,vector
npx supabase@2.111.0 status -o env
```

The excluded containers provide optional local analytics/log shipping; Atlas
does not use them. The PostgreSQL `vector` extension remains enabled—this
`vector` container is a log router, not pgvector.

Copy the reported local keys to `.env.local` and `backend/.env`. When the backend runs inside Compose, replace local service hosts as follows:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:54322/postgres
SUPABASE_URL=http://host.docker.internal:54321
```

The browser value remains `NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321` because the browser is outside Docker. Then:

```bash
docker compose up --build
```

This local mode is optional. In production, uploads, indexing, retrieval, chat, and memory all run on Supabase, Render, Cloudflare, and Gemini—not on the local Docker environment.

## 6. Optional Turnstile bot protection

Create a free Cloudflare Turnstile widget, add its site key to `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, and enable Turnstile under Supabase Authentication → Bot and Abuse Protection using the widget secret. When no site key is configured, the widget is omitted; Supabase email limits still apply.

## 7. Supabase Auth URLs

During development add:

- Site URL: `http://localhost:3000`
- Redirect URLs: `http://localhost:3000/auth/callback` and `http://localhost:3000/reset-password`

Add the corresponding HTTPS frontend URLs during deployment. Keep email confirmation enabled for public registration.
