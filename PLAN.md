# Wiki Citation Gap Finder — Build Plan

## Overview
Build a custom Wikipedia citation gap scanner tailored to monday.com's product categories.

## Architecture

### Phase 1: Data Pipeline (Sub-agent 1 — Claude Code)
- Download English Wikipedia ZIM snapshot from Kiwix
- Parse ZIM → extract articles with maintenance templates
- Extract: article_title, url, template_kind, snippet, section, page_path
- Output: SQLite DB + CSV

### Phase 2: monday.com Enrichment (Sub-agent 2 — Claude Code)
- Cross-reference gaps with PMM product categories
- Add relevance scoring (product alignment, pageviews)
- Flag articles mentioning monday.com or competitors
- Build search API (Node/Python)

### Phase 3: Wikipedia Update Strategy Research (Sub-agent 3 — lightweight model)
- How to create/manage Wikipedia editor accounts properly
- Account reputation building strategies
- Risk of paid editing detection
- Best practices for corporate Wikipedia engagement
- The 80/20 rule: community contributions vs self-serving edits
- Case studies of companies that did this well/poorly

### Phase 4: Strategy & Playbook (after Phase 1-3 complete)
- Combine tool output + research into actionable playbook
- Content mix recommendations
- Timeline and execution plan

## Token Economy
- Phase 1 (heavy coding): Claude Code (claude-sonnet-4-20250514)
- Phase 2 (enrichment coding): Claude Code (claude-sonnet-4-20250514)
- Phase 3 (research): Gemini/GPT (web search, no heavy compute)
- Orchestration: Main session (Opus) — minimal, just monitoring

## Git
- Repo: nymeria-ai/wiki-citation-gaps (new, public)
- All code via Claude Code sub-agents

## Constraints
- ⚠️ NO Wikipedia edits at any stage
- Strategy only — no execution on Wikipedia
