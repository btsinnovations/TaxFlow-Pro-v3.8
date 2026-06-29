#!/usr/bin/env python3
"""
OCR Module for Financial ETL Pipeline
Uses PaddleOCR for offline, high-accuracy text extraction from PDFs and images.
Falls back to direct text extraction for digital PDFs.
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import tempfile

# PDF handling
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

# PDF to image conversion (for scanned PDFs)
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

# Image preprocessing
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# PaddleOCR
try:
    from paddleocr import PaddleOCR, PPStructure
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False

from .logger import Logger
from .config import OCR_CONFIG

logger = Logger("ocr")

# ----------------------------------------------------------------------
# Configuration (can be overridden in config.py)
# ----------------------------------------------------------------------
DEFAULT_CONFIG = {
    "use_angle_cls": True,       # Detect text orientation
    "lang": "en",                # Language (en, ch, etc.)
    "show_log": False,           # Reduce console noise
    "use_gpu": False,            # Set to True if GPU available
    "enable_mkldnn": True,       # CPU acceleration for Intel
    "cpu_threads": 4,            # Adjust based on your CPU
    "det_db_thresh": 0.3,        # Detection confidence threshold
    "det_db_box_thresh": 0.5,    # Box detection threshold
    "rec_score_thresh": 0.5,     # Recognition confidence threshold
    "table_structure": True,     # Enable table recognition (PP-Structure)
}

# Merge with user config if available
def _get_config():
    if 'OCR_CONFIG' in globals() or 'OCR_CONFIG' in dir():
        cfg = OCR_CONFIG.copy() if hasattr(OCR_CONFIG, 'copy') else DEFAULT_CONFIG.copy()
    else:
        cfg = DEFAULT_CONFIG.copy()
    return cfg

# Global PaddleOCR instance (lazy initialization)
_ocr_instance = None
_ppstructure_instance = None

def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        cfg = _get_config()
        logger.info("Initializing PaddleOCR (this may take a moment on first run)...")
        _ocr_instance = PaddleOCR(
            use_angle_cls=cfg.get("use_angle_cls", True),
            lang=cfg.get("lang", "en"),
            show_log=cfg.get("show_log", False),
            use_gpu=cfg.get("use_gpu", False),
            enable_mkldnn=cfg.get("enable_mkldnn", True),
            cpu_threads=cfg.get("cpu_threads", 4),
            det_db_thresh=cfg.get("det_db_thresh", 0.3),
            det_db_box_thresh=cfg.get("det_db_box_thresh", 0.5),
            rec_score_thresh=cfg.get("rec_score_thresh", 0.5),
        )
    return _ocr_instance

def _get_ppstructure():
    global _ppstructure_instance
    if _ppstructure_instance is None and DEFAULT_CONFIG.get("table_structure", True):
        try:
            _ppstructure_instance = PPStructure(
                show_log=False,
                use_gpu=DEFAULT_CONFIG.get("use_gpu", False),
                enable_mkldnn=DEFAULT_CONFIG.get("enable_mkldnn", True),
            )
        except Exception as e:
            logger.warning(f"PP-Structure (table recognition) not available: {e}")
            _ppstructure_instance = None
    return _ppstructure_instance

# ----------------------------------------------------------------------
# Image Preprocessing (improves OCR accuracy)
# ----------------------------------------------------------------------
def preprocess_image(image):
    """
    Apply preprocessing to improve OCR accuracy.
    Steps: grayscale, denoise, threshold, deskew, contrast adjustment.
    """
    if not CV2_AVAILABLE:
        return image
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=30)
    
    # Adaptive thresholding (better for uneven lighting)
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Optional: deskew (if needed)
    # Optional: contrast adjustment
    return binary

# ----------------------------------------------------------------------
# PDF Text Extraction (digital PDFs - fast path)
# ----------------------------------------------------------------------
def extract_text_from_pdf_direct(pdf_path: Path) -> Optional[str]:
    """Extract text directly from digital PDFs (no OCR)."""
    if not PDFPLUMBER_AVAILABLE:
        logger.warning("pdfplumber not installed. Install with: pip install pdfplumber")
        return None
    
    try:
        all_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)
        return "\n".join(all_text) if all_text else None
    except Exception as e:
        logger.error(f"Direct PDF extraction failed: {e}")
        return None

# ----------------------------------------------------------------------
# PaddleOCR Text Extraction (for scanned documents)
# ----------------------------------------------------------------------
def extract_text_with_paddleocr(image_path: Path) -> List[Dict[str, Any]]:
    """Run PaddleOCR on a single image file."""
    if not PADDLEOCR_AVAILABLE:
        logger.error("PaddleOCR not installed. Install with: pip install paddleocr")
        return []
    
    ocr = _get_ocr()
    try:
        result = ocr.ocr(str(image_path), cls=True)
        parsed = []
        if result and result[0]:
            for line in result[0]:
                bbox, (text, confidence) = line
                parsed.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": bbox,
                })
        return parsed
    except Exception as e:
        logger.error(f"PaddleOCR failed on {image_path}: {e}")
        return []

def extract_text_from_pdf_scanned(pdf_path: Path, dpi: int = 200) -> str:
    """
    Convert scanned PDF to images, run PaddleOCR on each page, return combined text.
    """
    if not PDF2IMAGE_AVAILABLE:
        logger.error("pdf2image not installed. Install with: pip install pdf2image")
        return ""
    if not PADDLEOCR_AVAILABLE:
        logger.error("PaddleOCR not installed.")
        return ""
    
    ocr = _get_ocr()
    all_text = []
    
    try:
        # Convert PDF pages to images
        images = convert_from_path(str(pdf_path), dpi=dpi)
        logger.info(f"Converted {len(images)} pages from {pdf_path}")
        
        for page_num, img in enumerate(images, 1):
            logger.debug(f"Processing page {page_num}...")
            
            # Preprocess image for better OCR
            if CV2_AVAILABLE:
                img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                processed = preprocess_image(img_cv)
                # Convert back to PIL for PaddleOCR
                from PIL import Image
                img = Image.fromarray(processed)
            
            # Run OCR
            result = ocr.ocr(np.array(img), cls=True)
            if result and result[0]:
                page_text = []
                for line in result[0]:
                    text = line[1][0]
                    confidence = line[1][1]
                    if confidence > 0.5:  # Threshold
                        page_text.append(text)
                all_text.append(" ".join(page_text))
            else:
                logger.warning(f"No text found on page {page_num}")
        
        return "\n".join(all_text)
    
    except Exception as e:
        logger.error(f"Scanned PDF processing failed: {e}")
        return ""

# ----------------------------------------------------------------------
# Table Recognition (for bank statements with tables)
# ----------------------------------------------------------------------
def extract_tables_from_image(image_path: Path) -> List[Dict[str, Any]]:
    """
    Extract tables from an image using PP-Structure.
    Returns structured table data (rows, columns, cells).
    """
    ppstructure = _get_ppstructure()
    if ppstructure is None:
        logger.warning("PP-Structure not available, skipping table extraction")
        return []
    
    try:
        result = ppstructure.predict(str(image_path))
        tables = []
        for item in result:
            if item.get('type') == 'table':
                tables.append({
                    "html": item.get('res', {}).get('html', ''),
                    "cells": item.get('res', {}).get('cells', []),
                    "bbox": item.get('bbox', []),
                })
        return tables
    except Exception as e:
        logger.error(f"Table extraction failed: {e}")
        return []

# ----------------------------------------------------------------------
# Main Entry Point – Called from pdf_parser.py
# ----------------------------------------------------------------------
def extract_text_from_pdf(pdf_path: Path, prefer_digital: bool = True) -> str:
    """
    Extract all text from a PDF file.
    
    Strategy:
    1. If prefer_digital=True, try direct text extraction first (fast).
    2. If that returns little or no text, fall back to PaddleOCR (scanned).
    
    Returns:
        Combined text from all pages.
    """
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return ""
    
    logger.info(f"Extracting text from {pdf_path}")
    
    # Try direct extraction first (digital PDF)
    if prefer_digital:
        direct_text = extract_text_from_pdf_direct(pdf_path)
        if direct_text and len(direct_text.strip()) > 100:  # Reasonable amount of text
            logger.info("Successfully extracted text directly (digital PDF)")
            return direct_text
        else:
            logger.info("Direct extraction returned little text, falling back to OCR")
    
    # Fallback: treat as scanned PDF
    logger.info("Using PaddleOCR for scanned PDF")
    return extract_text_from_pdf_scanned(pdf_path)

def extract_text_from_image(image_path: Path) -> str:
    """Extract text from an image file using PaddleOCR."""
    results = extract_text_with_paddleocr(image_path)
    return " ".join([r["text"] for r in results if r["confidence"] > 0.5])

# ----------------------------------------------------------------------
# Test / Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Quick test (replace with your own PDF path)
    import sys
    if len(sys.argv) > 1:
        test_path = Path(sys.argv[1])
        text = extract_text_from_pdf(test_path)
        print(f"Extracted {len(text)} characters")
        print("\n--- First 500 characters ---")
        print(text[:500])
    else:
        print("Usage: python -m phase3_pipeline.ocr path/to/document.pdf")
