#!/usr/bin/env python3
"""
Quick script to check ZIM download progress and pipeline readiness.
"""

import os
from pathlib import Path

def format_bytes(bytes):
    """Convert bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} PB"

def main():
    zim_path = Path("data/wikipedia_en_all_nopic_2026-03.zim")
    expected_size = 48.3 * 1024 * 1024 * 1024  # ~48.3GB in bytes

    print("🔍 Wikipedia Citation Gap Pipeline Status\n")

    # Check if ZIM file exists and get size
    if zim_path.exists():
        current_size = zim_path.stat().st_size
        progress = (current_size / expected_size) * 100

        print(f"📥 ZIM File Download Progress:")
        print(f"   File: {zim_path}")
        print(f"   Current size: {format_bytes(current_size)}")
        print(f"   Expected size: {format_bytes(expected_size)}")
        print(f"   Progress: {progress:.1f}%")

        if progress >= 99.5:
            print("   Status: ✅ Download COMPLETE!")
            print("\n🚀 Ready to run pipeline:")
            print("   python3 main.py data/wikipedia_en_all_nopic_2026-03.zim")
        else:
            remaining = expected_size - current_size
            print(f"   Remaining: {format_bytes(remaining)}")
            print("   Status: ⏳ Download in progress...")
    else:
        print("❌ ZIM file not found!")
        print("   Expected location: data/wikipedia_en_all_nopic_2026-03.zim")

    # Check pipeline files
    print(f"\n📋 Pipeline Components:")
    components = [
        ("main.py", "Main pipeline script"),
        ("zim_parser.py", "ZIM parsing engine"),
        ("api.py", "Web API service"),
        ("test_pipeline.py", "Test suite"),
        ("requirements.txt", "Dependencies")
    ]

    for filename, description in components:
        status = "✅" if Path(filename).exists() else "❌"
        print(f"   {status} {filename} - {description}")

    # Check dependencies
    print(f"\n📦 Dependencies Check:")
    deps = [
        ("beautifulsoup4", "HTML parsing"),
        ("libzim", "ZIM file reading (primary)"),
        ("zimply", "ZIM file reading (fallback)"),
        ("fastapi", "Web API framework"),
        ("uvicorn", "ASGI server")
    ]

    for module_name, description in deps:
        try:
            __import__(module_name)
            status = "✅"
        except ImportError:
            status = "❌"
        print(f"   {status} {module_name} - {description}")

    print(f"\n📚 Next Steps:")
    if zim_path.exists() and zim_path.stat().st_size >= expected_size * 0.995:
        print("1. ✅ ZIM file ready")
        print("2. 🏃 Run: python3 main.py data/wikipedia_en_all_nopic_2026-03.zim")
        print("3. 🌐 Start API: python3 api.py")
        print("4. 🔍 Browse: http://localhost:8000")
    else:
        print("1. ⏳ Wait for ZIM download to complete")
        print("2. 🔍 Check progress: python3 check_download.py")
        print("3. 🏃 Once complete, run: python3 main.py data/wikipedia_en_all_nopic_2026-03.zim")

if __name__ == "__main__":
    main()