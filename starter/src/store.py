"""Store and search vectors using PostgreSQL + pgvector."""
import json
from typing import Any
import psycopg
from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        """Retain connection settings; validate model dimensions."""
        if dimensions <= 0:
            raise ValueError(f"Số chiều dimensions phải lớn hơn 0, nhận được: {dimensions}")
        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        """Create extension vector, table with vector column and metadata indexes."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # 1. Bật extension pgvector
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                # 2. Tạo bảng lưu trữ chunk với vector đúng số chiều dimensions
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id VARCHAR(128) PRIMARY KEY,
                        strategy VARCHAR(32) NOT NULL,
                        document_id VARCHAR(64) NOT NULL,
                        source TEXT NOT NULL,
                        page INT NOT NULL,
                        section VARCHAR(128),
                        text TEXT NOT NULL,
                        metadata JSONB,
                        embedding vector({self.dimensions})
                    );
                    CREATE INDEX IF NOT EXISTS idx_chunks_strategy ON document_chunks(strategy);
                    CREATE INDEX IF NOT EXISTS idx_chunks_section ON document_chunks(section);
                """)
                conn.commit()

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Validate lengths/dimensions, ensure idempotency, and batch insert chunks."""
        if len(chunks) != len(vectors):
            raise ValueError(f"Số lượng chunk ({len(chunks)}) không khớp với số vector ({len(vectors)})")
        if not chunks:
            return

        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # Tính Idempotent: Xóa các chunk cũ của cùng strategy và document_id trước khi nạp lại
                doc_ids = list({c.document_id for c in chunks})
                for doc_id in doc_ids:
                    cur.execute(
                        "DELETE FROM document_chunks WHERE strategy = %s AND document_id = %s;",
                        (strategy, doc_id),
                    )

                # Chuẩn bị dữ liệu dạng tuple để chèn batch tối ưu tốc độ
                records = [
                    (
                        c.chunk_id,
                        strategy,
                        c.document_id,
                        c.source,
                        c.page,
                        c.metadata.get("section"),
                        c.text,
                        json.dumps(c.metadata),
                        str(v),  # Format vector dạng chuỗi cho pgvector
                    )
                    for c, v in zip(chunks, vectors)
                ]

                insert_sql = """
                    INSERT INTO document_chunks (id, strategy, document_id, source, page, section, text, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (id) DO UPDATE SET
                        strategy = EXCLUDED.strategy,
                        document_id = EXCLUDED.document_id,
                        source = EXCLUDED.source,
                        page = EXCLUDED.page,
                        section = EXCLUDED.section,
                        text = EXCLUDED.text,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding;
                """
                cur.executemany(insert_sql, records)
                conn.commit()

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Filter permitted metadata in SQL, rank by cosine distance, return top-k."""
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"Kích thước query vector ({len(query_vector)}) không khớp với dimensions ({self.dimensions})"
            )

        q_vec_str = str(query_vector)
        params: list[Any] = [q_vec_str, strategy]
        filter_clause = ""

        # Xử lý Metadata Filtering bằng SQL parameterization an toàn (chống SQL Injection)
        if filters:
            if "section" in filters and filters["section"]:
                filter_clause += " AND section = %s"
                params.append(filters["section"])
            for k, v in filters.items():
                if k != "section" and v is not None:
                    filter_clause += " AND metadata->>%s = %s"
                    params.extend([k, str(v)])

        sql = f"""
            SELECT id, text, page, source, section, metadata, (embedding <=> %s::vector) AS distance
            FROM document_chunks
            WHERE strategy = %s {filter_clause}
            ORDER BY distance ASC
            LIMIT %s;
        """
        params.append(top_k)

        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                results = []
                for row in cur.fetchall():
                    chunk_id, text, page, source, section, meta, distance = row
                    # Score cosine similarity: 1 - distance
                    score = 1.0 - float(distance)
                    results.append({
                        "chunk_id": chunk_id,
                        "text": text,
                        "score": round(score, 6),
                        "page": page,
                        "source": source,
                        "section": section,
                        "metadata": meta if isinstance(meta, dict) else json.loads(meta or "{}"),
                    })
                return results
