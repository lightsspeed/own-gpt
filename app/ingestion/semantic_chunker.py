from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document

_QA_PATTERN = re.compile(r'(?:^|\n)(?:Q|Question)\s*[:\d.]+\s*(.+?)(?=\n(?:Q|Question)\s*[:\d.]|\Z)', re.IGNORECASE | re.DOTALL)
_HEADING_PATTERN = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)
_CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```')
_SECTION_BREAK = re.compile(r'\n{3,}')
_PDF_HEADING = re.compile(r'^([A-Z][A-Za-z\s]{2,40}|[A-Z][A-Za-z\s]{2,40}:)$', re.MULTILINE)
_MD_H2 = re.compile(r'^##\s(?!##).+$', re.MULTILINE)
_MD_H3 = re.compile(r'^###\s(?!##).+$', re.MULTILINE)


class SemanticChunker:
    """
    Splits documents into chunks using semantic boundaries instead of fixed character counts.

    Strategies:
      - Q&A interview PDFs: whole Q/A units stay together
      - Markdown: split on ##/### headings
      - Generic text: split on double newlines, then merge up to max_chars
      - Code blocks always stay intact

    Falls back to RecursiveCharacterTextSplitter semantics when no structure is detected.
    """

    def __init__(self, max_chars: int = 1500, overlap_chars: int = 100):
        self._max_chars = max_chars
        self._overlap_chars = overlap_chars

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents using the best strategy for each doc's content."""
        result: List[Document] = []
        for doc in documents:
            chunks = self._split_one(doc)
            result.extend(chunks)
        return result

    def _split_one(self, doc: Document) -> List[Document]:
        text = doc.page_content
        if not text.strip():
            return []

        ext = (doc.metadata or {}).get("file_type", "").lower()

        # Strategy selection
        if self._is_qa_format(text):
            return self._split_qa(text, doc.metadata)
        if ext in (".md", ".markdown"):
            return self._split_markdown(text, doc.metadata)
        if self._has_clear_headings(text):
            return self._split_by_headings(text, doc.metadata)

        # Fallback: section-based splitting (like the user's 300-char approach
        # but with smarter boundaries)
        return self._split_fallback(text, doc.metadata)

    # ── Strategy: Q&A interview format ──────────────────────────────────

    @staticmethod
    def _is_qa_format(text: str) -> bool:
        """Detect interview Q&A format like Q54, Question 12, etc."""
        qa_matches = _QA_PATTERN.findall(text)
        # Also check for "Q:" or "Question:" patterns
        simple_qa = len(re.findall(r'(?:^|\n)\s*(?:Q|Question)\s*[:\d.]', text, re.IGNORECASE)) >= 2
        return len(qa_matches) >= 2 or simple_qa

    def _split_qa(self, text: str, metadata: dict) -> List[Document]:
        """
        Split by question boundaries. Each question + its answer is ONE chunk.
        If a question is too long, it gets split further by sections.
        """
        # Find all Q positions
        q_positions = []
        for m in re.finditer(r'(?:^|\n)(?:Q|Question)\s*[:\d.]+', text, re.IGNORECASE):
            q_positions.append(m.start())

        if len(q_positions) <= 1:
            return [self._make_doc(text, metadata, 0)]

        chunks: List[Document] = []
        for i, start in enumerate(q_positions):
            end = q_positions[i + 1] if i + 1 < len(q_positions) else len(text)
            segment = text[start:end].strip()
            if segment:
                # If the segment is too long, split by sub-headings within it
                if len(segment) > self._max_chars:
                    sub_chunks = self._split_long_segment(segment, metadata, i)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(self._make_doc(segment, metadata, i))
        return chunks

    # ── Strategy: Markdown ───────────────────────────────────────────────

    def _split_markdown(self, text: str, metadata: dict) -> List[Document]:
        """Split markdown on ## (H2) headings. Sub-headings (###) stay
        under their parent. Small sections merge up to max_chars."""
        headings = list(_MD_H2.finditer(text))
        if not headings:
            # Try ### as fallback
            headings = list(_MD_H3.finditer(text))
        if not headings:
            return self._split_fallback(text, metadata)

        raw_sections: List[str] = []
        for i, m in enumerate(headings):
            start = m.start()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            raw_sections.append(text[start:end].strip())

        # Merge small sections
        merged: List[str] = []
        buffer = ""
        for section in raw_sections:
            if len(buffer) + len(section) < self._max_chars:
                buffer = (buffer + "\n\n" + section).strip() if buffer else section
            else:
                if buffer:
                    merged.append(buffer)
                buffer = section
        if buffer:
            merged.append(buffer)

        return [self._make_doc(s, metadata, i) for i, s in enumerate(merged)]

    # ── Strategy: Generic headings ──────────────────────────────────────

    def _has_clear_headings(self, text: str) -> bool:
        """Detect if text has PDF-style heading lines."""
        lines = text.split("\n")
        heading_lines = sum(1 for line in lines if _PDF_HEADING.match(line.strip()))
        return heading_lines >= 2

    def _split_by_headings(self, text: str, metadata: dict) -> List[Document]:
        """Split text on heading-like lines."""
        lines = text.split("\n")
        chunks: List[Document] = []
        current_lines: List[str] = []
        section_idx = 0

        for line in lines:
            stripped = line.strip()
            if _PDF_HEADING.match(stripped) and current_lines:
                segment = "\n".join(current_lines).strip()
                if segment:
                    if len(segment) > self._max_chars:
                        sub = self._split_long_segment(segment, metadata, section_idx)
                        chunks.extend(sub)
                    else:
                        chunks.append(self._make_doc(segment, metadata, section_idx))
                    section_idx += 1
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            segment = "\n".join(current_lines).strip()
            if segment:
                chunks.append(self._make_doc(segment, metadata, section_idx))

        return chunks or [self._make_doc(text, metadata, 0)]

    # ── Fallback ────────────────────────────────────────────────────────

    def _split_fallback(self, text: str, metadata: dict) -> List[Document]:
        """
        Split on double newlines, then merge small sections up to max_chars.
        Code blocks stay intact.
        """
        # Extract code blocks and replace with placeholders to avoid splitting them
        code_blocks = []
        def _save_code(m):
            code_blocks.append(m.group(0))
            return f"%%CODE_{len(code_blocks) - 1}%%"

        text_no_code = _CODE_BLOCK_PATTERN.sub(_save_code, text)
        sections = _SECTION_BREAK.split(text_no_code.strip())

        merged: List[str] = []
        buffer = ""
        for section in sections:
            # Restore code blocks
            for j, cb in enumerate(code_blocks):
                section = section.replace(f"%%CODE_{j}%%", cb)

            if not section.strip():
                continue
            if len(buffer) + len(section) < self._max_chars:
                buffer = (buffer + "\n\n" + section).strip() if buffer else section
            else:
                if buffer:
                    merged.append(buffer)
                buffer = section
        if buffer:
            merged.append(buffer)

        if not merged:
            merged = [text]

        return [self._make_doc(s, metadata, i) for i, s in enumerate(merged)]

    # ── Shared helpers ──────────────────────────────────────────────────

    def _split_long_segment(self, text: str, metadata: dict, base_idx: int) -> List[Document]:
        """Split a long segment by double newlines or sentences."""
        sub_sections = [s.strip() for s in _SECTION_BREAK.split(text) if s.strip()]
        if len(sub_sections) <= 1:
            sub_sections = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        chunks: List[Document] = []
        buffer = ""
        for ss in sub_sections:
            if len(buffer) + len(ss) < self._max_chars:
                buffer = (buffer + "\n\n" + ss).strip() if buffer else ss
            else:
                if buffer:
                    chunks.append(self._make_doc(buffer, metadata, base_idx + len(chunks)))
                buffer = ss
        if buffer:
            chunks.append(self._make_doc(buffer, metadata, base_idx + len(chunks)))
        return chunks

    @staticmethod
    def _make_doc(text: str, metadata: dict, seq: int) -> Document:
        meta = dict(metadata) if metadata else {}
        meta["chunk_sequence"] = seq
        return Document(page_content=text, metadata=meta)