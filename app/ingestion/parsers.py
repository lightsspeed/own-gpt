from __future__ import annotations

import csv
import io
import logging
import re
import traceback
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy import helper — avoids DLL conflicts at module-import time
def _doc(**kwargs):
    from langchain_core.documents import Document
    return Document(**kwargs)

# ---------------------------------------------------------------------------
# Parser registry
# ---------------------------------------------------------------------------

_PARSER_REGISTRY: Dict[str, str] = {}  # extension → parser_name


def register_parser(ext: str, name: str) -> None:
    _PARSER_REGISTRY[ext] = name


def list_available() -> List[str]:
    """Return descriptions of available parsers."""
    return [f"{ext} → {name}" for ext, name in sorted(_PARSER_REGISTRY.items())]


# ---------------------------------------------------------------------------
# .pdf  — PyMuPDF (fitz) or fallback to pypdf via PyPDFLoader
# ---------------------------------------------------------------------------

def parse_pdf(path: Path) -> List[Document]:
    """Extract text from a PDF using PyMuPDF (fitz) with a fallback to pypdf."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return _parse_pdf_pypdf(path)

    docs: List[Document] = []
    try:
        with fitz.open(path) as doc:
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text().strip()
                if text:
                    docs.append(_doc(
                        page_content=text,
                        metadata={
                            "source": path.name,
                            "file_type": ".pdf",
                            "page": page_num,
                            "ingestion_path": str(path),
                        },
                    ))
    except Exception as exc:
        logger.warning("PyMuPDF failed for %s, falling back to pypdf: %s", path.name, exc)
        return _parse_pdf_pypdf(path)
    return docs


def _parse_pdf_pypdf(path: Path) -> List[Document]:
    """Fallback PDF parser using pypdf directly."""
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("No PDF parser available (install pypdf or PyMuPDF)")
        return []

    docs: List[Document] = []
    try:
        reader = PdfReader(str(path))
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text().strip()
            if text:
                docs.append(_doc(
                    page_content=text,
                    metadata={
                        "source": path.name,
                        "file_type": ".pdf",
                        "page": page_num,
                        "ingestion_path": str(path),
                    },
                ))
    except Exception as exc:
        logger.error("pypdf failed for %s: %s", path.name, exc)
        return []
    return docs


register_parser(".pdf", "PyMuPDF (fitz) / pypdf fallback")


# ---------------------------------------------------------------------------
# .docx  — python-docx
# ---------------------------------------------------------------------------

def parse_docx(path: Path) -> List[Document]:
    """Extract text from a .docx file using python-docx."""
    try:
        from docx import Document as DocxDocument
    except ImportError:
        logger.error("python-docx not installed — cannot parse .docx files")
        return []

    try:
        doc = DocxDocument(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            logger.info("No text content found in %s", path.name)
            return []

        text = "\n".join(paragraphs)
        return [_doc(
            page_content=text,
            metadata={
                "source": path.name,
                "file_type": ".docx",
                "ingestion_path": str(path),
            },
        )]
    except Exception as exc:
        logger.error("python-docx failed for %s: %s", path.name, exc)
        return []


register_parser(".docx", "python-docx")


# ---------------------------------------------------------------------------
# .pptx  — python-pptx
# ---------------------------------------------------------------------------

def parse_pptx(path: Path) -> List[Document]:
    """Extract text from a .pptx file using python-pptx."""
    try:
        from pptx import Presentation
    except ImportError:
        logger.error("python-pptx not installed — cannot parse .pptx files")
        return []

    try:
        prs = Presentation(str(path))
        parts: List[str] = []
        for slide_num, slide in enumerate(prs.slides, start=1):
            slide_texts: List[str] = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        t = paragraph.text.strip()
                        if t:
                            slide_texts.append(t)
            if slide_texts:
                parts.append(f"--- Slide {slide_num} ---\n" + "\n".join(slide_texts))

        if not parts:
            logger.info("No text content found in %s", path.name)
            return []

        text = "\n\n".join(parts)
        return [_doc(
            page_content=text,
            metadata={
                "source": path.name,
                "file_type": ".pptx",
                "ingestion_path": str(path),
            },
        )]
    except Exception as exc:
        logger.error("python-pptx failed for %s: %s", path.name, exc)
        return []


register_parser(".pptx", "python-pptx")


# ---------------------------------------------------------------------------
# .csv  — stdlib csv
# ---------------------------------------------------------------------------

def parse_csv(path: Path) -> List[Document]:
    """Parse a CSV file. Each row becomes a sentence, with header context retained."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            sample = f.read(8192)
            dialect = csv.Sniffer().sniff(sample)
            f.seek(0)
            reader = csv.reader(f, dialect)
            headers = next(reader, None)
            rows = list(reader)
    except Exception as exc:
        logger.error("CSV parse failed for %s: %s", path.name, exc)
        return []

    if not headers or not rows:
        logger.info("CSV %s has no data", path.name)
        return []

    docs: List[Document] = []
    for row_num, row in enumerate(rows, start=2):  # start=2 because header is row 1
        if not any(cell.strip() for cell in row):
            continue
        pairs = [f"{h}: {v}" for h, v in zip(headers, row) if v.strip()]
        line = " | ".join(pairs)
        docs.append(_doc(
            page_content=line,
            metadata={
                "source": path.name,
                "file_type": ".csv",
                "row": row_num,
                "ingestion_path": str(path),
            },
        ))

    return docs


