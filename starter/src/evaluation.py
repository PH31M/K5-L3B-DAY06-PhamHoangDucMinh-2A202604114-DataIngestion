"""Evaluate retrieved evidence and preserve per-query traces."""
import re
from typing import Any


def _normalize_str(s: str) -> str:
    """Chuẩn hóa khoảng trắng và đưa về chữ thường để so khớp chuỗi bằng chứng đáng tin cậy."""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def evaluate_query(
    question: dict[str, Any],
    hits: list[dict[str, Any]],
    strategy: str = "",
) -> dict[str, Any]:
    """Check source/page and enough gold evidence; keep hit@1 and hit@3 trace."""
    gold_quote = _normalize_str(question.get("evidence_quote", ""))
    raw_gold_page = question.get("gold_page")
    gold_pages = raw_gold_page if isinstance(raw_gold_page, list) else [raw_gold_page]

    hit_details: list[dict[str, Any]] = []
    hit_at_1 = False
    hit_at_3 = False

    # Đánh giá tối đa top-3 kết quả trả về
    for rank, h in enumerate(hits[:3]):
        h_page = h.get("page")
        h_text_norm = _normalize_str(h.get("text", ""))

        # Điều kiện Hit: Đúng số trang gold VÀ chứa đoạn trích evidence
        page_match = h_page in gold_pages
        evidence_match = bool(gold_quote and gold_quote in h_text_norm)
        is_hit = page_match and evidence_match

        if rank == 0 and is_hit:
            hit_at_1 = True
        if is_hit:
            hit_at_3 = True

        hit_details.append({
            "rank": rank + 1,
            "chunk_id": h.get("chunk_id"),
            "page": h_page,
            "score": h.get("score"),
            "section": h.get("section"),
            "is_hit": is_hit,
            "text_snippet": (h.get("text", "")[:200] + "...") if len(h.get("text", "")) > 200 else h.get("text", ""),
        })

    # Lưu trace đầy đủ theo từng câu hỏi
    return {
        "question_id": question.get("id"),
        "question": question.get("question"),
        "split": question.get("split", "dev"),
        "type": question.get("type", "direct"),
        "filter": question.get("filter"),
        "gold_page": raw_gold_page,
        "evidence_quote": question.get("evidence_quote"),
        "strategy": strategy or question.get("strategy", ""),
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hits": hit_details,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    if not traces:
        return {}

    # Lấy danh sách các strategy có trong traces
    strategies = sorted(list({t.get("strategy", "default") for t in traces}))
    summary: dict[str, Any] = {}

    for strat in strategies:
        strat_traces = [t for t in traces if t.get("strategy", "default") == strat]
        strat_summary: dict[str, Any] = {}

        for split in ["dev", "test", "all"]:
            if split == "all":
                subset = strat_traces
            else:
                subset = [t for t in strat_traces if t.get("split") == split]

            total = len(subset)
            h1 = sum(1 for t in subset if t.get("hit_at_1", False))
            h3 = sum(1 for t in subset if t.get("hit_at_3", False))

            strat_summary[split] = {
                "total": total,
                "hit_at_1_count": h1,
                "hit_at_1_ratio": f"{h1}/{total}" if total else "0/0",
                "hit_at_1_pct": round(h1 / total * 100, 2) if total else 0.0,
                "hit_at_3_count": h3,
                "hit_at_3_ratio": f"{h3}/{total}" if total else "0/0",
                "hit_at_3_pct": round(h3 / total * 100, 2) if total else 0.0,
            }

        summary[strat] = strat_summary

    return summary
