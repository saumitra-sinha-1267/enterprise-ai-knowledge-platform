"""Document parser supporting PDF, DOCX, and TXT formats.
Extracts clean, normalized text while preserving page/section offsets.
"""

from dataclasses import dataclass
import io
import os
import re
from typing import List, Optional

import pypdf
import docx

from app.security.input_validator import sanitize_text


@dataclass
class ParsedSection:
    """A section of extracted text with page or segment number."""
    text: str
    page_number: Optional[int] = None


class DocumentParser:
    """Multi-format document extractor."""

    @classmethod
    def parse(cls, filename: str, content: bytes) -> List[ParsedSection]:
        """Extract text content from file bytes based on extension."""
        _, ext = os.path.splitext(filename.lower())
        
        if ext == ".txt":
            return cls._parse_txt(content)
        elif ext == ".pdf":
            return cls._parse_pdf(content)
        elif ext == ".docx":
            return cls._parse_docx(content)
        else:
            raise ValueError(f"Unsupported file format '{ext}' for text extraction.")

    @classmethod
    def _parse_txt(cls, content: bytes) -> List[ParsedSection]:
        """Decode TXT with UTF-8 or Latin-1 fallback."""
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")

        cleaned = sanitize_text(text)
        if not cleaned:
            return []
        return [ParsedSection(text=cleaned, page_number=1)]

    @classmethod
    def _parse_pdf(cls, content: bytes) -> List[ParsedSection]:
        """Extract text from PDF page by page using pypdf."""
        sections: List[ParsedSection] = []
        try:
            reader = pypdf.PdfReader(io.BytesIO(content))
            num_pages = len(reader.pages)
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                cleaned = sanitize_text(page_text)
                if cleaned:
                    sections.append(ParsedSection(text=cleaned, page_number=idx + 1))
        except Exception as e:
            raise ValueError(f"Failed to parse PDF document: {str(e)}")

        return sections

    @classmethod
    def _parse_docx(cls, content: bytes) -> List[ParsedSection]:
        """Extract text from DOCX paragraphs."""
        sections: List[ParsedSection] = []
        try:
            doc = docx.Document(io.BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            full_text = "\n\n".join(paragraphs)
            cleaned = sanitize_text(full_text)
            if cleaned:
                sections.append(ParsedSection(text=cleaned, page_number=1))
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX document: {str(e)}")

        return sections
