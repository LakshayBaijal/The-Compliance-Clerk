"""
Test OCR directly on one PDF page to diagnose issues
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.ingest import PDFIngestor
from src.logger import get_logger

logger = get_logger(__name__)

pdf_path = "Files/Rampura Mota S.No.-256 Lease Deed No.-854.pdf"
ingestor = PDFIngestor(pdf_path)

print("=" * 80)
print("Testing OCR on single PDF page")
print("=" * 80)

# Test page 1
page_num = 1
print(f"\n>>> Testing Page {page_num}...")
print("-" * 80)

# Get direct text
text1 = ingestor.extract_text(page_num)
text2 = ingestor.extract_text_pdfplumber(page_num)
print(f"PyMuPDF text length: {len(text1)}")
print(f"pdfplumber text length: {len(text2)}")
print(f"PyMuPDF text sample: {text1[:200]}")
print(f"pdfplumber text sample: {text2[:200]}")

# Get images
images = ingestor.get_page_images(page_num)
print(f"\nImages on page: {len(images)}")
for img in images:
    print(f"  - Image {img['index']}: {img['width']}x{img['height']}, xref={img['xref']}")

# Try OCR
print(f"\nAttempting OCR...")
ocr_text = ingestor._extract_text_ocr(page_num)
print(f"OCR text length: {len(ocr_text)}")
if ocr_text:
    print(f"OCR text sample:\n{ocr_text[:500]}")
else:
    print("OCR returned empty text")

# Now test full extraction
print("\n" + "=" * 80)
print("Testing full extract_page_content()")
print("=" * 80)
content = ingestor.extract_page_content(page_num)
print(f"Has text: {content['has_text']}")
print(f"Text length: {content['text_length']}")
print(f"Has images: {content['has_images']}")
print(f"OCR used: {content['ocr_used']}")
print(f"Text sample:\n{content['text'][:500]}")
