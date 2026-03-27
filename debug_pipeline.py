#!/usr/bin/env python
"""Debug script to diagnose pipeline issues"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.ingest import ingest_pdf
from src.classify import DocumentClassifier
from src.extract_echallan import extract_echallan
from src.extract_na import extract_na_permission

# Pick a sample PDF
pdf_path = Path("Files") / "251-p2 FINAL ORDER.pdf"

if not pdf_path.exists():
    print(f"❌ File not found: {pdf_path}")
    sys.exit(1)

print(f"[PDF] Processing: {pdf_path}")
print("=" * 80)

# 1. Ingest
ingested = ingest_pdf(str(pdf_path))
print(f"\n[OK] Ingestion: {len(ingested.get('pages', []))} pages extracted")

# 2. Check first page
if not ingested.get("pages"):
    print("[ERROR] No pages extracted!")
    sys.exit(1)

page = ingested["pages"][0]
page_num = page.get("page_num")
text = page.get("text", "")

print(f"\n[PAGE] Page {page_num}: {len(text)} characters")
print(f"First 500 characters:\n{text[:500]}")
print("\n" + "=" * 80)

# 3. Classify
classifier = DocumentClassifier()
classification = classifier.classify_text(text, page_num)

print(f"\n[CLASSIFY] Classification:")
print(f"  - Document Type: {classification.get('document_type')}")
print(f"  - Confidence: {classification.get('confidence'):.2f}")
print(f"  - Method: {classification.get('classification_method')}")

# 4. Extract based on type
doc_type = classification.get('document_type')
print(f"\n[EXTRACT] Extracting as: {doc_type}")

if doc_type.name == "ECHALLAN":
    result = extract_echallan(text)
    print(f"  - Overall Confidence: {result.get('overall_confidence'):.2f}")
    print(f"  - Fields Extracted: {result.get('extracted_fields')}/{result.get('total_fields')}")
    print(f"  - Data: {result['data'].model_dump(exclude_none=True)}")
    
elif doc_type.name == "NA_PERMISSION":
    result = extract_na_permission(text)
    print(f"  - Overall Confidence: {result.get('overall_confidence'):.2f}")
    print(f"  - Fields Extracted: {result.get('extracted_fields')}/{result.get('total_fields')}")
    print(f"  - Data: {result['data'].model_dump(exclude_none=True)}")
    
else:
    print(f"  [ERROR] Unknown document type - cannot extract")

print("\n" + "=" * 80)
