# Wikipedia Citation Gaps Pipeline

A Python pipeline that extracts Wikipedia articles needing citations, references, or source improvements from Wikipedia ZIM files. Perfect for identifying content improvement opportunities across Wikipedia.

## Features

- **ZIM File Parsing**: Processes offline Wikipedia ZIM files (~25GB English no-images version)
- **Template Detection**: Finds multiple citation gap patterns (citation needed, unreferenced, dead links, etc.)
- **Full-Text Search**: SQLite database with FTS5 indexing for fast searches
- **Web API**: FastAPI-based search service with simple web UI
- **Multiple Formats**: Export as SQLite database or CSV
- **Progress Tracking**: Real-time progress bars during extraction

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Download Wikipedia ZIM File

The pipeline automatically downloads the latest English Wikipedia ZIM file (~25GB):

```bash
# This happens automatically when you run the pipeline
# Or download manually from: https://download.kiwix.org/zim/wikipedia/
```

### 3. Extract Citation Gaps

```bash
# Run the full pipeline
python main.py data/wikipedia_en_all_nopic_2026-03.zim

# Or run the parser directly
python zim_parser.py data/wikipedia_en_all_nopic_2026-03.zim
```

### 4. Start the API Server

```bash
python api.py
```

Then visit http://localhost:8000 for the web interface.

## API Endpoints

### Web Interface
- `GET /` - Simple web search interface

### Search API
- `GET /api/search?q=<query>&limit=50` - Full-text search
- `GET /api/search?template_kind=inline_citation_needed` - Filter by template type
- `GET /api/stats` - Database statistics
- `GET /api/all?format=json` - Export all data as JSON
- `GET /api/all?format=csv` - Export all data as CSV

### Example API Usage

```bash
# Search for articles about "climate change" needing citations
curl "http://localhost:8000/api/search?q=climate%20change&limit=10"

# Find all articles with dead links
curl "http://localhost:8000/api/search?template_kind=inline_dead_link"

# Get database statistics
curl "http://localhost:8000/api/stats"
```

## Citation Gap Types Detected

| Template Kind | Description | Example |
|---------------|-------------|---------|
| `inline_citation_needed` | Inline "citation needed" tags | `[citation needed]` |
| `box_refimprove` | Articles needing more references | Refimprove template box |
| `box_unreferenced` | Completely unreferenced articles | Unreferenced template |
| `box_original_research` | Articles with unsourced claims | Original research template |
| `inline_dead_link` | Broken external links | `[dead link]` |
| `box_primary_sources` | Articles relying on primary sources | Primary sources template |
| `box_verifiability` | Verifiability issues | Verifiability template |
| `maintenance_template` | Other maintenance issues | Various CSS classes |

## Output Format

### Database Schema

```sql
CREATE TABLE citation_gaps (
    id INTEGER PRIMARY KEY,
    article_title TEXT,          -- "Climate change"
    official_url TEXT,           -- "https://en.wikipedia.org/wiki/Climate_change"
    template_kind TEXT,          -- "inline_citation_needed"
    template_label TEXT,         -- "Citation needed"
    opportunity TEXT,            -- "Add inline citation for this claim"
    snippet_text TEXT,           -- Surrounding context (~500 chars)
    section_title TEXT,          -- "Causes and effects"
    page_path TEXT,              -- "Climate_change"
    categories TEXT              -- "Environmental science|Climate"
);
```

### CSV Export

Same fields as database, with categories pipe-separated.

## Configuration

### Environment Variables

```bash
# Optional: Configure database path
export DB_PATH="custom/path/citation_gaps.db"

# Optional: API server settings
export API_HOST="0.0.0.0"
export API_PORT="8000"
```

### Command Line Options

```bash
python main.py --help
```

Options:
- `--db`: Output database path (default: `data/citation_gaps.db`)
- `--csv`: Output CSV path (default: `data/citation_gaps.csv`)
- `--skip-csv`: Skip CSV export

## Technical Details

### ZIM File Support

The pipeline supports multiple ZIM parsing libraries:

1. **libzim** (primary): Fast C++ library with Python bindings
2. **zimply** (fallback): Pure Python implementation

### Performance

- Streams processing to handle large ZIM files efficiently
- Batch database inserts for speed
- Progress bars for long-running operations
- FTS5 full-text search for fast queries

### Template Detection

Uses multiple detection methods:
- Regex patterns in article text
- CSS class matching for template boxes
- HTML element attribute scanning

## Development

### Project Structure

```
wiki-citation-gaps/
├── main.py              # Main pipeline script
├── zim_parser.py        # ZIM parsing and gap extraction
├── api.py              # FastAPI web service
├── requirements.txt     # Python dependencies
├── data/               # Data directory (gitignored)
│   ├── wikipedia_*.zim # ZIM files
│   ├── citation_gaps.db # SQLite database
│   └── citation_gaps.csv # CSV export
└── README.md           # This file
```

### Running Tests

```bash
# Install test dependencies
pip install pytest

# Run tests
pytest tests/
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Limitations

- Processing the full English Wikipedia (~25GB) takes several hours
- Memory usage scales with batch sizes (configurable)
- Some template patterns may be missed due to Wikipedia's template complexity
- Requires significant disk space for ZIM files and database

## Use Cases

- **Content Improvement**: Find Wikipedia articles needing better sourcing
- **Research**: Study citation patterns across Wikipedia
- **Tool Development**: Build specialized Wikipedia editing tools
- **Education**: Learn about Wikipedia's quality control systems

## License

MIT License - see LICENSE file for details.

## Support

- Issues: Create a GitHub issue
- Questions: Check existing issues or create a discussion

## Changelog

### v1.0.0
- Initial release
- ZIM file parsing with libzim/zimply
- Citation gap extraction for 8 template types
- SQLite database with FTS5 search
- FastAPI web service and UI
- CSV export functionality