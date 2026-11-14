"""Implement fixed-size and structure-aware chunking."""
from .models import Chunk, DocumentPage
import re
from .models import Chunk

def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """TODO: split text into overlapping windows and retain page metadata."""
    if not page.text or not page.text.strip():
        return []

    # Chuẩn hóa khoảng trắng để cửa sổ ký tự không bị đứt đoạn bởi ngắt dòng cứng của pdf
    text = re.sub(r'\s+', ' ', page.text).strip()
    chunks: list[Chunk] = []
    text_len = len(text)
    step = max(1, size - overlap)
    start = 0
    c_idx = 0

    while start < text_len:
        end = min(start + size, text_len)
        chunk_text = text[start:end].strip()

        if chunk_text:
            meta = dict(page.metadata)
            meta.update({
                "chunk_index": c_idx,
                "strategy": "fixed_size",
                "char_count": len(chunk_text),
                "start_char": start,
                "end_char": end,
            })
            chunks.append(
                Chunk(
                    chunk_id=f"{page.document_id}_p{page.page}_c{c_idx:03d}",
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=chunk_text,
                    metadata=meta,
                )
            )
            c_idx += 1

        # Đảm bảo dừng khi đã bao phủ đến hết ký tự cuối cùng
        if end >= text_len:
            break
        start += step
    
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """TODO: group paragraphs, split oversized paragraphs and retain metadata."""
    if not page.text or not page.text.strip():
        return []

    text = page.text.strip()

    # 1. Tách theo ranh giới đoạn văn / dòng
    raw_blocks = [b.strip() for b in re.split(r'\n+', text) if b.strip()]

    # 2. Xử lý các đoạn dài vượt trần max_size bằng cách bẻ nhỏ theo câu
    units: list[str] = []
    for block in raw_blocks:
        if len(block) <= max_size:
            units.append(block)
        else:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+',
            block) if s.strip()]
            for s in sentences:
                if len(s) <= max_size:
                    units.append(s)
                else:
                    # Nếu câu đơn lẻ vẫn vượt max_size, trượt cửa sổ
                    step = max_size - 50
                    for i in range(0, len(s), step):
                        sub = s[i:i + max_size].strip()
                        if sub:
                            units.append(sub)

    # 3. Gộp các units liên tiếp nếu tổng độ dài <= max_size
    chunks: list[Chunk] = []
    current_text = ""
    c_idx = 0

    for u in units:
        if not current_text:
            current_text = u
        elif len(current_text) + 1 + len(u) <= max_size:
            current_text += " " + u
        else:
            # Lưu chunk nếu đạt độ dài tối thiểu (>= 30 ký tự)
            if len(current_text) >= 30:
                meta = dict(page.metadata)
                meta.update({
                    "chunk_index": c_idx,
                    "strategy": "by_paragraph",
                    "char_count": len(current_text),
                })
                chunks.append(
                    Chunk(
                        chunk_id=f"{page.document_id}_p{page.page}_b{c_idx:03d}",
                        document_id=page.document_id,
                        source=page.source,
                        page=page.page,
                        text=current_text,
                        metadata=meta,
                    )
                )
                c_idx += 1
            current_text = u

    # 4. Lưu đoạn tích lũy cuối cùng nếu còn
    if current_text and len(current_text) >= 30:
        meta = dict(page.metadata)
        meta.update({
            "chunk_index": c_idx,
            "strategy": "by_paragraph",
            "char_count": len(current_text),
        })
        chunks.append(
            Chunk(
                chunk_id=f"{page.document_id}_p{page.page}_b{c_idx:03d}",
                document_id=page.document_id,
                source=page.source,
                page=page.page,
                text=current_text,
                metadata=meta,
            )
        )

    return chunks