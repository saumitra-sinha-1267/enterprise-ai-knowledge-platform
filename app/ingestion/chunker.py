"""Text chunking engine with configurable size, overlap, and metadata preservation.
"""

from dataclasses import dataclass
import re
from typing import List, Optional

from app.ingestion.parser import ParsedSection


@dataclass
class TextChunk:
    chunk_index: int
    text: str
    page_number: Optional[int]
    token_count: int


class TextChunker:
    """Chunks parsed text sections while preserving boundaries and page provenance."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size.")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_sections(self, sections: List[ParsedSection]) -> List[TextChunk]:
        """Split a list of parsed sections into overlapping chunks."""
        all_chunks: List[TextChunk] = []
        global_idx = 0

        for section in sections:
            section_chunks = self._split_text(section.text)
            for chunk_str in section_chunks:
                clean_chunk = chunk_str.strip()
                if not clean_chunk:
                    continue
                words = clean_chunk.split()
                all_chunks.append(
                    TextChunk(
                        chunk_index=global_idx,
                        text=clean_chunk,
                        page_number=section.page_number,
                        token_count=len(words),
                    )
                )
                global_idx += 1

        return all_chunks

    def _split_text(self, text: str) -> List[str]:
        """Split text into chunks of target size with overlap, respecting paragraph/sentence boundaries."""
        text = text.strip()
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        # Break text into atomic paragraph units
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            paragraphs = [text]

        chunks: List[str] = []
        current_chunk = ""

        for para in paragraphs:
            # If paragraph itself is larger than chunk_size, split by sentences
            if len(para) > self.chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    if not current_chunk:
                        current_chunk = sentence
                    elif len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                        current_chunk += " " + sentence
                    else:
                        chunks.append(current_chunk)
                        # Keep overlap from tail of current_chunk
                        overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else ""
                        current_chunk = (overlap_text + " " + sentence).strip()
            else:
                if not current_chunk:
                    current_chunk = para
                elif len(current_chunk) + len(para) + 2 <= self.chunk_size:
                    current_chunk += "\n\n" + para
                else:
                    chunks.append(current_chunk)
                    overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else ""
                    current_chunk = (overlap_text + "\n\n" + para).strip()

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
