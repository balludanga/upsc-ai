# UPSC Study Assistant — Private Study Backend

This is a personal UPSC preparation assistant. It combines grounded Q&A,
Prelims MCQs, and a small study-tracking layer so the assistant can help you
decide what to study next and show whether you are actually maintaining a
routine. It is intended to run locally for one person, not as a public SaaS.

## The stack (nothing paid, nothing proprietary)
| Piece | Tool | Why |
|---|---|---|
| API | FastAPI | Open source, fast, great docs |
| Database | PostgreSQL | Open source, stores users + quiz history |
| Vector store | Qdrant | Open source, self-hostable |
| LLM + embeddings | Ollama running Qwen2.5:3b + nomic-embed-text | Fully open-source models, self-hosted |
| Auth | JWT (python-jose + passlib) | No third-party auth vendor needed |

Everything runs together via Docker Compose on a **single free-tier VM**.

## Recommended free hosting: Oracle Cloud "Always Free" tier
Unlike most free tiers, Oracle's Always Free ARM instance (4 OCPUs, 24GB
RAM) is genuinely free forever, not a trial — and it's the only common
free tier with enough RAM to comfortably run Postgres + Qdrant + Ollama
+ your API together. Railway/Render free tiers (512MB–1GB RAM) are too
small for this combination.

Steps:
1. Sign up for Oracle Cloud, create an "Always Free" Ampere A1 instance
   (Ubuntu 22.04).
2. Install Docker and Docker Compose on it.
3. Copy this project to the VM (`git clone` your repo, or `scp`).
4. Copy `.env.example` to `.env` and fill in a real `JWT_SECRET`
   (generate with `openssl rand -hex 32`).
5. `docker compose up -d --build`
6. Once containers are up, pull the models into the Ollama container:
   ```bash
   docker exec -it upsc-app-ollama-1 ollama pull qwen2.5:3b
   docker exec -it upsc-app-ollama-1 ollama pull nomic-embed-text
   ```
7. Your API is now live at `http://<vm-ip>:8000`. Point your mobile app
   at this address. Put it behind a domain + HTTPS (Caddy or Nginx with
   Let's Encrypt, both free) before real public launch — app stores and
   browsers expect HTTPS.

## Building your corpus (do this before launch)
**Critical for a public app:** only use content you can legally
redistribute — NCERT textbooks, PIB releases, PRS briefs, Economic
Survey, budget docs, your own notes. Do not ingest copyrighted
commercial books; that's fine for personal use but not for serving
answers to other users.

1. Put your files in `corpus/<Subject>/...` (same structure as before).
2. Run ingestion — do this on Google Colab for speed (free GPU), pointed
   at your Qdrant instance via `.env`:
   ```bash
   pip install -r requirements.txt
   python ingest.py
   ```
   (Make sure `QDRANT_URL` in `.env` points to your VM's public IP and
   port 6333, or tunnel it, when running ingestion from Colab.)

## API endpoints
- `POST /auth/register` — `{email, password}`
- `POST /auth/login` — form data `username`, `password` → returns JWT
- `POST /ask` — `{question}` (requires `Authorization: Bearer <token>`)
- `POST /quiz/generate` — `{topic, num_questions}`
- `POST /quiz/submit` — `{quiz_attempt_id, selected_option}`
- `POST /study/sessions` — log a focused session: `{topic, mode, minutes, notes}`
- `GET /study/dashboard` — today's minutes, total time, streak, quiz accuracy,
  and the three weakest answered topics
- `GET /study/plan` — a short deterministic daily plan that does not call the LLM

`FREE_TIER_DAILY_LIMIT=0` disables the question cap for a private installation.
Set it to a positive number if you later share the API.

## A practical private workflow

1. Ask `/ask` for explanations, comparisons, and mains answer structures.
2. Generate a small quiz for the same topic with `/quiz/generate`.
3. Submit answers and use `/study/dashboard` to find weak areas.
4. Log the focused work with `/study/sessions` and follow `/study/plan` daily.

The assistant is grounded in the files you ingest, but generated answers and
questions can still contain mistakes. Treat it as a study partner, then verify
important facts against the original source.

## Running locally on your Mac first (recommended before any VM)
On an 8GB Mac, run Ollama natively (you already installed it earlier)
rather than adding a second containerized copy — that saves RAM.
Postgres, Qdrant, and the API run in Docker.

```bash
# 1. Make sure Ollama is running natively with models pulled
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
ollama serve   # leave running in its own terminal tab (may already be running)

# 2. Configure environment
cp .env.example .env
```
Edit `.env`:
- `DATABASE_URL=postgresql://upsc_user:upsc_pass@postgres:5432/upsc_db`
- `QDRANT_URL=http://qdrant:6333`
- `OLLAMA_HOST=http://host.docker.internal:11434`
- Set `JWT_SECRET` to the output of `openssl rand -hex 32`

```bash
# 3. Bring up Postgres, Qdrant, and the API (Ollama stays native)
docker compose -f docker-compose.local.yml up -d --build
```

Visit `http://localhost:8000/docs` for interactive API testing — try
`/health` first, then `/auth/register`.

For `ingest.py` (run directly on your Mac, not in Docker), use a
*separate* `.env` values or just override at runtime, since it connects
from outside the Docker network:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# QDRANT_URL=http://localhost:6333 and OLLAMA_HOST=http://localhost:11434
python ingest.py
```

## Moving to a VM later
When you're ready to deploy, the *only* thing that changes is you use
the original `docker-compose.yml` (which containerizes Ollama too,
since a VM like Oracle's Always Free tier has the RAM to spare) instead
of `docker-compose.local.yml`. Everything else — your code, your .env
structure, your corpus — carries over unchanged.

## What's still needed before a real public launch
- **Privacy policy + terms of service** — required by both app stores,
  even for free apps.
- **HTTPS** via a domain + reverse proxy (Caddy is the easiest, free,
  auto-HTTPS option).
- **Backups** for the Postgres volume.
- **Monitoring** — even basic uptime checks (free tier of UptimeRobot)
  so you know if your VM goes down.
- **Content review** — have someone check generated answers/MCQs for
  accuracy before trusting them fully; LLMs can still get facts wrong
  even with RAG.

## Next: the mobile app
Once this API is live and responding at `/docs`, we build the React
Native (Expo) app that talks to it — ask me when you're ready for that
step.
