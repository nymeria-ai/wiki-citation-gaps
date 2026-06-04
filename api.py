#!/usr/bin/env python3
"""
FastAPI web service for Wikipedia Citation Gap search and exploration.
"""

import sqlite3
import csv
import io
from typing import List, Dict, Optional
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from pydantic import BaseModel


class CitationGap(BaseModel):
    id: int
    article_title: str
    official_url: str
    template_kind: str
    template_label: str
    opportunity: str
    snippet_text: str
    section_title: str
    page_path: str
    categories: List[str]


class SearchResponse(BaseModel):
    gaps: List[CitationGap]
    total: int
    limit: int
    offset: int


class StatsResponse(BaseModel):
    total_gaps: int
    by_template_kind: Dict[str, int]
    top_categories: Dict[str, int]


app = FastAPI(
    title="Wikipedia Citation Gaps API",
    description="Search and explore Wikipedia articles needing citations",
    version="1.0.0"
)

DB_PATH = "data/citation_gaps.db"


def get_db_connection():
    """Get database connection."""
    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=503, detail="Database not found. Run zim_parser.py first.")
    return sqlite3.connect(DB_PATH)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Simple web UI for searching citation gaps."""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>Wikipedia Citation Gaps</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .search-box { margin: 20px 0; }
        .search-box input { padding: 10px; width: 400px; }
        .search-box button { padding: 10px 20px; margin-left: 10px; }
        .filters { margin: 20px 0; }
        .filters select { padding: 5px; margin-right: 10px; }
        .results { margin: 20px 0; }
        .gap { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
        .gap-title { font-size: 18px; font-weight: bold; margin-bottom: 5px; }
        .gap-url a { color: #0645ad; text-decoration: none; }
        .gap-template { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 12px; margin-right: 5px; }
        .gap-snippet { margin: 10px 0; font-style: italic; color: #666; }
        .gap-section { font-size: 14px; color: #888; }
        .stats { background: #f9f9f9; padding: 15px; margin: 20px 0; border-radius: 5px; }
        .loading { text-align: center; padding: 20px; }
    </style>
</head>
<body>
    <h1>🔍 Wikipedia Citation Gaps</h1>
    <p>Search for Wikipedia articles that need citations, references, or source improvements.</p>

    <div class="search-box">
        <input type="text" id="query" placeholder="Search articles, topics, or specific citation issues..." />
        <button onclick="search()">Search</button>
    </div>

    <div class="filters">
        <select id="template_filter">
            <option value="">All template types</option>
            <option value="inline_citation_needed">Citation needed</option>
            <option value="box_refimprove">References need improvement</option>
            <option value="box_unreferenced">Unreferenced</option>
            <option value="box_original_research">Original research</option>
            <option value="inline_dead_link">Dead link</option>
            <option value="box_primary_sources">Primary sources</option>
            <option value="box_verifiability">Verifiability</option>
        </select>
        <select id="limit">
            <option value="50">50 results</option>
            <option value="100">100 results</option>
            <option value="200">200 results</option>
        </select>
    </div>

    <div id="stats"></div>
    <div id="results"></div>

    <script>
        async function search() {
            const query = document.getElementById('query').value;
            const template_filter = document.getElementById('template_filter').value;
            const limit = document.getElementById('limit').value;

            document.getElementById('results').innerHTML = '<div class="loading">Searching...</div>';

            try {
                let url = `/api/search?limit=${limit}`;
                if (query) url += `&q=${encodeURIComponent(query)}`;
                if (template_filter) url += `&template_kind=${template_filter}`;

                const response = await fetch(url);
                const data = await response.json();

                displayResults(data);
            } catch (error) {
                document.getElementById('results').innerHTML = '<div class="error">Search failed: ' + error.message + '</div>';
            }
        }

        function displayResults(data) {
            const resultsDiv = document.getElementById('results');

            if (data.gaps.length === 0) {
                resultsDiv.innerHTML = '<p>No results found. Try a different search term.</p>';
                return;
            }

            let html = `<h2>Found ${data.total} results (showing ${data.gaps.length})</h2>`;

            data.gaps.forEach(gap => {
                const categories = gap.categories.join(', ');
                html += `
                    <div class="gap">
                        <div class="gap-title">${escapeHtml(gap.article_title)}</div>
                        <div class="gap-url"><a href="${gap.official_url}" target="_blank">${gap.official_url}</a></div>
                        <span class="gap-template">${gap.template_label}</span>
                        <div class="gap-snippet">"${escapeHtml(gap.snippet_text)}"</div>
                        <div class="gap-section">Section: ${escapeHtml(gap.section_title)}</div>
                        <div style="font-size: 12px; color: #999; margin-top: 5px;">
                            <strong>Opportunity:</strong> ${escapeHtml(gap.opportunity)}<br>
                            <strong>Categories:</strong> ${escapeHtml(categories)}
                        </div>
                    </div>
                `;
            });

            resultsDiv.innerHTML = html;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();

                let html = '<h3>Database Statistics</h3>';
                html += `<p><strong>Total gaps:</strong> ${stats.total_gaps.toLocaleString()}</p>`;

                html += '<p><strong>By template type:</strong></p><ul>';
                for (const [kind, count] of Object.entries(stats.by_template_kind)) {
                    html += `<li>${kind}: ${count.toLocaleString()}</li>`;
                }
                html += '</ul>';

                document.getElementById('stats').innerHTML = html;
            } catch (error) {
                console.error('Failed to load stats:', error);
            }
        }

        // Load stats on page load
        loadStats();

        // Enter key search
        document.getElementById('query').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') search();
        });
    </script>
</body>
</html>
    """)


