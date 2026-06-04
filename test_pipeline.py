#!/usr/bin/env python3
"""
Test script to verify the citation gap extraction pipeline.
"""

import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from zim_parser import CitationGap, create_database, save_to_database, export_to_csv

def create_mock_citation_gaps():
    """Create mock citation gaps for testing."""
    gaps = [
        CitationGap(
            article_title="Climate Change",
            official_url="https://en.wikipedia.org/wiki/Climate_change",
            template_kind="inline_citation_needed",
            template_label="Citation needed",
            opportunity="Add inline citation for this claim",
            snippet_text="Global warming is causing ice caps to melt [citation needed]. This has been observed across multiple regions.",
            section_title="Effects",
            page_path="Climate_change",
            categories=["Environment", "Climate science", "Global warming"]
        ),
        CitationGap(
            article_title="Artificial Intelligence",
            official_url="https://en.wikipedia.org/wiki/Artificial_intelligence",
            template_kind="box_refimprove",
            template_label="References need improvement",
            opportunity="Add more reliable sources to strengthen article",
            snippet_text="This article needs additional citations for verification. The current sources may not be sufficient to support all claims made.",
            section_title="Introduction",
            page_path="Artificial_intelligence",
            categories=["Computer science", "AI", "Technology"]
        ),
        CitationGap(
            article_title="Quantum Computing",
            official_url="https://en.wikipedia.org/wiki/Quantum_computing",
            template_kind="inline_dead_link",
            template_label="Dead link",
            opportunity="Fix or replace dead external links",
            snippet_text="Recent advances in quantum supremacy have been demonstrated [dead link]. Multiple research groups are competing.",
            section_title="Recent developments",
            page_path="Quantum_computing",
            categories=["Physics", "Computing", "Quantum mechanics"]
        )
    ]
    return gaps


def test_database_operations():
    """Test database creation and operations."""
    print("🧪 Testing database operations...")

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_gaps.db")
        csv_path = os.path.join(temp_dir, "test_gaps.csv")

        # Create mock data
        gaps = create_mock_citation_gaps()

        # Test database creation and saving
        save_to_database(iter(gaps), db_path)

        # Verify data was saved
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM citation_gaps")
        count = cursor.fetchone()[0]
        print(f"✅ Saved {count} citation gaps to database")

        # Test FTS5 search
        cursor.execute("SELECT COUNT(*) FROM citation_gaps_fts WHERE citation_gaps_fts MATCH 'climate'")
        search_count = cursor.fetchone()[0]
        print(f"✅ FTS5 search found {search_count} results for 'climate'")

        # Test CSV export
        export_to_csv(db_path, csv_path)

        with open(csv_path, 'r') as f:
            csv_lines = f.readlines()
        print(f"✅ CSV export created with {len(csv_lines)} lines (including header)")

        conn.close()


def test_template_detection():
    """Test template pattern detection."""
    print("\n🧪 Testing template detection patterns...")

    from zim_parser import ZIMParser

    # Test HTML samples with different citation gap patterns
    test_cases = [
        {
            'html': '<p>This statement needs verification <sup class="noprint Inline-Template Template-Fact">[citation needed]</sup>.</p>',
            'expected': 'inline_citation_needed',
            'title': 'Inline citation needed'
        },
        {
            'html': '<div class="ambox ambox-content ambox-Refimprove"><div class="ambox-text">This article <b>needs additional citations for verification</b>.</div></div>',
            'expected': 'box_refimprove',
            'title': 'Refimprove template box'
        },
        {
            'html': '<p>External link <a href="http://example.com">example</a> <span class="reference">[dead link]</span>.</p>',
            'expected': 'inline_dead_link',
            'title': 'Dead link detection'
        }
    ]

    # Mock the ZIM parser initialization since we don't have a real ZIM file
    with patch.object(ZIMParser, '_init_zim'):
        parser = ZIMParser('/fake/path.zim')

        for i, case in enumerate(test_cases):
            gaps = parser._detect_citation_gaps(case['html'], f'Test Article {i+1}', f'Test_Article_{i+1}')

            found_expected = any(gap.template_kind == case['expected'] for gap in gaps)
            status = "✅" if found_expected else "❌"
            print(f"{status} {case['title']}: {'DETECTED' if found_expected else 'NOT DETECTED'}")


def test_api_imports():
    """Test that API dependencies can be imported."""
    print("\n🧪 Testing API imports...")

    try:
        from fastapi import FastAPI
        print("✅ FastAPI import successful")
    except ImportError as e:
        print(f"❌ FastAPI import failed: {e}")

    try:
        import uvicorn
        print("✅ Uvicorn import successful")
    except ImportError as e:
        print(f"❌ Uvicorn import failed: {e}")

    try:
        from bs4 import BeautifulSoup
        print("✅ BeautifulSoup import successful")
    except ImportError as e:
        print(f"❌ BeautifulSoup import failed: {e}")


def test_zim_libraries():
    """Test ZIM parsing library imports."""
    print("\n🧪 Testing ZIM library imports...")

    libzim_available = False
    zimply_available = False

    try:
        import libzim
        libzim_available = True
        print("✅ libzim is available")
    except ImportError:
        print("⚠️ libzim not available (will use zimply fallback)")

    try:
        import zimply
        zimply_available = True
        print("✅ zimply is available")
    except ImportError:
        print("❌ zimply not available")

    if not libzim_available and not zimply_available:
        print("🚨 WARNING: No ZIM parsing libraries available!")
        return False

    return True


def main():
    """Run all tests."""
    print("🚀 Starting Wikipedia Citation Gap Pipeline Tests\n")

    # Test imports first
    test_api_imports()
    zim_libs_ok = test_zim_libraries()

    if not zim_libs_ok:
        print("\n❌ Cannot proceed without ZIM parsing libraries. Install with:")
        print("pip install libzim zimply")
        return False

    # Test core functionality
    test_template_detection()
    test_database_operations()

    print("\n🎉 All tests completed!")
    print("\n📋 Next steps:")
    print("1. Wait for ZIM file download to complete")
    print("2. Run: python main.py data/wikipedia_en_all_nopic_2026-03.zim")
    print("3. Start API: python api.py")
    print("4. Visit: http://localhost:8000")

    return True


if __name__ == "__main__":
    main()