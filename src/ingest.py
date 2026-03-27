"""
PDF ingestion module for The Compliance Clerk.
Handles PDF loading, text extraction, and image detection.
"""

import fitz  # PyMuPDF
import pdfplumber
from pathlib import Path
from typing import Optional, Dict, List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger

logger = get_logger(__name__)


class PDFIngestor:
    """Handles PDF ingestion and content extraction."""
    
    def __init__(self, pdf_path: str):
        """
        Initialize PDF ingestor.
        
        Args:
            pdf_path: Path to PDF file
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        logger.info(f"Initialized PDF ingestor for: {self.pdf_path.name}")
    
    def get_page_count(self) -> int:
        """Get total number of pages in PDF."""
        try:
            with fitz.open(str(self.pdf_path)) as doc:
                return doc.page_count
        except Exception as e:
            logger.error(f"Failed to get page count: {e}")
            raise
    
    def extract_text(self, page_num: int) -> str:
        """
        Extract text from a page using PyMuPDF.
        
        Args:
            page_num: Page number (0-indexed)
        
        Returns:
            Extracted text
        """
        try:
            with fitz.open(str(self.pdf_path)) as doc:
                if page_num < 0 or page_num >= doc.page_count:
                    raise ValueError(f"Page {page_num} out of range")
                
                page = doc[page_num]
                text = page.get_text()
                
                return text
        except Exception as e:
            logger.error(f"Failed to extract text from page {page_num}: {e}")
            raise
    
    def extract_text_pdfplumber(self, page_num: int) -> str:
        """
        Extract text from a page using pdfplumber (alternative method).
        
        Args:
            page_num: Page number (0-indexed)
        
        Returns:
            Extracted text
        """
        try:
            with pdfplumber.open(str(self.pdf_path)) as pdf:
                if page_num < 0 or page_num >= len(pdf.pages):
                    raise ValueError(f"Page {page_num} out of range")
                
                page = pdf.pages[page_num]
                text = page.extract_text()
                
                return text if text else ""
        except Exception as e:
            logger.error(f"Failed to extract text with pdfplumber: {e}")
            raise
    
    def _extract_text_ocr(self, page_num: int) -> str:
        """
        Extract text from a page using OCR (Tesseract via pytesseract).
        Fallback when text extraction fails.
        
        Args:
            page_num: Page number (0-indexed)
        
        Returns:
            Extracted text from OCR
        """
        try:
            import pytesseract
            from PIL import Image
            import tempfile
            
            # Convert PDF page to image
            with fitz.open(str(self.pdf_path)) as doc:
                if page_num < 0 or page_num >= doc.page_count:
                    return ""
                
                page = doc[page_num]
                # Render page to image at 150 DPI for better OCR
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    pix.save(tmp.name)
                    
                    # Run OCR
                    image = Image.open(tmp.name)
                    text = pytesseract.image_to_string(image)
                    
                    # Clean up
                    Path(tmp.name).unlink()
                    
                    return text if text else ""
        except ImportError:
            logger.debug("pytesseract not available for OCR")
            return ""
        except Exception as e:
            logger.debug(f"OCR extraction failed: {e}")
            return ""
    
    def get_page_images(self, page_num: int) -> List[Dict]:
        """
        Get list of images on a page.
        
        Args:
            page_num: Page number (0-indexed)
        
        Returns:
            List of image info dictionaries
        """
        images = []
        try:
            with fitz.open(str(self.pdf_path)) as doc:
                if page_num < 0 or page_num >= doc.page_count:
                    raise ValueError(f"Page {page_num} out of range")
                
                page = doc[page_num]
                image_list = page.get_images(full=True)

                for idx, img_info in enumerate(image_list):
                    try:
                        xref = img_info[0]
                        width = img_info[2] if len(img_info) > 2 else None
                        height = img_info[3] if len(img_info) > 3 else None
                        bits_per_component = img_info[4] if len(img_info) > 4 else None
                        colorspace_name = img_info[5] if len(img_info) > 5 else None

                        images.append({
                            "index": idx,
                            "xref": xref,
                            "width": width,
                            "height": height,
                            "bits_per_component": bits_per_component,
                            "colorspace": colorspace_name
                        })
                    except Exception as e:
                        logger.warning(f"Failed to parse image {idx} info: {e}")
                
                logger.debug(f"Found {len(images)} images on page {page_num}")
        except Exception as e:
            logger.error(f"Failed to get images from page {page_num}: {e}")
        
        return images
    
    def extract_page_content(self, page_num: int) -> Dict:
        """
        Extract complete content from a page.
        
        Args:
            page_num: Page number (0-indexed)
        
        Returns:
            Dictionary with page content
        """
        try:
            # Extract text using both methods and use the longer result
            text_method1 = self.extract_text(page_num)
            text_method2 = self.extract_text_pdfplumber(page_num)
            text = text_method1 if len(text_method1) >= len(text_method2) else text_method2
            
            # Check if text is corrupted (contains CID codes which indicate font encoding issues)
            cid_count = text.count("(cid:")
            corruption_ratio = cid_count / len(text) if text else 0
            
            # If more than 2% CID codes, try OCR
            if corruption_ratio > 0.02:
                logger.debug(f"Text corruption detected on page {page_num} ({corruption_ratio:.1%} CID codes), attempting OCR")
                try:
                    ocr_text = self._extract_text_ocr(page_num)
                    if ocr_text and len(ocr_text.strip()) > 50:
                        text = ocr_text
                        logger.debug(f"OCR successful on page {page_num}: {len(text)} chars")
                except Exception as e:
                    logger.debug(f"OCR failed on page {page_num}: {e}")
            
            # Get images
            images = self.get_page_images(page_num)
            
            return {
                "page_num": page_num,
                "text": text,
                "has_text": bool(text.strip()),
                "text_length": len(text),
                "images": images,
                "has_images": len(images) > 0,
                "image_count": len(images)
            }
            
        except Exception as e:
            logger.error(f"Failed to extract page content: {e}")
            raise
    
    def extract_all_pages(self) -> List[Dict]:
        """
        Extract content from all pages.
        
        Returns:
            List of page content dictionaries
        """
        try:
            total_pages = self.get_page_count()
            pages_content = []
            
            logger.info(f"Extracting from {total_pages} pages")
            
            for page_num in range(total_pages):
                try:
                    content = self.extract_page_content(page_num)
                    pages_content.append(content)
                except Exception as e:
                    logger.error(f"Failed to extract page {page_num}: {e}")
                    # Continue with next page
                    pages_content.append({
                        "page_num": page_num,
                        "text": "",
                        "has_text": False,
                        "images": [],
                        "has_images": False,
                        "error": str(e)
                    })
            
            logger.info(f"Extracted {len(pages_content)} pages")
            return pages_content
            
        except Exception as e:
            logger.error(f"Failed to extract all pages: {e}")
            raise
    
    @staticmethod
    def get_pdf_metadata(pdf_path: str) -> Dict:
        """
        Extract PDF metadata.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Dictionary with metadata
        """
        try:
            with fitz.open(str(pdf_path)) as doc:
                metadata = doc.metadata or {}
                return {
                    "title": metadata.get("title", ""),
                    "author": metadata.get("author", ""),
                    "creator": metadata.get("creator", ""),
                    "page_count": doc.page_count,
                    "is_encrypted": doc.is_encrypted
                }
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return {}


def ingest_pdf(pdf_path: str) -> Dict:
    """
    Convenient function to ingest a PDF.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Dictionary with all extracted content
    """
    ingestor = PDFIngestor(pdf_path)
    
    return {
        "file_name": ingestor.pdf_path.name,
        "file_path": str(ingestor.pdf_path),
        "metadata": PDFIngestor.get_pdf_metadata(str(ingestor.pdf_path)),
        "pages": ingestor.extract_all_pages()
    }
