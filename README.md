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