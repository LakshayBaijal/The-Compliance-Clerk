# Project Report: The Compliance Clerk

## 1. Problem Statement

The project goal is to build an intelligent extraction pipeline for two document classes:
- eChallan (traffic violation documents)
- NA/Lease Permission documents

The system should extract structured fields reliably, minimize token/API usage, and support scalable processing of multi-page PDFs.

---

## 2. Objectives

1. Build a modular Python codebase with clear separation of concerns.
2. Use deterministic extraction first to reduce LLM dependency.
3. Maintain confidence scoring for routing decisions.
4. Add robust testing for each module.
5. Keep the system auditable and production-ready for future phases.

---

## 3. Technical Stack

- **Language:** Python 3.8+
- **Schema/Validation:** Pydantic 2.5.0
- **PDF Extraction:** PyMuPDF, pdfplumber
- **OCR Support:** pytesseract, easyocr
- **Data/Export:** pandas, openpyxl
- **Logging:** Python logging with JSON formatter
- **Testing:** standalone test scripts + pytest

---

## 4. Architecture Overview

The architecture follows a staged extraction strategy:

1. **Ingestion Layer**
   - Reads PDF pages
   - Extracts text and image metadata
   - Captures document metadata

2. **Classification Layer**
   - Identifies document type (eChallan / NA Permission / Unknown)
   - Produces confidence score
   - Routes pages to the correct extractor

3. **Deterministic Extraction Layer**
   - Regex-driven extraction by document type
   - Field-level confidence and overall confidence

4. **(Upcoming) LLM Fallback Layer**
   - Used only when deterministic confidence is insufficient
   - Designed for token-optimized processing

5. **(Upcoming) Validation + Audit + Export Layer**
   - Validation and normalization
   - SQLite audit logs
   - Excel output generation

---

## 5. Token Optimization Strategy (Design)

The project defines a 6-tier strategy to optimize API cost and response time:

- **Tier 1:** Deterministic extraction (0 tokens)
- **Tier 2:** OCR + lightweight checks
- **Tier 3:** Classification support (~150 tokens)
- **Tier 4:** Route-specific extraction (~100 tokens)
- **Tier 5:** Full fallback extraction (~1000 tokens)
- **Tier 6:** Summary generation (~500 tokens)

This approach ensures most routine documents are solved in Tier 1 without LLM calls.

---

## 6. Step-by-Step Development Process Followed

### Step 1: Project Initialization
- Created clean repository structure (`src/`, `tests/`, `data/`, `logs/`, `output/`)
- Added `requirements.txt`, `.gitignore`, `.env.example`
- Established Git workflow

### Step 2: Config and Logging
- Implemented `src/config.py` for:
  - Environment variable loading
  - Path handling and directory creation
  - Confidence and token thresholds
- Implemented `src/logger.py` for:
  - Console logging
  - JSON file logging with rotation

### Step 3: Pydantic Schemas
- Implemented `src/schemas.py`
- Added models:
  - `DocumentType`
  - `EchallanData`
  - `NAPermissionData`
  - `ExtractionResult`
  - `BatchResult`
- Validated serialization and optional fields through tests

### Step 4: PDF Ingestion Module
- Implemented `src/ingest.py` with:
  - Text extraction per page
  - Batch extraction over full document
  - Metadata extraction
  - Image metadata extraction
- Added fallback extraction behavior
- Later patched image handling using `page.get_images(full=True)` for compatibility and reliability

### Step 5: Document Classification
- Implemented `src/classify.py`
- Added keyword-pattern classifier:
  - 15 eChallan indicators
  - 16 NA-permission indicators
- Implemented confidence-based routing logic

### Step 6: Deterministic Extractors
- Implemented `src/extract_echallan.py`
  - 9 core fields extracted
- Implemented `src/extract_na.py`
  - 14 fields including restrictions/conditions
- Added field confidence and aggregate confidence outputs

---

## 7. Testing Strategy and Results

Testing is module-wise and deterministic:

- `tests/test_schemas.py` → **7/7 pass**
- `tests/test_ingest.py` → **8/8 pass**
- `tests/test_classify.py` → **10/10 pass**
- `tests/test_extractors.py` → **12/12 pass**

### Aggregate Result
- **Total: 37/37 tests passed**

This confirms stable behavior for all completed modules.

---

## 8. Key Engineering Decisions

1. **Deterministic-first extraction** to reduce API token usage.
2. **Typed schemas with Pydantic** for data integrity and clear contracts.
3. **Confidence-driven routing** to decide when fallback is required.
4. **Modular code structure** for easier maintenance and extension.
5. **Test-per-module approach** for fast feedback during iterative development.

---

## 9. Current Status

### Completed
- Core framework
- Config and logging
- Schemas
- PDF ingestion
- Classification
- Deterministic extraction
- Full passing tests for completed phases

### Pending
- LLM client integration (Groq)
- Validation/normalization module
- SQLite audit logging
- Excel export module
- Main orchestration CLI
- Final end-to-end run and polished docs

---

## 10. Conclusion

The project currently has a strong, test-validated foundation for document intelligence workflows. The deterministic pipeline already provides useful and reliable extraction with confidence scoring. Next phases will add LLM fallback, validation, auditability, and final end-to-end automation.
