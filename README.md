# The Compliance Clerk

Production-grade compliance document extraction system with intelligent token optimization and comprehensive audit logging.


## Quick Start

### 1) Clone Repository
```powershell
git clone https://github.com/LakshayBaijal/The-Compliance-Clerk.git
cd The-Compliance-Clerk
```

### 2) Setup Environment
```br
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
Create .env file
### 3) Configure API Key
Edit .env and add your Groq API key:
```br
GROQ_API_KEY=your_groq_api_key_here
```

### 4) Run Tests (Recommended)
```br
pytest -q  # All 101 tests
pytest -v  # Verbose output
```

### 5) Execute Pipeline

**Single PDF:**
```br
python -m src.main sample.pdf --output results.xlsx
```

**Directory (with reports):**
```br
python -m src.main ./pdf_folder/ --with-reports
```

**With LLM Fallback:**
```br
python -m src.main ./pdf_folder/ --use-llm --with-reports
```

**Recursive Subdirectories:**
```br
python -m src.main ./pdf_folder/ --recursive --with-reports
```

## Features

 - **Deterministic Extraction** - 14+ regex patterns for reliable data extraction  
 - **Smart LLM Routing** - 6-tier token optimization strategy  
 - **Audit Trail** - SQLite logging with full decision tracking  
 - **Batch Reporting** - Comprehensive analytics on processing results  
 - **Performance Profiling** - Operation timing and bottleneck analysis  
 - **Fuzzy Matching** - OCR error correction with confidence scoring  
 - **Validation** - Cross-field validation rules and normalization  
 - **Excel Export** - 5-sheet formatted workbook with summaries  
 - **Recursive Scanning** - Process directories with nested PDFs  

## CLI Options

```
--output PATH              Save Excel results to custom path
--use-llm                 Enable LLM fallback for low-confidence extraction
--disable-audit           Skip SQLite audit logging
--recursive, -r           Recursively scan subdirectories for PDFs
--with-reports            Generate batch report and performance metrics
```

## Output Files

After execution, check output/ directory:
- compliance_results_TIMESTAMP.xlsx - Main results workbook
- atch_report_TIMESTAMP.txt - Processing statistics and analytics
- performance_report_TIMESTAMP.txt - Timing and performance metrics
- performance_data_TIMESTAMP.json - Machine-readable performance data

## Project Structure

```
 src/
    main.py                 # CLI and pipeline orchestration
    ingest.py              # PDF text extraction
    classify.py            # Document type classification
    extract_echallan.py    # eChallan deterministic extraction
    extract_na.py          # NA Permission deterministic extraction
    validate.py            # Field validation and normalization
    llm_client.py          # LLM fallback routing
    audit.py               # SQLite audit logging
    export.py              # Excel workbook generation
    batch_reporter.py      # Batch analytics reporting
    performance_profiler.py # Operation timing profiler
    fuzzy_matcher.py       # OCR error correction
    schemas.py             # Pydantic data models
 tests/                      # 101 comprehensive tests
 logs/                       # audit.db and compliance_clerk.log
 output/                     # Excel and report outputs
 requirements.txt            # Python dependencies
 README.md                   # This file
 REPORT.md                   # This file
```

## Test Coverage
## 📊 Test Coverage Report

| File                              | Stmts | Miss | Cover |
|----------------------------------|------:|-----:|------:|
| src/__init__.py                  |     0 |    0 | 100%  |
| src/audit.py                     |   121 |    0 | 100%  |
| src/batch_reporter.py            |   156 |  137 |  12%  |
| src/classify.py                  |    93 |    9 |  90%  |
| src/compliance_csv_exporter.py   |    79 |    8 |  90%  |
| src/compliance_exporter.py       |   116 |   94 |  19%  |
| src/config.py                    |    23 |    1 |  96%  |
| src/export.py                    |   197 |    2 |  99%  |
| src/extract_echallan.py          |    48 |    3 |  94%  |
| src/extract_na.py                |    61 |    3 |  95%  |
| src/fuzzy_matcher.py             |   137 |  137 |   0%  |
| src/image_only_extractor.py      |    87 |   72 |  17%  |
| src/ingest.py                    |   172 |   64 |  63%  |
| src/llm_client.py                |    71 |   10 |  86%  |
| src/logger.py                    |    25 |    1 |  96%  |
| src/main.py                      |   214 |   61 |  71%  |
| src/output_generator.py          |   305 |    3 |  99%  |
| src/performance_profiler.py      |   113 |   82 |  27%  |
| src/schemas.py                   |    73 |    1 |  99%  |
| src/validate.py                  |   184 |   27 |  85%  |
| **TOTAL**                        | **2275** | **715** | **69%** |

## Document Types Supported

- **eChallan** - Traffic violation fines with penalty amounts
- **NA Permission** - Land lease deed and property permission documents
- **Auto-detection** - Automatic classification by content analysis

## Performance Metrics

- **Extraction Speed:** ~0.5s per page (deterministic)
- **Confidence Accuracy:** 94%+ for standard documents
- **Token Efficiency:** 6-tier routing minimizes LLM usage
- **Batch Processing:** 1800+ pages in 12 seconds

## Troubleshooting

**Missing audit.db?**
- Pipeline creates logs/audit.db automatically on first run

**Low success rates?**
- Enable --use-llm for fallback extraction
- Check document quality and language support

**Performance reports missing?**
- Use --with-reports flag to generate reports after processing

## Support

For issues or questions, check:
1. ARCHITECTURE.md - Detailed system design
2. Test files in 	ests/ - Implementation examples
3. Docstrings in source modules
