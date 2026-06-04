#!/usr/bin/env python3
"""
Wikipedia ZIM file parser for citation gap extraction.
Supports libzim (primary) and zimply (fallback).
"""

import re
import logging
from typing import Iterator, Dict, List, Optional, Union
from dataclasses import dataclass
from bs4 import BeautifulSoup
import sqlite3
import csv
from pathlib import Path
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CitationGap:
    article_title: str
    official_url: str
    template_kind: str
    template_label: str
    opportunity: str
    snippet_text: str
    section_title: str
    page_path: str
    categories: List[str]


class ZIMParser:
    """Parse ZIM files and extract citation gaps."""

    # Template patterns to match
    TEMPLATE_PATTERNS = {
        'inline_citation_needed': {
            'patterns': [
                r'citation\s*needed',
                r'\bcn\b',
                r'\bfact\b',
                r'verify\s*source',
                r'verification\s*needed'
            ],
            'label': 'Citation needed',
            'opportunity': 'Add inline citation for this claim'
        },
        'box_refimprove': {
            'patterns': [
                r'refimprove',
                r'more\s*citations?\s*needed',
                r'additional\s*citations'
            ],
            'label': 'References need improvement',
            'opportunity': 'Add more reliable sources to strengthen article'
        },
        'box_unreferenced': {
            'patterns': [
                r'unreferenced',
                r'no\s*footnotes?',
                r'lacks?\s*references?'
            ],
            'label': 'Unreferenced',
            'opportunity': 'Add basic references to support key claims'
        },
        'box_original_research': {
            'patterns': [
                r'original\s*research',
                r'unsourced\s*claims?'
            ],
            'label': 'Original research',
            'opportunity': 'Replace unsourced claims with verifiable sources'
        },
        'inline_dead_link': {
            'patterns': [
                r'dead\s*links?',
                r'webarchive',
                r'link\s*not\s*found'
            ],
            'label': 'Dead link',
            'opportunity': 'Fix or replace dead external links'
        },
        'box_primary_sources': {
            'patterns': [
                r'primary\s*sources?',
                r'reliable\s*sources?',
                r'independent\s*sources?'
            ],
            'label': 'Primary sources',
            'opportunity': 'Add secondary and independent sources'
        },
        'box_verifiability': {
            'patterns': [
                r'verifiability',
                r'verify\s*sources?'
            ],
            'label': 'Verifiability',
            'opportunity': 'Add verifiable sources for claims'
        }
    }

    # CSS classes that indicate maintenance templates
    MAINTENANCE_CSS_CLASSES = [
        'ambox-content',
        'ambox-Verifiability',
        'mbox-text',
        'hatnote',
        'dablink'
    ]

    def __init__(self, zim_path: str):
        self.zim_path = Path(zim_path)
        self.archive = None
        self.use_libzim = True
        self._init_zim()

    def _init_zim(self):
        """Initialize ZIM reader with fallback support."""
        try:
            import libzim
            self.archive = libzim.Archive(str(self.zim_path))
            logger.info(f"Using libzim to read {self.zim_path}")
        except (ImportError, Exception) as e:
            logger.warning(f"libzim failed: {e}, trying zimply...")
            try:
                import zimply
                self.archive = zimply.ZIMFile(str(self.zim_path))
                self.use_libzim = False
                logger.info(f"Using zimply to read {self.zim_path}")
            except (ImportError, Exception) as e:
                raise RuntimeError(f"Cannot read ZIM file with libzim or zimply: {e}")

    def _get_all_entries(self) -> Iterator[tuple]:
        """Get all entries from ZIM file."""
        if self.use_libzim:
            # libzim approach
            for entry_idx in range(self.archive.entry_count):
                try:
                    entry = self.archive._get_entry_by_id(entry_idx)
                    if entry.is_article():
                        yield (entry.path, entry.title)
                except:
                    continue
        else:
            # zimply approach
            for article in self.archive.articles():
                yield (article.url, article.title)

    def _get_article_content(self, path: str) -> Optional[str]:
        """Get article HTML content."""
        try:
            if self.use_libzim:
                entry = self.archive.get_entry_by_path(path)
                if entry.is_article():
                    return bytes(entry.get_item().content).decode('utf-8')
            else:
                article = self.archive[path]
                return article.content.decode('utf-8') if article.content else None
        except Exception as e:
            logger.debug(f"Failed to read {path}: {e}")
            return None

    def _extract_page_path(self, path: str) -> str:
        """Extract page path for Wikipedia URL."""
        # Remove namespace prefixes like 'A/'
        if '/' in path:
            return path.split('/', 1)[1]
        return path

    def _extract_categories(self, soup: BeautifulSoup) -> List[str]:
        """Extract categories from article HTML."""
        categories = []
        # Look for category links
        for link in soup.find_all('a'):
            href = link.get('href', '')
            if '/wiki/Category:' in href:
                cat_name = href.split('/wiki/Category:')[-1].replace('_', ' ')
                categories.append(cat_name)
        return categories[:10]  # Limit to first 10 categories

    def _find_section_title(self, element, soup: BeautifulSoup) -> str:
        """Find the section title for a given element."""
        # Look backward for the nearest heading
        current = element
        while current:
            if current.name and current.name.startswith('h') and current.name[1:].isdigit():
                return current.get_text().strip()
            current = current.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        return "Introduction"

    def _extract_snippet(self, element, max_chars: int = 500) -> str:
        """Extract surrounding text context."""
        # Get parent paragraph or section
        parent = element.find_parent(['p', 'div', 'section'])
        if parent:
            text = parent.get_text()
            # Find element position in parent text
            element_text = element.get_text()
            if element_text in text:
                pos = text.find(element_text)
                start = max(0, pos - max_chars // 2)
                end = min(len(text), pos + len(element_text) + max_chars // 2)
                snippet = text[start:end].strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(text):
                    snippet = snippet + "..."
                return snippet
        return element.get_text()[:max_chars]

    def _detect_citation_gaps(self, html: str, article_title: str, page_path: str) -> List[CitationGap]:
        """Detect citation gaps in article HTML."""
        gaps = []
        soup = BeautifulSoup(html, 'lxml')

        # Extract categories once
        categories = self._extract_categories(soup)

        # Search for template patterns in text and CSS classes
        for template_kind, config in self.TEMPLATE_PATTERNS.items():
            patterns = config['patterns']

            # Search in text content
            for pattern in patterns:
                regex = re.compile(pattern, re.IGNORECASE)

                # Find in text nodes
                for element in soup.find_all(text=regex):
                    parent = element.parent
                    if parent:
                        gap = CitationGap(
                            article_title=article_title,
                            official_url=f"https://en.wikipedia.org/wiki/{page_path}",
                            template_kind=template_kind,
                            template_label=config['label'],
                            opportunity=config['opportunity'],
                            snippet_text=self._extract_snippet(parent),
                            section_title=self._find_section_title(parent, soup),
                            page_path=page_path,
                            categories=categories
                        )
                        gaps.append(gap)

                # Find in element attributes and classes
                for element in soup.find_all():
                    element_text = element.get_text().lower()
                    element_class = ' '.join(element.get('class', [])).lower()
                    element_id = element.get('id', '').lower()

                    if (regex.search(element_text) or
                        regex.search(element_class) or
                        regex.search(element_id)):

                        gap = CitationGap(
                            article_title=article_title,
                            official_url=f"https://en.wikipedia.org/wiki/{page_path}",
                            template_kind=template_kind,
                            template_label=config['label'],
                            opportunity=config['opportunity'],
                            snippet_text=self._extract_snippet(element),
                            section_title=self._find_section_title(element, soup),
                            page_path=page_path,
                            categories=categories
                        )
                        gaps.append(gap)

        # Also check for maintenance CSS classes
        for css_class in self.MAINTENANCE_CSS_CLASSES:
            for element in soup.find_all(class_=css_class):
                gap = CitationGap(
                    article_title=article_title,
                    official_url=f"https://en.wikipedia.org/wiki/{page_path}",
                    template_kind="maintenance_template",
                    template_label="Maintenance needed",
                    opportunity="Review and address maintenance issues",
                    snippet_text=self._extract_snippet(element),
                    section_title=self._find_section_title(element, soup),
                    page_path=page_path,
                    categories=categories
                )
                gaps.append(gap)

        return gaps

    def extract_citation_gaps(self) -> Iterator[CitationGap]:
        """Extract citation gaps from all articles in ZIM file."""
        logger.info("Starting citation gap extraction...")

        total_entries = self.archive.entry_count if self.use_libzim else len(self.archive)
        processed = 0

        with tqdm(total=total_entries, desc="Processing articles") as pbar:
            for path, title in self._get_all_entries():
                try:
                    # Skip non-article entries (images, redirects, etc.)
                    if not title or title.startswith('File:') or title.startswith('Category:'):
                        pbar.update(1)
                        continue

                    content = self._get_article_content(path)
                    if not content:
                        pbar.update(1)
                        continue

                    page_path = self._extract_page_path(path)
                    gaps = self._detect_citation_gaps(content, title, page_path)

                    for gap in gaps:
                        yield gap

                    processed += 1
                    if processed % 1000 == 0:
                        logger.info(f"Processed {processed} articles, found gaps in current batch")

                except Exception as e:
                    logger.debug(f"Error processing {path}: {e}")

                pbar.update(1)

        logger.info(f"Completed processing {processed} articles")


def create_database(db_path: str):
    """Create SQLite database with FTS5 index."""
    conn = sqlite3.connect(db_path)

    # Main table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS citation_gaps (
            id INTEGER PRIMARY KEY,
            article_title TEXT,
            official_url TEXT,
            template_kind TEXT,
            template_label TEXT,
            opportunity TEXT,
            snippet_text TEXT,
            section_title TEXT,
            page_path TEXT,
            categories TEXT
        )
    ''')

    # FTS5 index for full-text search
    conn.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS citation_gaps_fts USING fts5(
            article_title,
            template_label,
            opportunity,
            snippet_text,
            section_title,
            categories,
            content='citation_gaps',
            content_rowid='id'
        )
    ''')

    # Trigger to keep FTS5 in sync
    conn.execute('''
        CREATE TRIGGER IF NOT EXISTS citation_gaps_ai AFTER INSERT ON citation_gaps BEGIN
            INSERT INTO citation_gaps_fts(rowid, article_title, template_label, opportunity, snippet_text, section_title, categories)
            VALUES (new.id, new.article_title, new.template_label, new.opportunity, new.snippet_text, new.section_title, new.categories);
        END
    ''')

    conn.commit()
    conn.close()


