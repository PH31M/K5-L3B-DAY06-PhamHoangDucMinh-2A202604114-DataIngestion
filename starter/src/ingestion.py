"""Read and normalize source data. TODO: implement functions."""
from pathlib import Path
from .models import DocumentPage

import re
import unicodedata
from pathlib import Path
from .models import DocumentPage
import logging
import pypdf


def get_section_metadata(phys_page: int) -> str:
    """Xác định section trong Chương 2 theo số trang vậy lý"""

    if 75 <= phys_page <=84:
        return "transmission_shocks"
    elif 85 <= phys_page <= 95:
        return "fiscal_pressures"
    elif 96 <= phys_page <= 102:
        return "food_import"
    else:
        return "notes_references"


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """TODO: extract each physical page; keep its page number and source.

    Detect and record pages with no text. OCR, when needed, is a separate step.
    """
    if not path.exists():
        raise FileNotFoundError(f"Corpus File not found: {path}")

    reader = pypdf.PdfReader(str(path))
    pages: list[DocumentPage] = []

    # 32 trang thuộc chương 2 : trang vật lý từ  75 đến 106 (0-indexed: 74 đến 105)
    start_idx = 74
    end_idx = 106

    for idx in range(start_idx, end_idx):
        phys_page = idx + 1

        # 1. Trích xuất text gốc từ PDF
        raw_text = reader.pages[idx].extract_text() or ""

        # 2. Chuẩn hóa text
        clean_text = normalize_text(raw_text)

        # 3. Bat loi khi không có text
        is_empty = False
        if len(clean_text) < 50:
            is_empty = True
            logging.warning(
                f"[Page Warning] Trang vật lý {phys_page} có ít hơn 50 ký tự hữu ích ({len(clean_text)} chars)."
            )

        # 4. gan metadata ngu canh
        metadata = {
            "section": get_section_metadata(phys_page),
            "year": 2026,
            "chapter": 2,
            "char_count": len(clean_text),
            "is_empty": is_empty,
        }

        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=phys_page,
                text=clean_text,
                metadata=metadata,
            )
        )
    logging.info(f"Đã trích xuất thành công {len(pages)} trang từ {path}")
    return pages


def normalize_text(text: str) -> str:
    """TODO: normalize Unicode and whitespace without discarding useful structure."""

    if not text:
        return ""

    text = text.replace("\x00", "")  # Remove null bytes
    text = unicodedata.normalize("NFKC",text) # Normalize Unicode characters to a standard form
    text = text.replace("\xa0"," ")
    
    text = text.replace("\r\n","\n").replace("\r","\n") # Normalize line endings to Unix style
    
    text = re.sub(r'(\b\w+)-\s*\n\s*(\w+\b)', r'\1\2', text) # Remove hyphenation at line breaks

    lines = [line.strip() for line in text.split("\n")] # Remove leading and trailing whitespace from each line
    text = "\n".join(lines)

    text = re.sub(r'\n{3,}', '\n\n', text) # Collapse multiple consecutive newlines into two newlines

    text = re.sub(r'[^\S\n]+', ' ', text) # Replace multiple consecutive whitespace characters with a single space, preserving newlines

    return text.strip()