register_parser(".csv", "stdlib csv")


# ---------------------------------------------------------------------------
# .xlsx  — openpyxl
# ---------------------------------------------------------------------------

def parse_xlsx(path: Path) -> List[Document]:
    """Parse an Excel workbook. One Document per row, prefixed by sheet + headers."""
    try:
        import openpyxl
    except ImportError:
        logger.error("openpyxl not installed — cannot parse .xlsx files")
        return []

    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        logger.error("openpyxl failed to open %s: %s", path.name, exc)
        return []

    docs: List[Document] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        headers: List[Optional[str]] = []
        for row_num, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if row_num == 1:
                headers = [str(c) if c is not None else None for c in row]
                continue
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue
            pairs = []
            for h, v in zip(headers, row):
                if v is not None and h:
                    pairs.append(f"{h}: {v}")
            if pairs:
                line = " | ".join(pairs)
                docs.append(_doc(
                    page_content=line,
                    metadata={
                        "source": path.name,
                        "file_type": ".xlsx",
                        "sheet": sheet_name,
                        "row": row_num,
                        "ingestion_path": str(path),
                    },
                ))
    wb.close()
    return docs


register_parser(".xlsx", "openpyxl")


# ---------------------------------------------------------------------------
# .html / .htm  — beautifulsoup4
# ---------------------------------------------------------------------------

def parse_html(path: Path) -> List[Document]:
    """
    Parse an HTML file. Strips tags, preserves heading structure, extracts title.
    Uses a two-pass approach:
      1. Extract <title> as document-level context.
      2. Split by headings (h1–h3), each section becomes a Document.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return _parse_html_fallback(path)

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
    except Exception as exc:
        logger.error("BeautifulSoup parse failed for %s: %s", path.name, exc)
        return []

    title_tag = soup.find("title")
    doc_title = title_tag.get_text(strip=True) if title_tag else path.stem

    docs: List[Document] = []
    body = soup.find("body") or soup
    current_heading = ""
    current_parts: List[str] = []

    def _flush():
        nonlocal current_parts
        text = _clean_whitespace("\n".join(current_parts))
        if text:
            docs.append(_doc(
                page_content=text,
                metadata={
                    "source": path.name,
                    "file_type": ".html",
                    "section": current_heading or "body",
                    "title": doc_title,
                    "ingestion_path": str(path),
                },
            ))
        current_parts = []

    for element in body.descendants:
        if element.name in ("h1", "h2", "h3"):
            _flush()
            current_heading = element.get_text(strip=True)
        elif element.name in ("p", "li", "td", "th", "blockquote", "pre", "code"):
            t = element.get_text(strip=True)
            if t:
                current_parts.append(t)
    _flush()

    if not docs:
        text = _clean_whitespace(body.get_text(separator="\n"))
        if text:
            docs.append(_doc(
                page_content=text,
                metadata={
                    "source": path.name,
                    "file_type": ".html",
                    "section": "body",
                    "title": doc_title,
                    "ingestion_path": str(path),
                },
            ))

    return docs


def _parse_html_fallback(path: Path) -> List[Document]:
    """Stripped HTML via regex when BeautifulSoup is unavailable."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.error("Cannot read %s: %s", path.name, exc)
        return []

    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    return [_doc(
        page_content=text,
        metadata={
            "source": path.name,
            "file_type": ".html",
            "section": "body",
            "ingestion_path": str(path),
        },
    )]


register_parser(".html", "BeautifulSoup / regex fallback")
register_parser(".htm", "BeautifulSoup / regex fallback")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _clean_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def parse(path: Path) -> List[Document]:
    """
    Dispatch to the correct parser based on file extension.

    Returns an empty list if the extension is unsupported or the parser fails.
    """
    ext = path.suffix.lower()
    parser_map = {
        ".pdf": parse_pdf,
        ".docx": parse_docx,
        ".pptx": parse_pptx,
        ".csv": parse_csv,
        ".xlsx": parse_xlsx,
        ".html": parse_html,
        ".htm": parse_html,
    }
    parser = parser_map.get(ext)
    if parser is None:
        logger.warning("Unsupported extension: %s (%s)", ext, path.name)
        return []

    try:
        return parser(path)
    except Exception as exc:
        logger.error("Parser crashed for %s: %s\n%s", path.name, exc, traceback.format_exc())
        return []
