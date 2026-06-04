#!/usr/bin/env python3
"""
Targeted Wikipedia pipeline for monday.com citation gap analysis.
Instead of scanning all ~7M articles, filters by title/topic first,
then parses only relevant articles for citation gaps and references.
"""

import re
import json
import logging
import sqlite3
import time
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Iterator, Dict, Set
from bs4 import BeautifulSoup
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data/pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

# ── Topic keywords for filtering ──────────────────────────────────────

# Tier 1: Direct mentions (always include)
TIER1_EXACT = {
    'monday.com', 'Monday.com',
    'Asana (software)', 'Asana (company)',
    'ClickUp', 'Notion (productivity software)',
    'Jira (software)', 'Trello',
    'Wrike', 'Smartsheet', 'Basecamp (software)',
    'Airtable', 'Teamwork (software)',
    'Microsoft Project', 'Microsoft Planner',
    'Planview', 'Workfront', 'Celoxis',
    'Linear (software)', 'Height (software)',
    'Hive (software)', 'Zoho Projects',
}

# Tier 2: Broad topic keywords (title must contain)
TIER2_KEYWORDS = [
    # Core PM concepts
    'project management', 'task management', 'work management',
    'portfolio management', 'resource management',
    'project planning', 'project tracking',
    # Methodologies
    'agile software development', 'scrum', 'kanban',
    'waterfall model', 'lean software development',
    'extreme programming', 'sprint (software)',
    # Tools & concepts
    'gantt chart', 'work breakdown structure',
    'critical path method', 'pert chart',
    'burndown chart', 'backlog (software)',
    'user story', 'product backlog',
    # Collaboration
    'collaboration software', 'collaborative software',
    'productivity software', 'groupware',
    'team collaboration', 'workflow management',
    'business process management',
    # CRM & related
    'customer relationship management',
    'enterprise resource planning',
    'software as a service', 'cloud computing',
    # Work concepts
    'remote work', 'telecommuting',
    'digital workplace', 'work from home',
    'hybrid work', 'distributed team',
    # Industry
    'project manager', 'product manager',
    'project management software',
    'issue tracking system', 'bug tracking',
    'time tracking', 'resource allocation',
    # Company related
    'tel aviv', 'israeli technology', 'startup nation',
    'new york stock exchange', 'nasdaq',
    'initial public offering',
    # Broader SaaS
    'saas', 'low-code', 'no-code',
    'workflow automation', 'business intelligence',
    'data visualization', 'dashboard (business)',
]

# Compile patterns for efficient matching
TIER2_PATTERNS = [re.compile(re.escape(kw), re.IGNORECASE) for kw in TIER2_KEYWORDS]


@dataclass
class ArticleRecord:
    """A parsed article with its metadata and citation gaps."""
    title: str
    url: str
    page_path: str
    tier: int  # 1=direct competitor/product, 2=topic match
    match_reason: str
    word_count: int = 0
    ref_count: int = 0
    citation_needed_count: int = 0
    dead_link_count: int = 0
    unreferenced: bool = False
    refimprove: bool = False
    original_research: bool = False
    categories: List[str] = field(default_factory=list)
    references: List[Dict] = field(default_factory=list)
    citation_gaps: List[Dict] = field(default_factory=list)
    mentions_monday: bool = False
    mentions_competitors: List[str] = field(default_factory=list)
    infobox_data: Dict = field(default_factory=dict)


COMPETITOR_NAMES = [
    'monday.com', 'asana', 'clickup', 'notion', 'jira', 'trello',
    'wrike', 'smartsheet', 'basecamp', 'airtable', 'teamwork',
    'microsoft project', 'microsoft planner', 'planview', 'workfront',
    'linear', 'height app', 'hive', 'zoho projects', 'celoxis',
    'miro', 'figma', 'confluence', 'microsoft teams',
]


