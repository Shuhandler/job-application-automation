# Automated Job Application Pipeline — System Design

> [!NOTE]
> **Implementation status (last updated 2026-04-22):**
> - ✅ **Phase 0 — Scaffolding:** complete. See [§2 Phase 0](#phase-0--scaffolding-12-days--complete) for the full checklist and [§6 Phase 0 Handoff](#6-phase-0-handoff-notes) for decisions made, deviations from this document, and entry points for Phase 1.
> - ⏳ **Phase 1 — Source Monitoring:** not started. Start here: `src/scrapers/` is an empty package. Company YAML schema and Celery Beat wiring are unbuilt.
> - ⏳ **Phases 2–6:** not started.

## 1. System Architecture

### High-Level Dataflow

```mermaid
graph LR
    A["Source Monitor<br/>(Scrapers + APIs)"] -->|raw postings| B["Parse & Filter<br/>Engine"]
    B -->|matched jobs| C["Referral<br/>Checker"]
    C -->|enriched jobs| D["Resume Selector +<br/>LLM Drafting"]
    D -->|application package| E["Discord Bot<br/>Delivery"]
    E -->|rich embed + files| F["Your Discord<br/>Server"]
    F -->|confirmation emails| I["Email Parser<br/>(Gmail API)"]
    I -->|status updates| G["State DB"]
    B -->|all events| G
    G -->|status changes| E
```

### Proposed Stack

| Layer | Tool | Rationale |
|---|---|---|
| **Runtime** | Python 3.12+ | Ecosystem depth for scraping, NLP, automation |
| **Task Orchestrator** | Celery + Redis | Distributed task queue; retry/backoff built-in; beat scheduler for polling |
| **Discord Integration** | `discord.py` (bot) + webhooks | Bot for interactive commands + reactions; webhooks for one-way alerts |
| **HTTP Scraping** | `httpx` + `parsel` | Async HTTP client + fast CSS/XPath parsing for API-based sources |
| **Browser Scraping** | Playwright (headless) + `playwright-stealth` | Only for sources that require JS rendering (LinkedIn, Workday) |
| **NLP / Filtering** | spaCy rule matcher + keyword scoring | Fast local inference; no API cost |
| **LLM Integration** | OpenAI `gpt-4o` or Claude via `litellm` | Provider-agnostic; easy fallback between providers |
| **Referral Network** | LinkedIn data export + local cache | Cross-reference connections against matched companies |
| **State / DB** | SQLite → PostgreSQL via SQLAlchemy | Job tracking, dedup, audit trail |
| **Config / Secrets** | Pydantic Settings + `.env` | Typed config; secrets via env vars |
| **Email Parsing** | Gmail API (`gmail.readonly`) + `google-auth` | Parse confirmation, OA, interview, and rejection emails into status updates |
| **Deployment** | Docker Compose on VPS (Hetzner / DigitalOcean) | Always-on; Discord bot needs persistent connection |

### Core Data Model

```python
class JobStatus(str, Enum):
    DISCOVERED  = "discovered"
    MATCHED     = "matched"
    NOTIFIED    = "notified"      # Discord notification sent
    SUBMITTED   = "submitted"     # you applied manually
    CONFIRMED   = "confirmed"     # confirmation email received
    OA_RECEIVED = "oa_received"   # online assessment link detected
    INTERVIEW   = "interview"     # interview invite detected
    OFFER       = "offer"
    REJECTED    = "rejected"      # rejection email detected
    SKIPPED     = "skipped"       # you reacted ❌ in Discord

class Job(Base):
    id: int
    source: str                   # "linkedin", "greenhouse:citadel", "lever:stripe", ...
    external_id: str              # dedup key
    title: str
    company: str
    url: str
    application_url: str          # direct link to the apply page
    description_raw: str
    description_clean: str
    relevance_score: float        # 0–1
    matched_keywords: list[str]
    role_category: str            # "quant", "tech" — drives resume selection
    status: JobStatus
    cover_letter_path: str | None # path to generated PDF
    resume_variant: str           # "quant" or "tech"
    resume_match_score: float     # confidence in variant selection
    referral_contacts: list[dict] # [{name, title, linkedin_url, degree}]
    discord_message_id: int | None # message ID for reaction tracking
    notified_at: datetime | None
    submitted_at: datetime | None # you mark this via Discord reaction
    confirmed_at: datetime | None # from email parser
    oa_deadline: datetime | None  # from email parser
    interview_date: datetime | None
    discovered_at: datetime
    error_log: str | None

class ResumeVariant(Base):
    id: int
    name: str                     # "quant", "tech"
    file_path: str                # path to PDF
    keywords: list[str]           # keywords this variant is optimized for
    description: str              # "Emphasizes stochastic calc, options pricing, C++"

class ReferralContact(Base):
    id: int
    name: str
    company: str
    title: str
    linkedin_url: str
    connection_degree: int        # 1 or 2
    last_synced: datetime

class EmailEvent(Base):
    id: int
    job_id: int | None            # FK → Job, null if unmatched
    gmail_message_id: str
    sender: str
    subject: str
    received_at: datetime
    event_type: str               # "confirmation", "oa", "interview", "rejection", "offer"
    extracted_data: dict          # {oa_link, deadline, interview_time, ...}
    processed_at: datetime
```

---

## 2. Implementation Phases

### Phase 0 — Scaffolding (1–2 days) — ✅ COMPLETE
- [x] Repo structure:
  ```
  src/
  ├── scrapers/          # one module per source                       (Phase 1 — empty stub)
  ├── filters/           # keyword scoring + NLP                       (Phase 2 — empty stub)
  ├── referrals/         # LinkedIn connection lookup                  (Phase 3 — empty stub)
  ├── resumes/           # resume variant selection logic              (Phase 4a — empty stub)
  ├── drafting/          # LLM cover letter generation                 (Phase 4b — empty stub)
  ├── discord_bot/       # discord.py bot + webhook delivery           (Phase 5 — empty stub)
  ├── email_tracker/     # Gmail API integration + status CRM          (Phase 6 — empty stub)
  ├── db/                # SQLAlchemy models + Alembic env             (Phase 0 — done)
  ├── config/            # Pydantic Settings + personal-info YAML      (Phase 0 — done)
  └── cli/               # Typer CLI entrypoints                       (Phase 0 — done)
  ```
- [x] Pydantic config: personal info schema (name, email, phone, university, GPA, grad date, work auth, skills, experiences, resume paths) — `src/config/personal.py` (`PersonalInfo`, loaded from YAML; example at `config/personal.example.yaml`)
- [x] SQLAlchemy models + Alembic — `src/db/models.py` (`Job`, `ResumeVariant`, `ReferralContact`, `EmailEvent`) + `src/db/migrations/versions/0001_initial_schema.py`
- [x] `.env` template with all required secrets — `.env.example`, consumed by `src/config/settings.py`
- [x] `pyproject.toml` with dependency groups — core deps + per-phase optional extras (`scraping`, `nlp`, `celery`, `discord`, `pdf`, `llm`, `email`, `postgres`, `all`) + PEP 735 `dev` group
- [x] Tooling beyond the spec: Ruff (lint + format), Mypy (strict), Pytest + asyncio, pre-commit hooks, Hatchling build backend, `uv` as the package/project manager, `docker-compose.yml` for Postgres + Redis, Typer CLI entry point (`jaa version|config show|config personal|db upgrade|db downgrade|db revision|db current`)

### Phase 1 — Source Monitoring (3–5 days)
- [ ] **API-based sources (no scraping needed):**
  - Greenhouse: `GET https://boards-api.greenhouse.io/v1/boards/{company}/jobs` — public JSON
  - Lever: `GET https://api.lever.co/v0/postings/{company}` — public JSON
  - Maintain a YAML config of target companies + their ATS type
- [ ] **Scraping-based sources:**
  - LinkedIn: authenticated session via saved `storage_state`; scrape `/jobs/search/` results
  - Handshake: `.edu` SSO auth state; scrape posting feeds
  - Workday / iCIMS / custom: Playwright per-company scrapers
- [ ] **Company config file:**
  ```yaml
  companies:
    - name: Jane Street
      ats: greenhouse
      board_id: janestreet
      priority: 1
    - name: Citadel
      ats: workday
      careers_url: https://www.citadel.com/careers/
      priority: 1
    - name: Google
      ats: custom
      careers_url: https://careers.google.com/jobs/results/
      search_params: {q: "new grad software engineer"}
      priority: 2
  ```
- [ ] Celery Beat scheduler: poll API sources every 5 min, scraping sources every 15 min
- [ ] Dedup on `(source, external_id)` — skip if already in DB

### Phase 2 — Filtering Engine (2–3 days)
- [ ] **Keyword taxonomy** (configurable in YAML):
  ```yaml
  include_title:    # weight: 3x
    - quant
    - quantitative
    - data scientist
    - software engineer
    - ML engineer
    - research
    - trading
  include_body:     # weight: 1x
    - Python
    - C++
    - stochastic calculus
    - probability
    - machine learning
    - linear algebra
    - statistics
  exclude:          # instant reject
    - senior
    - staff
    - principal
    - "10+ years"
    - director
    - VP
  require_any:      # must match ≥1
    - new grad
    - entry level
    - intern
    - "2025"
    - "2026"
    - early career
    - "0-2 years"
  ```
- [ ] Scoring: `score = (3 × title_hits + 1 × body_hits) / max_possible`, reject if any `exclude` match
- [ ] Thresholds: `≥ 0.6` → auto-notify via Discord; `0.3–0.6` → post to `#review` channel; `< 0.3` → skip
- [ ] Handle edge case: postings that omit seniority level → flag for manual triage, don't auto-reject

### Phase 3 — Referral Network Automation (3–4 days)
- [ ] **LinkedIn Connection Sync:**
  - Export connections via LinkedIn data export (Settings → Get a copy of your data) → parse `Connections.csv`
  - Alternatively: scrape your connections list via Playwright with auth state (riskier, but real-time)
  - Store in `ReferralContact` table with company normalization (fuzzy match company names)
- [ ] **Matching Logic:**
  - For each matched job, query `ReferralContact` where `company` fuzzy-matches `Job.company`
  - Surface 1st-degree connections first, then 2nd-degree
  - Attach to `Job.referral_contacts`
- [ ] **Referral Message Drafting:**
  - LLM-generated referral request, personalized to the contact's role:
    ```
    Hi {contact_name}, I saw that {company} has an opening for {job_title}.
    I'm a {degree} student at {university} with experience in {relevant_skills}.
    Would you be open to referring me or connecting me with the hiring team?
    ```
  - Included in Discord notification — copy-pasteable, never auto-sent

### Phase 4 — Resume Variant Selector + LLM Drafting (3–4 days)

#### 4a. Resume Variant Selector
- [ ] **Define two resume variants:**

  | Variant | Optimized For | Key Sections Emphasized |
  |---|---|---|
  | **Quant** (`quant.pdf`) | Quant research, trading, quant dev | Stochastic calculus, options pricing, statistical modeling, C++, probability theory, math competitions |
  | **Tech** (`tech.pdf`) | SWE, ML/AI, data engineering, big tech | Systems design, distributed systems, Python/Java, ML pipelines, open-source contributions, hackathons |

- [ ] **Selection logic** — score each variant against the JD:
  ```python
  VARIANT_KEYWORDS = {
      "quant": ["quantitative", "trading", "stochastic", "options", "pricing",
               "risk", "derivatives", "fixed income", "alpha", "portfolio",
               "C++", "numerical", "probability", "statistics", "math"],
      "tech":  ["software engineer", "distributed", "systems", "API",
               "cloud", "kubernetes", "ML", "data pipeline", "backend",
               "frontend", "full stack", "Python", "Java", "Go", "scale"],
  }

  def select_variant(job: Job) -> tuple[str, float]:
      scores = {}
      jd = job.description_clean.lower()
      for variant, keywords in VARIANT_KEYWORDS.items():
          hits = sum(1 for kw in keywords if kw.lower() in jd)
          scores[variant] = hits / len(keywords)
      best = max(scores, key=scores.get)
      return best, scores[best]
  ```
- [ ] Store `Job.resume_variant` and `Job.resume_match_score`
- [ ] Edge case: if scores are within 0.05 of each other, flag for manual selection in Discord
- [ ] Also set `Job.role_category` (`"quant"` or `"tech"`) — this drives cover letter tone as well

#### 4b. LLM Cover Letter Generation
- [ ] **Cover Letter Generation:**
  - System prompt with your background, target tone, and structural constraints
  - Tone varies by `role_category`:
    - **Quant**: emphasize mathematical rigor, research experience, quantitative competitions
    - **Tech**: emphasize engineering projects, scale, open-source, system design
  - Per-job prompt injects: `{job_title}`, `{company}`, `{job_description}`, `{matched_keywords}`, `{role_category}`
  - Output: 250–350 word letter, professional but specific to the role
  - Generate as markdown → convert to PDF via `weasyprint` (use a clean LaTeX-style template)
- [ ] **Free-Text Answer Drafting:**
  - Some portals ask "Why do you want to work at X?" or "Describe a project..."
  - Pre-generate 2–3 common answers, templated with company/role specifics
  - Delivered as a text block in the Discord notification
- [ ] **Caching:** Hash `(company, job_title, description_hash)` → skip re-generation for similar roles

### Phase 5 — Discord Bot & Notification Delivery (4–5 days)

This is the **core delivery mechanism**. Everything the pipeline prepares gets packaged and sent to your Discord server.

- [ ] **Discord Server Structure:**
  ```
  #job-alerts          — high-confidence matches (score ≥ 0.6), auto-notified
  #job-review          — medium-confidence matches (0.3–0.6), for manual triage
  #status-updates      — email parser events (OA received, interview, rejection)
  #daily-digest        — daily summary of pipeline activity
  #bot-commands        — interact with the bot (search, stats, force-refresh)
  ```

- [ ] **Job Alert Embed Format:**
  ```python
  embed = discord.Embed(
      title=f"🎯 {job.company} — {job.title}",
      url=job.application_url,
      color=0x00FF88 if job.role_category == "quant" else 0x5865F2,
  )
  embed.add_field(name="📊 Score", value=f"{job.relevance_score:.0%}", inline=True)
  embed.add_field(name="📄 Resume", value=f"`{job.resume_variant}` ({job.resume_match_score:.0%})", inline=True)
  embed.add_field(name="🏷️ Keywords", value=", ".join(job.matched_keywords[:8]), inline=False)
  embed.add_field(name="🔗 Referrals", value=referral_text or "None found", inline=False)
  embed.set_footer(text=f"Source: {job.source} | Discovered: {job.discovered_at:%b %d %H:%M}")
  ```

- [ ] **File Attachments per notification:**
  - ✅ Cover letter PDF (tailored to this role)
  - ✅ Selected resume PDF (quant or tech variant)
  - ✅ Referral message draft (as a text block in the embed, copy-pasteable)
  - ✅ Pre-drafted free-text answers (if applicable)

- [ ] **Reaction-Based Workflow:**
  | Reaction | Action |
  |---|---|
  | ✅ | Mark as `SUBMITTED` — you applied |
  | ❌ | Mark as `SKIPPED` — not interested |
  | 🔄 | Regenerate cover letter with different tone |
  | 📄 | Switch resume variant (quant ↔ tech) |
  | 👤 | Show full referral contact details + drafted message |

- [ ] **Bot Slash Commands:**
  | Command | Description |
  |---|---|
  | `/stats` | Pipeline summary: matched, notified, submitted, by company |
  | `/search <keyword>` | Search past jobs by keyword |
  | `/status <company>` | Show all jobs + statuses for a given company |
  | `/refresh` | Force an immediate scrape cycle |
  | `/digest` | Trigger daily digest now |

- [ ] **Daily Digest** (posted to `#daily-digest` at 9 AM):
  - New jobs discovered today
  - Jobs awaiting your action (notified but no reaction)
  - Status changes from email parser
  - Pipeline health (source uptime, error counts)

### Phase 6 — Email Parser & Application Status CRM (3–4 days)

Closes the loop from submission → outcome tracking with zero manual data entry.

- [ ] **Gmail API Setup:**
  - OAuth2 with `gmail.readonly` scope via Google Cloud Console
  - Credentials stored in `.env` / secure keychain
  - Poll every 5 min via Celery Beat (or use Gmail push notifications via Pub/Sub for real-time)
- [ ] **Email Classification Pipeline:**
  ```python
  EMAIL_PATTERNS = {
      "confirmation": [
          r"application.*(received|confirmed|submitted)",
          r"thank you for (applying|your interest)",
          r"we have received your application",
      ],
      "oa": [
          r"(hackerrank|codesignal|hirevue|codility)\.com",
          r"online assessment",
          r"coding (challenge|test)",
      ],
      "interview": [
          r"(schedule|invite).*(interview|phone screen|onsite)",
          r"next (round|step|stage)",
      ],
      "rejection": [
          r"(unfortunately|regret|not moving forward)",
          r"will not be (proceeding|advancing)",
          r"other candidates",
      ],
      "offer": [
          r"(pleased|excited) to (offer|extend)",
          r"offer letter",
      ],
  }
  ```
- [ ] **Job Matching:**
  - Match incoming emails to `Job` records by fuzzy-matching `sender` domain → `Job.company` and `subject` → `Job.title`
  - Unmatched emails flagged in `#status-updates` for manual linking
- [ ] **Data Extraction:**
  - OA emails: extract assessment URL + deadline via regex
  - Interview emails: extract proposed dates/times, interviewer names
  - Store in `EmailEvent.extracted_data` as JSON
- [ ] **Automated Actions on Status Change:**
  - `OA_RECEIVED`: Create Google Calendar event with deadline via Calendar API + Discord alert
  - `INTERVIEW`: Create calendar event + Discord alert with interview details
  - `REJECTED`: Discord notification; update stats
  - All transitions posted to `#status-updates`
- [ ] **Pipeline Funnel** (available via `/stats`):
  - % conversion at each stage: Notified → Submitted → OA → Interview → Offer

---

## 3. Feature Expansion (Beyond Core)

### 3a. Application Timing Optimizer
Track `submitted_at` timestamps vs. outcomes. Hypothesis: apps submitted within the first 48 hours of posting have higher response rates. Use this data to prioritize notification ordering by posting age.

### 3b. JD Change Detection
Some companies silently update JDs (e.g., changing "3+ years" to "0-2 years" or adding new locations). Diff each scrape against the stored `description_raw`. Alert in `#job-alerts` on material changes to previously-skipped postings.

### 3c. Portfolio Link Injection
For applications with a "portfolio" or "website" field, auto-generate a personalized one-pager via GitHub Pages that highlights projects relevant to the specific JD. Templated HTML + LLM-selected project descriptions.

---

## 4. Risk Mitigation

> [!TIP]
> Since the system only scrapes and notifies — no automated form-filling or submission — anti-bot risk is limited entirely to the scraping phase. You apply manually via your own browser.

### 4a. Scraping Phase (Automated — Moderate Risk)

| Technique | Implementation |
|---|---|
| **Prefer APIs over scraping** | Greenhouse + Lever = free JSON APIs. Use them. Scrape only when no API exists. |
| **Residential proxies** | BrightData / Smartproxy for LinkedIn and Workday scraping. ~$15/mo for this volume. |
| **Rate limiting** | Max 1 request/3s per source. Celery rate limits: `@task(rate_limit="20/m")` |
| **Session reuse** | Save `storage_state` for authenticated sites. Avoid re-login per cycle. |
| **`playwright-stealth`** | Patches webdriver detection for headless scraping. |
| **User-Agent pool** | 10–15 real Chrome UAs, rotated per session. |

### 4b. Resilience Patterns
- **Retry with backoff**: Celery `autoretry_for=(HTTPError,)`, `retry_backoff=True`, `max_retries=3`
- **Circuit breaker**: >5 consecutive failures on a source → pause + Discord alert in `#bot-commands`
- **Screenshot on failure**: `page.screenshot()` for debugging scraping errors
- **Idempotency**: Dedup on `(source, external_id)` before insert; skip already-notified jobs
- **Graceful degradation**: If LinkedIn scraping fails, the system still runs on API sources

---

## 5. Timeline

| Phase | Duration | Cumulative |
|---|---|---|
| P0: Scaffolding | 1–2 days | 2 days |
| P1: Source Monitoring | 3–5 days | 7 days |
| P2: Filtering | 2–3 days | 10 days |
| P3: Referral Network | 3–4 days | 14 days |
| P4: Resume Selector + LLM Drafting | 3–4 days | 18 days |
| P5: Discord Bot + Delivery | 4–5 days | 23 days |
| P6: Email Parser + Status CRM | 3–4 days | 27 days |
| **Total MVP** | | **~4 weeks** |

> [!TIP]
> **Suggested build order for fastest time-to-value**: P0 → P1 (Greenhouse/Lever APIs only) → P2 → P5 (basic Discord webhook alerts) → P4 (resume selector + cover letter). This gets you a working scrape → filter → Discord notification loop in ~10 days. Add referrals (P3), bot commands, and email tracking (P6) incrementally.

> [!NOTE]
> **P6 can run independently** once you start manually submitting applications. Even before the full bot is built, you can deploy the email parser against your Gmail to start tracking statuses and posting updates to `#status-updates`.

---

## 6. Phase 0 Handoff Notes

Context for whoever picks up Phase 1. Reflects the state of `main` as of 2026-04-22.

### 6a. Decisions Locked In During Phase 0

These fix the shape of every later phase:

| Area | Decision | Rationale |
|---|---|---|
| Package / project manager | `uv` (Astral) | Fast installs; manages Python toolchain; PEP 621 native. `uv.lock` is committed. |
| Build backend | Hatchling | Pairs cleanly with `uv` + PEP 621 metadata. |
| Python version | `>=3.12` (`.python-version` = 3.12) | Matches spec §1; enables modern typing syntax. |
| Personal info source | YAML (`config/personal.yaml`, gitignored) loaded via Pydantic | `.env` used only for secrets and deployment knobs. See `src/config/personal.py`. |
| Secrets / env | `pydantic-settings` + `.env` (aliased uppercase vars), `SecretStr` for all tokens | Central, typed, masked in logs. See `src/config/settings.py`. |
| SQLAlchemy execution | Sync only in P0 (`Session`, `sessionmaker`) | Celery + CLI are sync. An async engine can be layered in at P5 against the same `Base` — **no model changes needed**. |
| ORM style | SQLAlchemy 2.0 typed `Mapped[...]` + `mapped_column(...)` | Native dataclass-like models; strict-mypy friendly. |
| JSON-typed columns | Cross-dialect `sqlalchemy.JSON` | Same schema works for SQLite and Postgres. Postgres-only `JSONB` operations are deliberately **not** used. |
| Enum columns | `Enum(..., native_enum=False, length=32)` | Portable across SQLite + Postgres; stored as `VARCHAR`. |
| DB default | SQLite at `./data/app.db` for dev | `data/` is gitignored; parent dir auto-created on first connect. `PRAGMA foreign_keys=ON` enforced via connect event. |
| DB prod | Postgres via `docker-compose.yml` (`postgres` + `redis` services only, no app container) | Flip `DATABASE_URL` to `postgresql+psycopg://jaa:jaa@localhost:5432/jaa`. |
| Alembic | Initial revision `0001` hand-written to mirror `Base.metadata`; `render_as_batch=True` for SQLite ALTERs | Autogenerate will work correctly for future revisions because `env.py` imports `src.db.models`. |
| CLI framework | Typer + Rich | Spec §1. Subcommands call `python -m alembic` internally. |
| Lint / format | Ruff (E/F/W/I/B/UP/N/SIM/RUF) + `ruff format` | Replaces black + isort + flake8. |
| Type check | Mypy `strict=true` with `pydantic.mypy` plugin | Migrations directory excluded. |
| Tests | Pytest, `asyncio_mode=auto`, `filterwarnings=error` | 14 passing baseline tests including an Alembic upgrade/downgrade/upgrade round-trip. |
| Dependency grouping | Core deps minimal; feature-specific libs under `[project.optional-dependencies]` (`scraping`, `nlp`, `celery`, `discord`, `pdf`, `llm`, `email`, `postgres`); `all` extra composes them; `dev` group via PEP 735 | Lets each phase opt into its libs without bloating a minimal install. |

### 6b. Deliberately Deferred Work

Do **not** treat any of these as forgotten — they are parked until their phase:

| Deferred | Reason | When to build |
|---|---|---|
| LLM client (`litellm` / OpenAI / Anthropic SDKs) | Not needed for P1–P3; declared under `[project.optional-dependencies].llm` only | Phase 4b |
| `celery` + `redis` runtime deps | Not needed until there's a task to schedule | Phase 1 (add via `uv sync --extra celery`) |
| Async SQLAlchemy engine + `AsyncSession` | `discord.py` is the only async consumer | Phase 5 — add `create_async_engine(settings.database_url)` in `src/db/base.py`; models are already engine-agnostic |
| App Dockerfile + full deployment stack | Outside Phase 0 scope; infra services (Postgres, Redis) are scaffolded in `docker-compose.yml` | Pre-production, likely after P5 |
| Company target list YAML (`config/companies.yaml`) | Belongs to the scraping layer | Phase 1 — schema sketched in §2 Phase 1 |
| Keyword taxonomy YAML | Belongs to the filter layer | Phase 2 |
| Discord server setup + bot token | Cannot be tested without a real guild | Phase 5 |
| Gmail OAuth credentials + token files | Paths reserved in `.env.example` but files are gitignored | Phase 6 |
| Structured logging | Using stdlib + `rich` for now; swap to `structlog` if needed | When log volume justifies it |
| CI pipeline (GitHub Actions) | Pre-commit runs locally and is sufficient for solo dev | Add if/when collaborators join |

### 6c. Entry Points for Phase 1 (Source Monitoring)

Concrete starting points for whoever implements Phase 1:

1. **Add runtime deps for this phase:**
   ```bash
   uv sync --extra scraping --extra celery --group dev
   ```
   This pulls in `httpx`, `parsel`, `playwright`, `playwright-stealth`, `celery[redis]`, and `redis`.

2. **New files to create (none exist yet):**
   - `config/companies.yaml` — target list; schema already sketched in §2 Phase 1.
   - `src/config/companies.py` — Pydantic loader mirroring `src/config/personal.py`.
   - `src/scrapers/base.py` — `Scraper` protocol / ABC returning `list[JobPayload]` (a Pydantic DTO, **not** the ORM `Job`).
   - `src/scrapers/greenhouse.py`, `src/scrapers/lever.py` — API-based scrapers first (no Playwright).
   - `src/scrapers/linkedin.py`, `src/scrapers/handshake.py`, `src/scrapers/workday.py` — Playwright scrapers after APIs work end-to-end.
   - `src/tasks/` (new package) — Celery app, beat schedule, and per-source tasks.
   - `src/cli/` — register a `scrape` sub-app with `once` / `beat` / `worker` commands.

3. **Persistence hooks that already exist:**
   - `src/db/models.py::Job` — has `source`, `external_id`, `url`, `application_url`, `description_raw`, `description_clean`, a `UniqueConstraint("source", "external_id")`, and `status` defaulting to `JobStatus.DISCOVERED`. Insert with a `SessionLocal()` / `get_session()` from `src/db/base.py`; dedup by catching `IntegrityError` or using `INSERT … ON CONFLICT DO NOTHING` (Postgres) / `INSERT OR IGNORE` (SQLite).
   - `src/db/models.py::JobStatus` — full state enum; Phase 1 only writes `DISCOVERED`.

4. **Config hooks that already exist:**
   - `settings.redis_url` — Celery broker/result backend.
   - `settings.proxy_url`, `settings.linkedin_storage_state_path`, `settings.handshake_storage_state_path` — plumbed through but unused until scrapers exist.

5. **Test pattern to copy:** `tests/conftest.py::db_session` gives a fresh in-memory schema per test; `tests/test_models.py` shows the insert + unique-constraint pattern. Phase 1 tests should assert dedup on `(source, external_id)` and clean `JobPayload → Job` hydration.

6. **Things *not* to rebuild:**
   - Don't add a second settings object — extend `src/config/settings.py` with new fields.
   - Don't create a new migration to rename fields in `Job` unless the schema changes; `Job` already covers every P1–P6 field.
   - Don't switch to async SQLAlchemy just for scrapers — `httpx.AsyncClient` inside a Celery task is fine, and DB writes can batch at the end of each task synchronously.

### 6d. How to Verify a Clean Working Copy

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest            # expect 14 passed
uv run jaa config personal --path config/personal.example.yaml
uv run jaa db upgrade head
uv run jaa db current    # expect: 0001 (head)
```

All of the above pass on `main` as of this commit.