@app.get("/api/search", response_model=SearchResponse)
async def search_gaps(
    q: Optional[str] = Query(None, description="Search query"),
    template_kind: Optional[str] = Query(None, description="Filter by template kind"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results"),
    offset: int = Query(0, ge=0, description="Results offset")
):
    """Search citation gaps with full-text search and filtering."""
    conn = get_db_connection()

    # Build query
    if q:
        # Use FTS5 for full-text search
        base_query = """
            SELECT g.id, g.article_title, g.official_url, g.template_kind, g.template_label,
                   g.opportunity, g.snippet_text, g.section_title, g.page_path, g.categories
            FROM citation_gaps g
            JOIN citation_gaps_fts fts ON g.id = fts.rowid
            WHERE citation_gaps_fts MATCH ?
        """
        count_query = """
            SELECT COUNT(*)
            FROM citation_gaps g
            JOIN citation_gaps_fts fts ON g.id = fts.rowid
            WHERE citation_gaps_fts MATCH ?
        """
        params = [q]
    else:
        # No search term, select all
        base_query = """
            SELECT id, article_title, official_url, template_kind, template_label,
                   opportunity, snippet_text, section_title, page_path, categories
            FROM citation_gaps
            WHERE 1=1
        """
        count_query = "SELECT COUNT(*) FROM citation_gaps WHERE 1=1"
        params = []

    # Add template_kind filter
    if template_kind:
        base_query += " AND template_kind = ?"
        count_query += " AND template_kind = ?"
        params.append(template_kind)

    # Add pagination
    base_query += " ORDER BY id LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    # Execute queries
    cursor = conn.cursor()
    cursor.execute(base_query, params)
    rows = cursor.fetchall()

    cursor.execute(count_query, params[:-2])  # Remove limit/offset for count
    total = cursor.fetchone()[0]

    conn.close()

    # Convert to response format
    gaps = []
    for row in rows:
        gaps.append(CitationGap(
            id=row[0],
            article_title=row[1],
            official_url=row[2],
            template_kind=row[3],
            template_label=row[4],
            opportunity=row[5],
            snippet_text=row[6],
            section_title=row[7],
            page_path=row[8],
            categories=row[9].split('|') if row[9] else []
        ))

    return SearchResponse(
        gaps=gaps,
        total=total,
        limit=limit,
        offset=offset
    )


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """Get database statistics."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total gaps
    cursor.execute("SELECT COUNT(*) FROM citation_gaps")
    total_gaps = cursor.fetchone()[0]

    # By template kind
    cursor.execute("SELECT template_kind, COUNT(*) FROM citation_gaps GROUP BY template_kind ORDER BY COUNT(*) DESC")
    by_template_kind = dict(cursor.fetchall())

    # Top categories (parse categories and count)
    cursor.execute("SELECT categories FROM citation_gaps WHERE categories IS NOT NULL AND categories != ''")
    category_counts = {}
    for (categories_str,) in cursor.fetchall():
        for category in categories_str.split('|'):
            if category.strip():
                category_counts[category.strip()] = category_counts.get(category.strip(), 0) + 1

    top_categories = dict(sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:20])

    conn.close()

    return StatsResponse(
        total_gaps=total_gaps,
        by_template_kind=by_template_kind,
        top_categories=top_categories
    )


@app.get("/api/all")
async def export_all(format: str = Query("json", regex="^(json|csv)$")):
    """Export all citation gaps as JSON or CSV."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, article_title, official_url, template_kind, template_label,
               opportunity, snippet_text, section_title, page_path, categories
        FROM citation_gaps
        ORDER BY id
    """)
    rows = cursor.fetchall()
    conn.close()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'id', 'article_title', 'official_url', 'template_kind', 'template_label',
            'opportunity', 'snippet_text', 'section_title', 'page_path', 'categories'
        ])

        # Data
        writer.writerows(rows)

        response_content = output.getvalue()
        return Response(
            content=response_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=citation_gaps.csv"}
        )

    else:  # JSON
        gaps = []
        for row in rows:
            gaps.append({
                'id': row[0],
                'article_title': row[1],
                'official_url': row[2],
                'template_kind': row[3],
                'template_label': row[4],
                'opportunity': row[5],
                'snippet_text': row[6],
                'section_title': row[7],
                'page_path': row[8],
                'categories': row[9].split('|') if row[9] else []
            })

        return {"gaps": gaps}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)