class TargetedPipeline:
    """Targeted Wikipedia extraction pipeline."""

    def __init__(self, zim_path: str, db_path: str = 'data/wiki_analysis.db'):
        self.zim_path = Path(zim_path)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        import libzim
        self.archive = libzim.Archive(str(self.zim_path))
        logger.info(f"Opened ZIM: {self.zim_path} ({self.archive.entry_count:,} entries)")

        self._init_db()

    def _init_db(self):
        """Create the analysis database."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")

        conn.executescript('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT UNIQUE,
                url TEXT,
                page_path TEXT,
                tier INTEGER,
                match_reason TEXT,
                word_count INTEGER DEFAULT 0,
                ref_count INTEGER DEFAULT 0,
                citation_needed_count INTEGER DEFAULT 0,
                dead_link_count INTEGER DEFAULT 0,
                unreferenced INTEGER DEFAULT 0,
                refimprove INTEGER DEFAULT 0,
                original_research INTEGER DEFAULT 0,
                categories TEXT DEFAULT '',
                mentions_monday INTEGER DEFAULT 0,
                mentions_competitors TEXT DEFAULT '',
                infobox_json TEXT DEFAULT '{}',
                parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS citation_gaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER REFERENCES articles(id),
                template_kind TEXT,
                template_label TEXT,
                section_title TEXT,
                snippet TEXT,
                opportunity TEXT
            );

            CREATE TABLE IF NOT EXISTS references_found (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER REFERENCES articles(id),
                ref_type TEXT,
                ref_url TEXT,
                ref_text TEXT,
                ref_title TEXT,
                is_dead INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS competitor_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER REFERENCES articles(id),
                competitor TEXT,
                context TEXT,
                section_title TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_articles_tier ON articles(tier);
            CREATE INDEX IF NOT EXISTS idx_articles_monday ON articles(mentions_monday);
            CREATE INDEX IF NOT EXISTS idx_gaps_article ON citation_gaps(article_id);
            CREATE INDEX IF NOT EXISTS idx_refs_article ON references_found(article_id);
            CREATE INDEX IF NOT EXISTS idx_mentions_article ON competitor_mentions(article_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                title, categories, match_reason,
                content='articles', content_rowid='id'
            );
        ''')
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")

    # ── Phase 1: Title scan ──────────────────────────────────────────

    def scan_titles(self) -> List[tuple]:
        """Scan ZIM index for relevant article titles. Returns (path, title, tier, reason)."""
        logger.info("Phase 1: Scanning article titles...")
        matches = []
        skipped = 0
        total = self.archive.entry_count

        for idx in tqdm(range(total), desc="Scanning titles", mininterval=5):
            try:
                entry = self.archive._get_entry_by_id(idx)
                if not entry.is_redirect:
                    path = entry.path
                    title = entry.title

                    if not title:
                        continue
                    # Skip non-article entries
                    if title.startswith(('File:', 'Category:', 'Template:', 'Wikipedia:', 'Help:', 'Portal:', 'Draft:', 'Module:', 'MediaWiki:', 'User:', 'Talk:')):
                        continue

                    # Tier 1 check: exact title match
                    if title in TIER1_EXACT:
                        matches.append((path, title, 1, f'exact:{title}'))
                        continue

                    # Tier 2 check: keyword in title
                    title_lower = title.lower()
                    for i, pattern in enumerate(TIER2_PATTERNS):
                        if pattern.search(title_lower):
                            matches.append((path, title, 2, f'keyword:{TIER2_KEYWORDS[i]}'))
                            break
                else:
                    skipped += 1
            except Exception:
                continue

        logger.info(f"Title scan complete: {len(matches)} relevant articles found "
                     f"(Tier 1: {sum(1 for m in matches if m[2]==1)}, "
                     f"Tier 2: {sum(1 for m in matches if m[2]==2)}), "
                     f"{skipped:,} redirects skipped")
        return matches

    # ── Phase 2: Parse relevant articles ─────────────────────────────

    def parse_article(self, path: str, title: str, tier: int, reason: str) -> Optional[ArticleRecord]:
        """Parse a single article for citation gaps and references."""
        try:
            entry = self.archive.get_entry_by_path(path)
            item = entry.get_item()
            html = bytes(item.content).decode('utf-8', errors='replace')
        except Exception as e:
            logger.debug(f"Failed to read {path}: {e}")
            return None

        if len(html) < 100:
            return None

        soup = BeautifulSoup(html, 'lxml')
        page_path = path.replace(' ', '_')

        record = ArticleRecord(
            title=title,
            url=f"https://en.wikipedia.org/wiki/{page_path}",
            page_path=page_path,
            tier=tier,
            match_reason=reason,
        )

        # Word count
        body = soup.find('body') or soup
        text = body.get_text(separator=' ', strip=True)
        record.word_count = len(text.split())

        # ── Citation gaps ────────────────────────────────────────
        self._extract_citation_gaps(soup, record)

        # ── References ───────────────────────────────────────────
        self._extract_references(soup, record)

        # ── Competitor mentions ──────────────────────────────────
        self._extract_competitor_mentions(soup, text, record)

        # ── Categories ───────────────────────────────────────────
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if 'Category:' in href:
                cat = href.split('Category:')[-1].replace('_', ' ')
                if cat and len(record.categories) < 20:
                    record.categories.append(cat)

        # ── Infobox ──────────────────────────────────────────────
        infobox = soup.find('table', class_=re.compile(r'infobox', re.I))
        if infobox:
            record.infobox_data = self._parse_infobox(infobox)

        return record

    def _extract_citation_gaps(self, soup: BeautifulSoup, record: ArticleRecord):
        """Extract all citation-related issues from the article."""
        full_text = soup.get_text().lower()

        # Check for article-level banners
        if re.search(r'refimprove|more\s*citations?\s*needed|additional\s*citations', full_text):
            record.refimprove = True
        if re.search(r'unreferenced|no\s*footnotes|lacks?\s*references', full_text):
            record.unreferenced = True
        if re.search(r'original\s*research', full_text):
            record.original_research = True

        # Count inline citation-needed tags
        cn_patterns = [
            re.compile(r'citation\s*needed', re.I),
            re.compile(r'class="[^"]*noprint\s+Inline-Template[^"]*"', re.I),
        ]
        for p in cn_patterns:
            record.citation_needed_count += len(p.findall(str(soup)))

        # Detailed gap extraction
        gap_configs = [
            ('citation_needed', r'citation\s*needed', 'Citation needed', 'Add inline citation'),
            ('refimprove', r'refimprove|more\s*citations', 'Needs more references', 'Add reliable sources'),
            ('unreferenced', r'unreferenced|no\s*footnotes', 'Unreferenced section', 'Add basic references'),
            ('original_research', r'original\s*research', 'Original research', 'Replace with sourced claims'),
            ('dead_link', r'dead\s*link|link\s*rot', 'Dead link', 'Fix or replace broken link'),
            ('primary_sources', r'primary\s*sources?|relies.*primary', 'Primary sources only', 'Add independent sources'),
            ('disputed', r'disputed|accuracy.*dispute', 'Disputed content', 'Add authoritative sources'),
            ('pov', r'neutrality.*disputed|pov|point\s*of\s*view', 'POV issues', 'Add balanced sourcing'),
        ]

        for kind, pattern, label, opportunity in gap_configs:
            for el in soup.find_all(text=re.compile(pattern, re.I)):
                parent = el.parent
                if parent:
                    section = self._find_section(parent)
                    snippet = self._get_snippet(parent)
                    record.citation_gaps.append({
                        'template_kind': kind,
                        'template_label': label,
                        'section_title': section,
                        'snippet': snippet[:500],
                        'opportunity': opportunity,
                    })

        # Also check ambox (article message box) elements
        for ambox in soup.find_all(class_=re.compile(r'ambox', re.I)):
            ambox_text = ambox.get_text().lower()
            if any(kw in ambox_text for kw in ['citation', 'source', 'reference', 'verify', 'unreferenced']):
                record.citation_gaps.append({
                    'template_kind': 'ambox_maintenance',
                    'template_label': 'Maintenance banner',
                    'section_title': 'Article-level',
                    'snippet': ambox.get_text()[:500].strip(),
                    'opportunity': 'Address article-level citation issues',
                })

        # Dead links
        record.dead_link_count = len(re.findall(r'dead\s*link|link\s*rot|\[dead\s*link\]', full_text))

    def _extract_references(self, soup: BeautifulSoup, record: ArticleRecord):
        """Extract all references/citations from the article."""
        refs = []

        # <cite> elements
        for cite in soup.find_all('cite'):
            ref = self._parse_cite(cite)
            if ref:
                refs.append(ref)

        # <ref> or reference list items
        for li in soup.find_all('li', id=re.compile(r'^cite_note')):
            ref = self._parse_ref_li(li)
            if ref:
                refs.append(ref)

        # Fallback: links in references section
        ref_section = soup.find(id=re.compile(r'references|notes|citations', re.I))
        if ref_section:
            for a in ref_section.find_all('a', href=True):
                href = a.get('href', '')
                if href.startswith('http'):
                    refs.append({
                        'ref_type': 'link',
                        'ref_url': href,
                        'ref_text': a.get_text()[:300],
                        'ref_title': '',
                        'is_dead': 0,
                    })

        record.references = refs
        record.ref_count = len(refs)

    def _parse_cite(self, cite) -> Optional[Dict]:
        """Parse a <cite> element into a reference dict."""
        text = cite.get_text(strip=True)[:300]
        url = ''
        title = ''
        for a in cite.find_all('a', href=True):
            href = a.get('href', '')
            if href.startswith('http'):
                url = href
                title = a.get_text(strip=True)
                break
        if text or url:
            return {
                'ref_type': 'cite',
                'ref_url': url,
                'ref_text': text,
                'ref_title': title,
                'is_dead': 0,
            }
        return None

    def _parse_ref_li(self, li) -> Optional[Dict]:
        """Parse a reference list item."""
        text = li.get_text(strip=True)[:300]
        url = ''
        title = ''
        for a in li.find_all('a', href=True):
            href = a.get('href', '')
            if href.startswith('http'):
                url = href
                title = a.get_text(strip=True)
                break
        if text:
            return {
                'ref_type': 'footnote',
                'ref_url': url,
                'ref_text': text,
                'ref_title': title,
                'is_dead': 1 if 'dead link' in text.lower() else 0,
            }
        return None

    def _extract_competitor_mentions(self, soup: BeautifulSoup, text: str, record: ArticleRecord):
        """Find mentions of monday.com and competitors in the article text."""
        text_lower = text.lower()

        if 'monday.com' in text_lower or 'monday com' in text_lower:
            record.mentions_monday = True

        for comp in COMPETITOR_NAMES:
            if comp.lower() in text_lower:
                record.mentions_competitors.append(comp)
                # Find context
                idx = text_lower.find(comp.lower())
                start = max(0, idx - 100)
                end = min(len(text), idx + len(comp) + 100)
                context = text[start:end].strip()

                # Find section
                # Walk backwards from the match position to find heading
                section = 'Unknown'
                for h in soup.find_all(re.compile(r'^h[1-6]$')):
                    section = h.get_text(strip=True)

                record.citation_gaps  # just reference to avoid unused
                # We store mentions separately

    def _find_section(self, element) -> str:
        """Find the nearest heading above this element."""
        current = element
        while current:
            prev = current.find_previous(re.compile(r'^h[1-6]$'))
            if prev:
                return prev.get_text(strip=True)
            current = current.parent
        return 'Introduction'

    def _get_snippet(self, element, max_chars=500) -> str:
        """Get text context around an element."""
        parent = element.find_parent(['p', 'div', 'td', 'li'])
        if parent:
            return parent.get_text(strip=True)[:max_chars]
        return element.get_text(strip=True)[:max_chars]

    def _parse_infobox(self, table) -> Dict:
        """Extract key-value pairs from an infobox table."""
        data = {}
        for row in table.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(strip=True)
                if key and val and len(key) < 50:
                    data[key] = val[:200]
        return data

    # ── Phase 3: Save to DB ──────────────────────────────────────────

    def save_record(self, conn: sqlite3.Connection, record: ArticleRecord) -> int:
        """Save an ArticleRecord to the database. Returns article_id."""
        cursor = conn.execute('''
            INSERT OR REPLACE INTO articles
            (title, url, page_path, tier, match_reason, word_count, ref_count,
             citation_needed_count, dead_link_count, unreferenced, refimprove,
             original_research, categories, mentions_monday, mentions_competitors,
             infobox_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.title, record.url, record.page_path, record.tier,
            record.match_reason, record.word_count, record.ref_count,
            record.citation_needed_count, record.dead_link_count,
            int(record.unreferenced), int(record.refimprove),
            int(record.original_research),
            '|'.join(record.categories),
            int(record.mentions_monday),
            ','.join(record.mentions_competitors),
            json.dumps(record.infobox_data),
        ))
        article_id = cursor.lastrowid

        # Save citation gaps
        for gap in record.citation_gaps:
            conn.execute('''
                INSERT INTO citation_gaps (article_id, template_kind, template_label,
                    section_title, snippet, opportunity)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (article_id, gap['template_kind'], gap['template_label'],
                  gap['section_title'], gap['snippet'], gap['opportunity']))

        # Save references
        for ref in record.references:
            conn.execute('''
                INSERT INTO references_found (article_id, ref_type, ref_url,
                    ref_text, ref_title, is_dead)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (article_id, ref['ref_type'], ref['ref_url'],
                  ref['ref_text'], ref['ref_title'], ref['is_dead']))

        # Save competitor mentions
        for comp in record.mentions_competitors:
            conn.execute('''
                INSERT INTO competitor_mentions (article_id, competitor, context, section_title)
                VALUES (?, ?, ?, ?)
            ''', (article_id, comp, '', ''))

        return article_id

    # ── Run full pipeline ────────────────────────────────────────────

    def run(self):
        """Execute the full targeted pipeline."""
        start_time = time.time()

        # Phase 1: Scan titles
        matches = self.scan_titles()

        if not matches:
            logger.error("No relevant articles found!")
            return

        # Phase 2+3: Parse and save
        logger.info(f"Phase 2: Parsing {len(matches)} relevant articles...")
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        parsed = 0
        failed = 0
        with_gaps = 0
        with_monday = 0

        for path, title, tier, reason in tqdm(matches, desc="Parsing articles"):
            try:
                record = self.parse_article(path, title, tier, reason)
                if record:
                    self.save_record(conn, record)
                    parsed += 1
                    if record.citation_gaps:
                        with_gaps += 1
                    if record.mentions_monday:
                        with_monday += 1

                    if parsed % 50 == 0:
                        conn.commit()
                        logger.info(f"  Parsed {parsed}/{len(matches)} — "
                                    f"{with_gaps} with gaps, {with_monday} mention monday.com")
                else:
                    failed += 1
            except Exception as e:
                logger.warning(f"Error parsing {title}: {e}")
                failed += 1

        conn.commit()

        # Rebuild FTS index
        logger.info("Building full-text search index...")
        try:
            conn.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
            conn.commit()
        except Exception as e:
            logger.warning(f"FTS rebuild issue (non-fatal): {e}")

        conn.close()

        elapsed = time.time() - start_time

        # ── Summary ──────────────────────────────────────────────
        summary = self._generate_summary(elapsed, len(matches), parsed, failed, with_gaps, with_monday)
        logger.info(summary)

        # Save summary to file
        with open('data/pipeline_summary.json', 'w') as f:
            json.dump({
                'elapsed_seconds': round(elapsed, 1),
                'total_matches': len(matches),
                'parsed': parsed,
                'failed': failed,
                'with_gaps': with_gaps,
                'with_monday_mentions': with_monday,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            }, f, indent=2)

        return summary

    def _generate_summary(self, elapsed, total_matches, parsed, failed, with_gaps, with_monday) -> str:
        """Generate a human-readable summary."""
        conn = sqlite3.connect(str(self.db_path))

        # Stats queries
        total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        total_gaps_rows = conn.execute("SELECT COUNT(*) FROM citation_gaps").fetchone()[0]
        total_refs = conn.execute("SELECT COUNT(*) FROM references_found").fetchone()[0]
        total_mentions = conn.execute("SELECT COUNT(*) FROM competitor_mentions").fetchone()[0]

        tier1 = conn.execute("SELECT COUNT(*) FROM articles WHERE tier=1").fetchone()[0]
        tier2 = conn.execute("SELECT COUNT(*) FROM articles WHERE tier=2").fetchone()[0]

        # Gap breakdown
        gap_types = conn.execute(
            "SELECT template_kind, COUNT(*) FROM citation_gaps GROUP BY template_kind ORDER BY COUNT(*) DESC"
        ).fetchall()

        # Top articles by citation gaps
        top_gap_articles = conn.execute('''
            SELECT a.title, COUNT(g.id) as gap_count
            FROM articles a JOIN citation_gaps g ON a.id = g.article_id
            GROUP BY a.id ORDER BY gap_count DESC LIMIT 10
        ''').fetchall()

        # Monday mentions
        monday_articles = conn.execute(
            "SELECT title FROM articles WHERE mentions_monday=1"
        ).fetchall()

        # Competitor mention counts
        comp_counts = conn.execute(
            "SELECT competitor, COUNT(*) FROM competitor_mentions GROUP BY competitor ORDER BY COUNT(*) DESC LIMIT 15"
        ).fetchall()

        conn.close()

        lines = [
            "=" * 60,
            "WIKIPEDIA CITATION GAP ANALYSIS — PIPELINE COMPLETE",
            "=" * 60,
            f"Runtime: {elapsed/60:.1f} minutes",
            f"Articles scanned (title): {total_matches:,}",
            f"Articles parsed (HTML): {parsed:,} ({failed} failed)",
            f"  Tier 1 (direct products): {tier1}",
            f"  Tier 2 (topic matches): {tier2}",
            "",
            f"Total citation gaps found: {total_gaps_rows:,}",
            f"Articles with gaps: {with_gaps}",
            f"Total references indexed: {total_refs:,}",
            f"Competitor mentions: {total_mentions:,}",
            "",
            "── Gap Breakdown ──",
        ]
        for kind, count in gap_types:
            lines.append(f"  {kind}: {count}")

        lines.append("")
        lines.append("── Top 10 Articles by Citation Gaps ──")
        for title, count in top_gap_articles:
            lines.append(f"  [{count} gaps] {title}")

        lines.append("")
        lines.append(f"── Articles Mentioning monday.com ({len(monday_articles)}) ──")
        for (title,) in monday_articles[:20]:
            lines.append(f"  • {title}")

        lines.append("")
        lines.append("── Competitor Mention Counts ──")
        for comp, count in comp_counts:
            lines.append(f"  {comp}: {count}")

        return '\n'.join(lines)


if __name__ == '__main__':
    zim_file = sys.argv[1] if len(sys.argv) > 1 else 'data/wikipedia_en_all_nopic_2026-03.zim'

    pipeline = TargetedPipeline(zim_file)
    summary = pipeline.run()
    print(summary)
