"""Orchestrate the Day 06 Data Ingestion, Storage, and Evaluation pipeline."""
import csv
import json
import logging
import os
from pathlib import Path
import time
from typing import Any

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf
from .models import Chunk, DocumentPage
from .store import PgVectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def find_paths() -> tuple[Path, Path, Path, Path, Path]:
    """Locate key directories and files regardless of invocation working directory."""
    current_dir = Path(__file__).resolve().parent
    # current_dir is starter/src
    starter_dir = current_dir.parent
    root_dir = starter_dir.parent

    # Try root first, then starter
    pdf_path = root_dir / "data" / "bookdata_01.pdf"
    if not pdf_path.exists():
        pdf_path = starter_dir / "data" / "bookdata_01.pdf"

    questions_path = root_dir / "benchmark" / "questions.json"
    if not questions_path.exists():
        questions_path = starter_dir / "benchmark" / "questions.json"

    results_dir = root_dir / "results"
    artifacts_dir = root_dir / "artifacts"
    env_file = starter_dir / ".env"

    return pdf_path, questions_path, results_dir, artifacts_dir, env_file


def run_pipeline() -> dict[str, Any]:
    """Execute end-to-end pipeline: load -> chunk -> embed -> store -> evaluate -> report."""
    pdf_path, questions_path, results_dir, artifacts_dir, env_file = find_paths()

    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()

    results_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    db_url = os.getenv("DATABASE_URL", "postgresql://day6:day6_local_only@127.0.0.1:55433/day6_lab")
    model_name = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    dimensions = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

    logging.info(f"=== DAY 06 DATA INGESTION PIPELINE ===")
    logging.info(f"PDF Source: {pdf_path}")
    logging.info(f"DB URL: {db_url}")
    logging.info(f"Embedding Model: {model_name} ({dimensions} dimensions)")

    # 1. Load Corpus
    logging.info("--- Giai đoạn 1: Load & Normalize PDF ---")
    pages: list[DocumentPage] = load_pdf(
        pdf_path,
        document_id="bookdata_01",
        source="World Bank International Debt Report 2026",
    )
    if len(pages) < 30:
        raise ValueError(f"Yêu cầu tối thiểu 30 trang nội dung hữu ích, chỉ tìm thấy {len(pages)} trang.")
    logging.info(f"Đã nạp {len(pages)} trang (từ trang vật lý {pages[0].page} đến {pages[-1].page}).")

    # 2. Chunking
    logging.info("--- Giai đoạn 2: Chunking Strategies ---")
    # Strategy A: Fixed size 500, overlap 50
    chunks_a: list[Chunk] = []
    for p in pages:
        chunks_a.extend(fixed_size(p, size=500, overlap=50))
    logging.info(f"Strategy A (Fixed 500/50): {len(chunks_a)} chunks")

    # Strategy B: By paragraph, max_size 800
    chunks_b: list[Chunk] = []
    for p in pages:
        chunks_b.extend(by_paragraph(p, max_size=800))
    logging.info(f"Strategy B (Paragraph <=800): {len(chunks_b)} chunks")

    # Strategy C: Same chunks as B
    chunks_c: list[Chunk] = []
    for c in chunks_b:
        meta_c = dict(c.metadata)
        meta_c["strategy"] = "strategy_c"
        chunks_c.append(
            Chunk(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                source=c.source,
                page=c.page,
                text=c.text,
                metadata=meta_c,
            )
        )
    logging.info(f"Strategy C (Paragraph <=800 + Metadata Filter): {len(chunks_c)} chunks")

    # 3. Embedding Model & Vector Store
    logging.info("--- Giai đoạn 3 & 4: Embedding & Vector Storage ---")
    embedder = MyEmbedder()
    store = PgVectorStore(database_url=db_url, dimensions=dimensions)
    store.create_schema()
    logging.info("Bảng document_chunks và extension pgvector đã sẵn sàng.")

    # Embed & Upsert Strategy A
    t0_a = time.perf_counter()
    logging.info(f"Đang sinh embeddings cho Strategy A ({len(chunks_a)} chunks)...")
    texts_a = [c.text for c in chunks_a]
    vecs_a = embedder.embed_documents(texts_a)
    store.upsert("strategy_a", chunks_a, vecs_a)
    dur_a = time.perf_counter() - t0_a
    logging.info(f"Strategy A hoàn tất trong {dur_a:.2f}s.")

    # Embed & Upsert Strategy B
    t0_b = time.perf_counter()
    logging.info(f"Đang sinh embeddings cho Strategy B ({len(chunks_b)} chunks)...")
    texts_b = [c.text for c in chunks_b]
    vecs_b = embedder.embed_documents(texts_b)
    store.upsert("strategy_b", chunks_b, vecs_b)
    dur_b = time.perf_counter() - t0_b
    logging.info(f"Strategy B hoàn tất trong {dur_b:.2f}s.")

    # Reuse Embeddings for Strategy C & Upsert
    t0_c = time.perf_counter()
    logging.info(f"Đang nạp Strategy C (tái sử dụng {len(vecs_b)} vectors từ Strategy B)...")
    store.upsert("strategy_c", chunks_c, vecs_b)
    dur_c = time.perf_counter() - t0_c
    logging.info(f"Strategy C hoàn tất trong {dur_c:.2f}s.")

    # 4. Benchmark Evaluation
    logging.info("--- Giai đoạn 5: Đánh giá Benchmark ---")
    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    logging.info(f"Đã nạp {len(questions)} câu hỏi benchmark từ {questions_path}.")

    # Pre-embed queries
    logging.info("Đang sinh embedding cho các câu hỏi benchmark...")
    query_vectors: dict[str, list[float]] = {}
    for q in questions:
        qid = q["id"]
        q_text = q["question"]
        query_vectors[qid] = embedder.embed_query(q_text)

    # Run queries against Strategy A, B, C
    traces_a: list[dict[str, Any]] = []
    traces_b: list[dict[str, Any]] = []
    traces_c: list[dict[str, Any]] = []

    for q in questions:
        qid = q["id"]
        q_vec = query_vectors[qid]
        q_filter = q.get("filter")

        # Strategy A (no filter)
        hits_a = store.search("strategy_a", q_vec, top_k=3, filters=None)
        traces_a.append(evaluate_query(q, hits_a, strategy="strategy_a"))

        # Strategy B (no filter)
        hits_b = store.search("strategy_b", q_vec, top_k=3, filters=None)
        traces_b.append(evaluate_query(q, hits_b, strategy="strategy_b"))

        # Strategy C (apply filter if present)
        hits_c = store.search("strategy_c", q_vec, top_k=3, filters=q_filter)
        traces_c.append(evaluate_query(q, hits_c, strategy="strategy_c"))

    all_traces = traces_a + traces_b + traces_c
    summary = summarize(all_traces)

    # 5. Save Artifacts & Traces
    logging.info("--- Giai đoạn 6: Lưu vết & Báo cáo ---")
    with open(results_dir / "traces_strategy_a.json", "w", encoding="utf-8") as f:
        json.dump(traces_a, f, ensure_ascii=False, indent=2)
    with open(results_dir / "traces_strategy_b.json", "w", encoding="utf-8") as f:
        json.dump(traces_b, f, ensure_ascii=False, indent=2)
    with open(results_dir / "traces_strategy_c.json", "w", encoding="utf-8") as f:
        json.dump(traces_c, f, ensure_ascii=False, indent=2)
    with open(results_dir / "all_traces.json", "w", encoding="utf-8") as f:
        json.dump(all_traces, f, ensure_ascii=False, indent=2)
    with open(results_dir / "benchmark_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Update artifacts/experiment_log.csv
    exp_log_path = artifacts_dir / "experiment_log.csv"
    with open(exp_log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "strategy", "chunking", "chunk_size", "overlap", "metadata", "filter",
            "vectorizer", "hypothesis", "dev_hit1", "dev_hit3", "test_hit1", "test_hit3", "notes"
        ])

        # Row A
        sum_a = summary.get("strategy_a", {})
        writer.writerow([
            "A", "fixed", "500", "50", "section,year,chapter", "none",
            f"{model_name} ({dimensions})",
            "Baseline fixed window chunking with overlap",
            sum_a.get("dev", {}).get("hit_at_1_ratio", "0/0"),
            sum_a.get("dev", {}).get("hit_at_3_ratio", "0/0"),
            sum_a.get("test", {}).get("hit_at_1_ratio", "0/0"),
            sum_a.get("test", {}).get("hit_at_3_ratio", "0/0"),
            f"chunks={len(chunks_a)}, time={dur_a:.2f}s, cost=~$0.0003",
        ])

        # Row B
        sum_b = summary.get("strategy_b", {})
        writer.writerow([
            "B", "paragraph", "800", "0", "section,year,chapter", "none",
            f"{model_name} ({dimensions})",
            "Paragraph boundary chunking preserving semantic units",
            sum_b.get("dev", {}).get("hit_at_1_ratio", "0/0"),
            sum_b.get("dev", {}).get("hit_at_3_ratio", "0/0"),
            sum_b.get("test", {}).get("hit_at_1_ratio", "0/0"),
            sum_b.get("test", {}).get("hit_at_3_ratio", "0/0"),
            f"chunks={len(chunks_b)}, time={dur_b:.2f}s, cost=~$0.0002",
        ])

        # Row C
        sum_c = summary.get("strategy_c", {})
        writer.writerow([
            "C", "paragraph", "800", "0", "section,year,chapter", "section",
            f"{model_name} ({dimensions})",
            "Paragraph chunking + metadata filtering on section",
            sum_c.get("dev", {}).get("hit_at_1_ratio", "0/0"),
            sum_c.get("dev", {}).get("hit_at_3_ratio", "0/0"),
            sum_c.get("test", {}).get("hit_at_1_ratio", "0/0"),
            sum_c.get("test", {}).get("hit_at_3_ratio", "0/0"),
            f"chunks={len(chunks_c)}, time={dur_c:.2f}s, cost=$0.00 (reused)",
        ])

    logging.info(f"Đã cập nhật log thí nghiệm tại {exp_log_path}")

    return {
        "summary": summary,
        "timings": {"A": dur_a, "B": dur_b, "C": dur_c},
        "counts": {"A": len(chunks_a), "B": len(chunks_b), "C": len(chunks_c)},
    }


