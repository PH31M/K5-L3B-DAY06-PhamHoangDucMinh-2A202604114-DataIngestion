# Day 06 · Data Ingestion Engineering

- **Học viên**: Phạm Hoàng Đức Minh
- **MSSV**: 2A202604114
- **Lớp**: L3B
- **Báo cáo cá nhân chi tiết**: [report/individual/2A202604114_PhamHoangDucMinh.md](report/individual/2A202604114_PhamHoangDucMinh.md)
- **Tài liệu nguồn & Manifest**: [data/manifest.md](data/manifest.md) (World Bank International Debt Report 2026, 32 trang vật lý 75–106)
- **Bộ Benchmark (22 câu)**: [benchmark/questions.json](benchmark/questions.json)

---

## Hướng dẫn Chạy & Tái lập (Reproduction Guide)

### 1. Chuẩn bị Môi trường & Khởi động Database

Yêu cầu: Python 3.11+ và Docker Desktop.

```bash
# 1. Kích hoạt môi trường ảo Python
cd starter
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt openai python-dotenv

# 2. Cấu hình biến môi trường
cp .env.example .env
# Điền OPENROUTER_API_KEY hoặc OPENAI_API_KEY vào starter/.env nếu cần chạy lại embedding API

# 3. Khởi động PostgreSQL + pgvector
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

Kỳ vọng: In ra `Setup OK. Pipeline functions still need to be implemented.` (kết nối database thành công).

### 2. Chạy Pipeline & Đánh giá Tự động

Chạy pipeline end-to-end từ thư mục `starter/`:

```bash
python -m src.run
```

Lệnh trên sẽ tự động:
1. Nạp và chuẩn hóa 32 trang PDF từ `data/bookdata_01.pdf`.
2. Tạo 3 chiến lược Ingestion (Strategy A: Fixed 500/50; Strategy B: Paragraph 800; Strategy C: Paragraph 800 + Metadata Filter).
3. Tạo embedding model thật và lưu trữ vector vào PostgreSQL + pgvector (đảm bảo tính idempotent, không nhân đôi khi chạy lại).
4. Thực thi 22 câu hỏi benchmark (16 dev / 6 test), đo lường Hit@1, Evidence Hit@3.
5. Xuất vết truy xuất ra `results/all_traces.json`, cập nhật `artifacts/experiment_log.csv` và in bảng tóm tắt kết quả ra terminal.

---

## Tóm tắt Kết quả Thí nghiệm

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunks | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| **A (Fixed 500/50)** | Dev / Test / All | 10/16 \| 0/6 \| **10/22 (45.5%)** | 12/16 \| 1/6 \| **13/22 (59.1%)** | 169 | 9.61s | ~$0.0003 |
| **B (Paragraph 800)** | Dev / Test / All | 11/16 \| 2/6 \| **13/22 (59.1%)** | 13/16 \| 5/6 \| **18/22 (81.8%)** | 108 | 6.22s | ~$0.0002 |
| **C (B + Metadata Filter)** | Dev / Test / All | 11/16 \| 2/6 \| **13/22 (59.1%)** | 13/16 \| 5/6 \| **18/22 (81.8%)** | 108 | 0.07s | $0.00 (reused) |

Chi tiết đánh giá 5 khía cạnh và phân tích case lỗi xem tại [Báo cáo cá nhân](report/individual/2A202604114_PhamHoangDucMinh.md).

---

## Bắt đầu nhanh (Đề bài gốc)

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.
