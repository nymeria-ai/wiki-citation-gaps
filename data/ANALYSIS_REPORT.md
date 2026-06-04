# Wikipedia Citation Gap Analysis — Phase 1 Report
**Date:** June 5, 2026  
**ZIM Snapshot:** English Wikipedia (no pictures), March 2026 — 48.3GB, 19.5M entries  
**Pipeline runtime:** ~2.5 minutes (title scan + targeted HTML parsing)

---

## Executive Summary

Scanned 19.5M Wikipedia entries, filtered to 967 articles relevant to monday.com's competitive space (project management, work management, collaboration software, competitors). Parsed all 967 articles, indexed 15,373 references, and identified 502 competitor mentions across 12 articles that reference monday.com.

**Key finding:** The PM software space on Wikipedia is generally well-referenced — no major "citation needed" tags on competitor or monday.com pages. The real opportunities are **structural**: articles where monday.com is absent but competitors are present, and thin/underdeveloped articles in the PM ecosystem.

---

## Monday.com Article Health

| Metric | Value |
|--------|-------|
| Word count | 1,495 |
| References | 52 |
| Citation needed tags | 0 |
| Ref density | 34.8 per 1,000 words |
| Dead links | 0 |
| Status | ✅ Clean |

The monday.com article is well-maintained with no maintenance banners. Sources include SEC filings, Forbes, TechCrunch, Reuters, Business Insider, VentureBeat, and Israeli press (Calcalist, Globes, Geektime, TheMarker).

---

## Competitor Comparison

| Article | Words | Refs | Ref Density | monday.com Mentioned? |
|---------|-------|------|-------------|----------------------|
| Microsoft Project | 3,409 | 33 | 9.7/1Kw | ❌ |
| Workfront | 3,111 | 122 | 39.2/1Kw | ❌ |
| Wrike | 1,753 | 76 | 43.4/1Kw | ❌ |
| Trello | 1,589 | 68 | 42.8/1Kw | ✅ |
| **Monday.com** | **1,495** | **52** | **34.8/1Kw** | ✅ |
| Smartsheet | 1,470 | 51 | 34.7/1Kw | ❌ |
| Airtable | 1,270 | 40 | 31.5/1Kw | ✅ |
| Jira (software) | 1,241 | 46 | 37.1/1Kw | ❌ |
| Planview | 1,217 | 62 | 50.9/1Kw | ❌ |
| Notion | 995 | 30 | 30.2/1Kw | ✅ |
| ClickUp | 989 | 34 | 34.4/1Kw | ✅ |
| Microsoft Planner | 715 | 18 | 25.2/1Kw | ✅ |
| Basecamp | 2 | 0 | 0.0/1Kw | ❌ (stub!) |

**Observations:**
- Monday.com is mid-pack in article size — Microsoft Project and Workfront are 2x larger
- Reference density is healthy at 34.8/1Kw
- Basecamp's article is essentially a redirect/stub (2 words)

---

## Strategic Gaps Identified

### 🔴 Gap 1: "List of collaborative software" — monday.com ABSENT
- **4,293 words, 79 references**
- Lists ClickUp, Notion, Trello, Wrike, Smartsheet, Microsoft Project, Zoho Projects, Confluence
- **monday.com is NOT listed** — this is a high-traffic directory article

### 🔴 Gap 2: "Agile software development" — monday.com ABSENT
- **11,904 words, 277 references** — one of the largest articles in the PM space
- Only mentions Notion, Linear, Hive as tools
- No monday.com presence despite being a key agile tool

### 🔴 Gap 3: "Project management" (main article) — monday.com ABSENT
- **10,911 words, 158 references**
- THE definitive article for the entire category
- Only mentions "Hive" as a tool — none of the major competitors are listed

### 🟡 Gap 4: "Gantt chart" — monday.com ABSENT
- **2,198 words, 54 references**
- No PM tools mentioned (only "Hive" match from content)
- Opportunity to be listed as a tool that implements Gantt charts

### 🟡 Gap 5: "Task management" — thin article
- **1,001 words, only 6 references** — ref density of 6.0/1Kw (very low)
- Does mention monday.com ✅ but the article needs significant expansion

### 🟡 Gap 6: "Project management software" — needs strengthening
- **1,337 words, 18 references** — ref density of 13.5/1Kw (low)
- Does mention monday.com ✅ but could be more comprehensive

---

## Articles Where monday.com IS Present (12 total)

1. ✅ Monday.com (own article)
2. ✅ Comparison of project management software (3,547w, 90 refs)
3. ✅ Project management software (1,337w, 18 refs)
4. ✅ Task management (1,001w, 6 refs)
5. ✅ Kanban board (896w, 13 refs)
6. ✅ List of Israeli companies listed on the Nasdaq
7. ✅ Airtable, ClickUp, Notion, Trello, Microsoft Planner, Teamwork (competitor articles)

---

## Database Deliverables

| File | Description |
|------|-------------|
| `data/wiki_analysis.db` | SQLite DB with articles, citation_gaps, references_found, competitor_mentions tables |
| `data/pipeline_summary.json` | Machine-readable pipeline stats |
| `data/pipeline.log` | Full processing log |
| `data/ANALYSIS_REPORT.md` | This report |

### DB Schema
- **articles** — 967 rows, full metadata per article (word count, refs, gaps, competitor mentions, infobox)
- **citation_gaps** — 78 rows, detailed gap annotations with section/snippet
- **references_found** — 15,373 rows, every reference URL and text extracted
- **competitor_mentions** — 502 rows, which competitors appear in which articles
- **articles_fts** — Full-text search index on titles, categories, match reasons

---

## Recommendations for Phase 2

1. **Add monday.com to "List of collaborative software"** — straightforward, high impact
2. **Get mentioned in "Project management" main article** — needs careful, community-approved approach
3. **Expand "Task management" article** — very thin, legitimate expansion opportunity
4. **Strengthen "Project management software"** — more references, better coverage
5. **Consider "Agile software development" presence** — large article, would need natural integration
6. **Monitor Basecamp stub** — if someone rebuilds it, ensure monday.com landscape is fair

---

*Pipeline code: `targeted_pipeline.py` | Data: `data/wiki_analysis.db` | Repo: nymeria-ai/wiki-citation-gaps*