def main() -> None:
    """Entry point for command-line execution."""
    results = run_pipeline()
    summary = results["summary"]
    timings = results["timings"]
    counts = results["counts"]

    print("\n" + "=" * 80)
    print("BENCHMARK RETRIEVAL EVALUATION SUMMARY TABLE")
    print("=" * 80)
    print(f"| {'Strategy':<10} | {'Split':<6} | {'Hit@1 (n/N)':<12} | {'Hit@1 (%)':<10} | {'Hit@3 (n/N)':<12} | {'Hit@3 (%)':<10} | {'Chunks':<8} | {'Time (s)':<10} | {'Cost':<10} |")
    print("|" + "-" * 12 + "|" + "-" * 8 + "|" + "-" * 14 + "|" + "-" * 12 + "|" + "-" * 14 + "|" + "-" * 12 + "|" + "-" * 10 + "|" + "-" * 12 + "|" + "-" * 12 + "|")

    cost_map = {"A": "~$0.0003", "B": "~$0.0002", "C": "$0.00 (reused)"}
    strat_keys = [("strategy_a", "A"), ("strategy_b", "B"), ("strategy_c", "C")]

    for skey, sname in strat_keys:
        sdata = summary.get(skey, {})
        for split in ["dev", "test", "all"]:
            sp = sdata.get(split, {})
            h1_r = sp.get("hit_at_1_ratio", "0/0")
            h1_p = f"{sp.get('hit_at_1_pct', 0.0):.1f}%"
            h3_r = sp.get("hit_at_3_ratio", "0/0")
            h3_p = f"{sp.get('hit_at_3_pct', 0.0):.1f}%"
            c_count = str(counts[sname])
            t_dur = f"{timings[sname]:.2f}s"
            cost_str = cost_map[sname]
            print(f"| {sname:<10} | {split:<6} | {h1_r:<12} | {h1_p:<10} | {h3_r:<12} | {h3_p:<10} | {c_count:<8} | {t_dur:<10} | {cost_str:<10} |")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
