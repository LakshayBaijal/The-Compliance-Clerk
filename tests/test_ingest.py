"""
Unit tests for PDF ingestion module.
Tests with actual sample PDFs from Files/ directory.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingest import PDFIngestor, ingest_pdf


def test_pdf_ingestor_init():
    """Test PDFIngestor initialization with sample PDF."""
    pdf_files = list(Path("Files").glob("*.pdf"))
    
    if not pdf_files:
        print("[SKIP] No sample PDFs found in Files/")
        return
    
    # Use first available PDF
    pdf_path = str(pdf_files[0])
    ingestor = PDFIngestor(pdf_path)
    assert ingestor.pdf_path.exists()
    print(f"[PASS] PDFIngestor initialized with: {pdf_files[0].name}")


def test_get_page_count():
    """Test getting page count from sample PDF."""
    pdf_files = list(Path("Files").glob("*.pdf"))
    
    if not pdf_files:
        print("[SKIP] No sample PDFs found")
        return
    
    pdf_path = str(pdf_files[0])
    ingestor = PDFIngestor(pdf_path)
    count = ingestor.get_page_count()
    
    assert count > 0
    print(f"[PASS] Page count: {count} pages")


def test_extract_text():
    """Test text extraction from first page."""
    pdf_files = list(Path("Files").glob("*.pdf"))
    
    if not pdf_files:
        print("[SKIP] No sample PDFs found")
        return
    
    pdf_path = str(pdf_files[0])
    ingestor = PDFIngestor(pdf_path)
    text = ingestor.extract_text(0)
    
    assert text is not None
    print(f"[PASS] Text extracted: {len(text)} characters")


def test_extract_page_content():
    """Test comprehensive page content extraction."""
    pdf_files = list(Path("Files").glob("*.pdf"))
    
    if not pdf_files:
        print("[SKIP] No sample PDFs found")
        return
    
    pdf_path = str(pdf_files[0])
    ingestor = PDFIngestor(pdf_path)
    content = ingestor.extract_page_content(0)
    
    assert "page_num" in content
    assert "text" in content
    assert "has_text" in content
    assert "images" in content
    assert "has_images" in content
    print(f"[PASS] Content extracted - text:{len(content['text'])} chars, images:{content['image_count']}")


def test_extract_all_pages():
    """Test extracting all pages."""
    pdf_files = list(Path("Files").glob("*.pdf"))
    
    if not pdf_files:
        print("[SKIP] No sample PDFs found")
        return
    
    pdf_path = str(pdf_files[0])
    ingestor = PDFIngestor(pdf_path)
    pages = ingestor.extract_all_pages()
    
    assert len(pages) > 0
    assert pages[0]["page_num"] == 0
    print(f"[PASS] All pages extracted: {len(pages)} pages")


def test_get_pdf_metadata():
    """Test PDF metadata extraction."""
    pdf_files = list(Path("Files").glob("*.pdf"))
    
    if not pdf_files:
        print("[SKIP] No sample PDFs found")
        return
    
    pdf_path = str(pdf_files[0])
    metadata = PDFIngestor.get_pdf_metadata(pdf_path)
    
    assert "page_count" in metadata
    assert metadata["page_count"] > 0
    print(f"[PASS] Metadata extracted - pages:{metadata['page_count']}, encrypted:{metadata['is_encrypted']}")


def test_ingest_pdf_function():
    """Test the convenient ingest_pdf function."""
    pdf_files = list(Path("Files").glob("*.pdf"))
    
    if not pdf_files:
        print("[SKIP] No sample PDFs found")
        return
    
    pdf_path = str(pdf_files[0])
    result = ingest_pdf(pdf_path)
    
    assert "file_name" in result
    assert "metadata" in result
    assert "pages" in result
    assert len(result["pages"]) > 0
    print(f"[PASS] ingest_pdf function works - {len(result['pages'])} pages processed")


def test_multiple_pdfs():
    """Test processing multiple PDFs."""
    pdf_files = list(Path("Files").glob("*.pdf"))
    
    if len(pdf_files) < 2:
        print("[SKIP] Need at least 2 PDFs to test multiple processing")
        return
    
    results = []
    for pdf_path in pdf_files[:3]:  # Test first 3 PDFs
        try:
            result = ingest_pdf(str(pdf_path))
            results.append(result)
        except Exception as e:
            print(f"[WARN] Failed to process {pdf_path.name}: {e}")
    
    assert len(results) > 0
    print(f"[PASS] Multiple PDFs processed: {len(results)} files")


if __name__ == "__main__":
    print("Running PDF ingestion tests...\n")
    test_pdf_ingestor_init()
    test_get_page_count()
    test_extract_text()
    test_extract_page_content()
    test_extract_all_pages()
    test_get_pdf_metadata()
    test_ingest_pdf_function()
    test_multiple_pdfs()
    print("\n[SUCCESS] All PDF ingestion tests completed!")
