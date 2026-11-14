"""Choose a real embedding provider (API or local) and implement this contract."""
import os
from typing import Protocol
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Implement real embedder via OpenRouter / OpenAI SDK; no mock fallback."""

    def __init__(self, model_name: str | None = None, dimensions: int | None = None) -> None:
        # Đọc cấu hình từ tham số truyền vào hoặc lấy từ .env
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
        self.dimensions = dimensions or int(os.getenv("EMBEDDING_DIMENSION", 1536))

        # Kiểm tra API key
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "Không tìm thấy OPENROUTER_API_KEY hoặc OPENAI_API_KEY trong file .env. "
                "Tuyệt đối không dùng vector ngẫu nhiên (random mock)."
            )

        # Cấu hình OpenRouter endpoint
        base_url = "https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") else None
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        # Xử lý theo từng batch để không bị quá tải request hoặc lỗi payload
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            # Thay thế văn bản rỗng bằng khoảng trắng để tránh lỗi API
            cleaned_batch = [t if t.strip() else " " for t in batch]

            try:
                response = self.client.embeddings.create(
                    model=self.model_name,
                    input=cleaned_batch,
                )

                # Sắp xếp lại theo đúng thứ tự index trả về của API
                sorted_items = sorted(response.data, key=lambda x: x.index)
                for item in sorted_items:
                    vec = item.embedding
                    if len(vec) != self.dimensions:
                        raise ValueError(f"Sai lệch số chiều: kỳ vọng {self.dimensions}, nhận được {len(vec)}")
                    all_embeddings.append(vec)

            except Exception as e:
                # Báo lỗi cụ thể, không âm thầm fallback sang vector ngẫu nhiên
                raise RuntimeError(f"Lỗi khi gọi API embedding cho batch {i}-{i+len(batch)}: {e}") from e

        return all_embeddings

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        if not question or not question.strip():
            question = " "

        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=[question],
            )
            vec = response.data[0].embedding
            if len(vec) != self.dimensions:
                raise ValueError(f"Sai lệch số chiều query: kỳ vọng {self.dimensions}, nhận được {len(vec)}")
            return vec

        except Exception as e:
            raise RuntimeError(f"Lỗi khi tạo query embedding cho câu hỏi '{question}': {e}") from e
