# Job Application Automation

A semi-automated pipeline for monitoring, filtering, and staging job applications targeting new graduate and internship roles in Quantitative Finance and Big Tech.

## How It Works

The system **does not** auto-submit applications. It scrapes job boards, filters for relevant roles, selects the best resume variant, drafts a tailored cover letter, pre-fills the application form in your browser, and hands control to you for review and manual submission.

## Core Features

- **Source Monitoring** — Polls Greenhouse/Lever APIs and scrapes LinkedIn, Handshake, and company career pages for new postings
- **Smart Filtering** — Keyword-scored relevance engine with configurable include/exclude/require rules
- **Referral Network** — Cross-references matched companies against your LinkedIn connections and drafts referral messages
- **Resume Variant Selector** — Automatically picks quant or tech resume based on JD keyword analysis
- **LLM Cover Letters** — Generates tailored cover letters with role-category-aware tone via GPT-4o/Claude
- **Application Staging** — Pre-fills forms in a headed Playwright browser for your review and manual submit
- **Email Status Tracker** — Parses Gmail for confirmations, OA invites, interviews, and rejections to build a full CRM

## Documentation

- **[System Design](docs/SYSTEM_DESIGN.md)** — Full architecture, tech stack, data model, implementation phases, and risk mitigation

## Tech Stack

| Layer | Tool |
|---|---|
| Runtime | Python 3.12+ |
| Task Queue | Celery + Redis |
| Browser | Playwright (persistent headed context) |
| Scraping | httpx + parsel |
| LLM | litellm (OpenAI / Anthropic) |
| DB | SQLite → PostgreSQL (SQLAlchemy) |
| Email | Gmail API |
| Dashboard | Streamlit |
| Notifications | Discord webhooks |