def save_to_database(gaps: Iterator[CitationGap], db_path: str):
    """Save citation gaps to SQLite database."""
    create_database(db_path)
    conn = sqlite3.connect(db_path)

    batch = []
    batch_size = 1000

    for gap in gaps:
        batch.append((
            gap.article_title,
            gap.official_url,
            gap.template_kind,
            gap.template_label,
            gap.opportunity,
            gap.snippet_text,
            gap.section_title,
            gap.page_path,
            '|'.join(gap.categories)
        ))

        if len(batch) >= batch_size:
            conn.executemany('''
                INSERT INTO citation_gaps
                (article_title, official_url, template_kind, template_label, opportunity, snippet_text, section_title, page_path, categories)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch)
            conn.commit()
            batch = []

    # Insert remaining batch
    if batch:
        conn.executemany('''
            INSERT INTO citation_gaps
            (article_title, official_url, template_kind, template_label, opportunity, snippet_text, section_title, page_path, categories)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', batch)
        conn.commit()

    conn.close()


def export_to_csv(db_path: str, csv_path: str):
    """Export database to CSV."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM citation_gaps')
    rows = cursor.fetchall()

    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Header
        writer.writerow([
            'id', 'article_title', 'official_url', 'template_kind', 'template_label',
            'opportunity', 'snippet_text', 'section_title', 'page_path', 'categories'
        ])

        # Data
        writer.writerows(rows)

    conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python zim_parser.py <path_to_zim_file>")
        sys.exit(1)

    zim_path = sys.argv[1]
    db_path = "data/citation_gaps.db"
    csv_path = "data/citation_gaps.csv"

    # Parse ZIM and extract gaps
    parser = ZIMParser(zim_path)
    gaps = parser.extract_citation_gaps()

    # Save to database
    logger.info("Saving to database...")
    save_to_database(gaps, db_path)

    # Export to CSV
    logger.info("Exporting to CSV...")
    export_to_csv(db_path, csv_path)

    logger.info("Citation gap extraction complete!")