# Job Application Automation

A pipeline for monitoring, filtering, and preparing job applications targeting new graduate and internship roles in Quantitative Finance and Big Tech — delivered entirely through Discord.

## How It Works

The system scrapes job boards, filters for relevant roles, selects the best resume variant (quant or tech), drafts a tailored cover letter, checks your LinkedIn network for referrals, and sends everything to your Discord server as a rich notification with attached files. You review, grab the materials, and apply manually.

## Core Features

- **Source Monitoring** — Polls Greenhouse/Lever APIs and scrapes LinkedIn, Handshake, and company career pages for new postings
- **Smart Filtering** — Keyword-scored relevance engine with configurable include/exclude/require rules
- **Referral Network** — Cross-references matched companies against your LinkedIn connections and drafts referral messages
- **Resume Variant Selector** — Automatically picks quant or tech resume based on JD keyword analysis
- **LLM Cover Letters** — Generates tailored cover letters with role-category-aware tone via GPT-4o/Claude
- **Discord Delivery** — Rich embeds with cover letter PDF, resume, referral info, and direct apply link; reaction-based workflow (✅ applied, ❌ skip, 🔄 regenerate)
- **Email Status Tracker** — Parses Gmail for confirmations, OA invites, interviews, and rejections; posts updates to Discord

## Documentation

- **[System Design](docs/SYSTEM_DESIGN.md)** — Full architecture, tech stack, data model, implementation phases, and risk mitigation

## Getting Started (Phase 0 Scaffold)

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Docker (optional, only needed for Postgres/Redis in dev)

### Setup

```bash
git clone <this repo> && cd job-application-automation

# Install deps (creates .venv automatically, using Python 3.12)
uv sync --all-extras --group dev

# Configure secrets
cp .env.example .env
# → edit .env as needed

# Configure your personal profile
cp config/personal.example.yaml config/personal.yaml
# → edit config/personal.yaml (gitignored — stays local)

# Validate the profile
uv run jaa config personal

# Initialize the database (SQLite by default)
mkdir -p data
uv run jaa db upgrade head

# Optional: bring up Postgres + Redis for prod-parity local dev
docker compose up -d
# Then switch DATABASE_URL in .env to:
#   postgresql+psycopg://jaa:jaa@localhost:5432/jaa

# Install pre-commit hooks
uv run pre-commit install
```

### Dev workflow

```bash
uv run ruff check .            # lint
uv run ruff format .           # format
uv run mypy src                # type check
uv run pytest                  # tests
uv run jaa --help              # CLI
uv run jaa db revision -m "…"  # new migration
```

### Repository Layout

```
src/
├── config/         # Pydantic settings + personal profile YAML loader
├── db/             # SQLAlchemy models + Alembic migrations
├── scrapers/       # (Phase 1)
├── filters/        # (Phase 2)
├── referrals/      # (Phase 3)
├── resumes/        # (Phase 4a)
├── drafting/       # (Phase 4b)
├── discord_bot/    # (Phase 5)
├── email_tracker/  # (Phase 6)
└── cli/            # Typer entrypoints
```

## Tech Stack

| Layer | Tool |
|---|---|
| Runtime | Python 3.12+ |
| Task Queue | Celery + Redis |
| Discord | discord.py bot + webhooks |
| Scraping | httpx + parsel + Playwright (headless) |
| LLM | litellm (OpenAI / Anthropic) |
| DB | SQLite → PostgreSQL (SQLAlchemy) |
| Email | Gmail API |
| Deployment | Docker Compose on VPS |