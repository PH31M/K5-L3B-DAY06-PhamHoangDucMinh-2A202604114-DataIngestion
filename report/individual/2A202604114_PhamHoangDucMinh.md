# Báo cáo cá nhân — Day 6 · Data Ingestion Engineering

Học viên: **Phạm Hoàng Đức Minh**  
MSSV: **2A202604114**  
Lớp: **L3B**  
Repo bài nộp: [GitHub Repo](https://github.com/PH31M/K5-L3B-DAY06-PhamHoangDucMinh-2A202604114-DataIngestion.git)

---

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang**:
  - **Chủ đề & Nguồn tài liệu**: Báo cáo Nợ Quốc tế 2026 (*International Debt Report 2026: Debt Dynamics—Policy Implications*), xuất bản bởi Nhóm Ngân hàng Thế giới (World Bank Group). Giấy phép Creative Commons Attribution 3.0 IGO ([CC BY 3.0 IGO](https://creativecommons.org/licenses/by/3.0/igo/)). DOI: `10.1596/978-1-4648-2355-8`. Chi tiết tại [manifest.md](file:///Users/minh/GitHub-PMinh/K5-L3B-DAY06-PhamHoangDucMinh-2A202604114-DataIngestion/data/manifest.md).
  - **Quy tắc tính trang**: File PDF có tổng cộng 280 trang vật lý. Phạm vi được chọn để ingest là toàn bộ Chương 2 ("Debt Dynamics: Policy Implications").
  - **Ánh xạ số trang**:
    - Trang in trên sách (printed page): Trang 51 đến trang 82 (đúng 32 trang nội dung chuyên môn hữu ích). Bỏ qua hoàn toàn trang bìa, lời tựa, mục lục (đánh số La Mã từ i đến xxi) và các chương/phụ lục ngoài phạm vi nghiên cứu.
    - Trang vật lý trong file PDF (physical page): Trang 75 đến trang 106 (gồm đúng 32 trang). Pipeline và toàn bộ nhãn `gold_page` được quy chuẩn đồng nhất theo số trang vật lý PDF (75–106) để đảm bảo tính truy vết chính xác tuyệt đối.
  - **Số ký tự thực tế**: 71.116 ký tự sau trích xuất và tiền xử lý.

- **Chuẩn hóa, lỗi và giới hạn**:
  - **Chuẩn hóa văn bản**: Sử dụng thư viện `pypdf` để bóc tách text từng trang vật lý. Áp dụng chuẩn hóa Unicode `NFKC` (qua `unicodedata.normalize`) nhằm chuẩn hóa font và ký tự đặc biệt, khử null bytes (`\x00`), chuyển đổi `\xa0` thành khoảng trắng thường, chuẩn hóa xuống dòng Unix `\n`. Xử lý hiện tượng gạch nối ngắt dòng (hyphenation at line breaks, ví dụ `sus-\ntainability` thành `sustainability`).
  - **Lỗi và phát hiện ngoại lệ**: Trang vật lý 106 là trang kết chương chứa bảng chú dẫn phụ chú ngắn (dưới 50 ký tự hữu ích), pipeline tự động ghi nhận log cảnh báo `is_empty = True` mà không làm sập pipeline. Các trang còn lại trích xuất văn bản rõ ràng, không gặp lỗi font mã hóa.
  - **Giới hạn**: Các biểu đồ dạng vector và đồ thị phức tạp (figures/charts) chỉ trích xuất được phần tiêu đề và số liệu ghi chú dạng văn bản, chưa có OCR hình ảnh chuyên sâu cho đồ họa pixel.

- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí**:
  - **Embedding model**: `openai/text-embedding-3-small` (version mới nhất, 1536 chiều vector).
  - **Provider**: Truy xuất qua OpenRouter API Gateway (`https://openrouter.ai/api/v1`), có cơ chế xử lý theo batch và xác thực kích thước vector trả về; tuyệt đối không dùng mock vector ngẫu nhiên.
  - **Vector store**: `PostgreSQL 16` kết hợp extension `pgvector` (chạy trên Docker container local cổng 55433).
  - **Metric**: Khoảng cách Cosine (`<=>` trong pgvector, score tương đồng cosine = $1 - \text{distance}$).
  - **Lệnh chạy**: `python -m src.run` (từ thư mục `starter/`).
  - **Chi phí thực tế**: Tổng chi phí gọi API OpenRouter cho toàn bộ quá trình embedding corpus và truy vấn benchmark là **~$0.0006** (rất tiết kiệm, dưới 1 cent).

- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn**:
  - **Metadata bắt buộc**: `document_id` (`bookdata_01`), `source` (*World Bank International Debt Report 2026*), `page` (số trang vật lý PDF 75–106).
  - **Trường lọc bổ sung**:
    - `section`: Phân đoạn chủ đề theo nội dung chương, gồm: `transmission_shocks` (Trang 75–84: Cơ chế truyền dẫn các cú sốc bên ngoài), `fiscal_pressures` (Trang 85–95: Áp lực tài khóa và ổn định nợ công), `food_import` (Trang 96–102: Nhập khẩu lương thực và rủi ro dinh dưỡng), `notes_references` (Trang 103–106: Ghi chú và trích dẫn).
    - `year`: 2026 (Năm xuất bản báo cáo).
    - `chapter`: 2 (Chương 2 của báo cáo).
  - **Lý do chọn**: Báo cáo nợ có cấu trúc chia phần rất rõ ràng giữa các chủ đề vĩ mô (cú sốc ngoại lai vs áp lực nợ vs an ninh lương thực). Metadata `section` giúp người dùng hoặc hệ thống AI giới hạn phạm vi truy vấn đúng phân khu chuyên môn, tránh tình trạng tìm nhầm số liệu giữa các ngành khác nhau.

---

## Cấu hình và benchmark

- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C)**:
  - **Chiến lược A (Fixed-size Baseline)**: Cắt văn bản theo cửa sổ kích thước cố định `chunk_size = 500` ký tự, bước trượt gối đầu `overlap = 50` ký tự. Metadata đầy đủ (`document_id`, `source`, `page`, `section`). Truy xuất top-3 hoàn toàn bằng Cosine Similarity, **không lọc metadata**.
  - **Chiến lược B (Structure-aware Paragraph)**: Cắt văn bản theo ranh giới đoạn văn bản tự nhiên (`\n+`), bẻ nhỏ các đoạn văn quá dài (oversized > 800 ký tự) theo câu hoàn chỉnh, sau đó gom cụm các đoạn văn liên tiếp sao cho tổng kích thước tối đa `max_size = 800` ký tự (không dùng overlap). Cùng metadata, **không lọc metadata**.
  - **Chiến lược C (Structure-aware Paragraph + Metadata Filtering)**: Dùng **chính xác cấu trúc chunk và vector embedding của Chiến lược B**; điểm khác biệt duy nhất là khi câu hỏi có yêu cầu lọc phạm vi (`filter: {"section": "..."}`), hệ thống bổ sung điều kiện lọc `WHERE section = %s` trong truy vấn SQL. Các câu hỏi không có filter sẽ truy xuất tương tự Chiến lược B.

- **≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence**:
  - **Quy mô bộ câu hỏi**: Bộ Benchmark gồm **22 câu hỏi** độc lập được lưu tại [benchmark/questions.json](file:///Users/minh/GitHub-PMinh/K5-L3B-DAY06-PhamHoangDucMinh-2A202604114-DataIngestion/benchmark/questions.json).
  - **Phân chia split**: **16 câu Dev** (từ `q01` đến `q16`) và **6 câu Test** (từ `q17` đến `q22`).
  - **Đa dạng câu hỏi**: Phủ rộng các dạng câu hỏi: trực tiếp (*direct*), diễn đạt lại (*paraphrase*), câu hỏi điều kiện/ngoại lệ (*conditional*), và câu hỏi phân biệt bằng metadata (*metadata_filter*).
  - **Câu hỏi kiểm tra Metadata Filter**: Có **5 câu hỏi có filter** (chiếm 22.7%), gồm 3 câu tập Dev (`q07`, `q11`, `q15`) và 2 câu tập Test (`q20`, `q22`), thỏa mãn điều kiện $\ge 3$ câu filter và $\ge 1$ câu test.
  - **Cách kiểm chứng Evidence**: Từng đoạn `evidence_quote` được sao chép và đối chiếu thủ công trực tiếp từ văn bản sau chuẩn hóa của đúng trang `gold_page`, đảm bảo bằng chứng tồn tại nguyên văn và trả lời trọn vẹn câu hỏi trước khi chạy benchmark.

- **Tiêu chí chọn chiến lược đã chốt trước khi xem test**:
  - Thứ tự ưu tiên quyết định lựa chọn:
    1. **Evidence Hit@3 trên tập Dev**: Khả năng bao hàm bằng chứng chính xác trong top-3 kết quả truy xuất.
    2. **Grounding Quality & Chunk Coherence**: Văn bản chunk phải bảo toàn câu/đoạn trọn vẹn để AI agent có đủ ngữ cảnh lập luận.
    3. **Hiệu quả tài nguyên**: Giảm thiểu số lượng chunk phân mảnh, giảm chi phí lưu trữ và thời gian embedding.

---

## Kết quả

### Bảng 1: Hiệu năng Truy xuất và Tài nguyên Ingestion

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| **A (Fixed 500/50)** | Dev | 10/16 (62.50%) | 12/16 (75.00%) | 169 chunks | 9.61s | ~$0.0003 |
| **A (Fixed 500/50)** | Test | 0/6 (0.00%) | 1/6 (16.67%) | 169 chunks | - | - |
| **A (Fixed 500/50)** | **All** | **10/22 (45.45%)** | **13/22 (59.09%)** | **169 chunks** | **9.61s** | **~$0.0003** |
| **B (Paragraph 800)** | Dev | 11/16 (68.75%) | 13/16 (81.25%) | 108 chunks | 6.22s | ~$0.0002 |
| **B (Paragraph 800)** | Test | 2/6 (33.33%) | 5/6 (83.33%) | 108 chunks | - | - |
| **B (Paragraph 800)** | **All** | **13/22 (59.09%)** | **18/22 (81.82%)** | **108 chunks** | **6.22s** | **~$0.0002** |
| **C (B + Filter)** | Dev | 11/16 (68.75%) | 13/16 (81.25%) | 108 chunks | 0.07s | $0.00 (reused) |
| **C (B + Filter)** | Test | 2/6 (33.33%) | 5/6 (83.33%) | 108 chunks | - | - |
| **C (B + Filter)** | **All** | **13/22 (59.09%)** | **18/22 (81.82%)** | **108 chunks** | **0.07s** | **$0.00** |

---

### Bảng 2: Đánh giá Chất lượng 5 Khía cạnh Chuẩn hóa

| Strategy | Coherence trung bình /2 (n=10) | Metadata đủ và đúng (n/N, n=18) | Filter tuân thủ (n/N) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| **A (Fixed 500/50)** | **0.20 / 2** (2/20 điểm) | 18/18 (100%) | N/A (không dùng filter) | 0: 1 câu \| 1: 4 câu \| 2: 1 câu $\rightarrow$ **1.00 / 2** |
| **B (Paragraph 800)** | **1.70 / 2** (17/20 điểm) | 18/18 (100%) | N/A (không dùng filter) | 0: 0 câu \| 1: 1 câu \| 2: 5 câu $\rightarrow$ **1.83 / 2** |
| **C (B + Filter)** | **1.70 / 2** (17/20 điểm) | 18/18 (100%) | 6/6 (100% tuân thủ) | 0: 0 câu \| 1: 1 câu \| 2: 5 câu $\rightarrow$ **1.83 / 2** |

- **Đường dẫn trace, nhãn thủ công và cách chọn mẫu**:
  - Dữ liệu trace chi tiết từng câu hỏi: [results/all_traces.json](file:///Users/minh/GitHub-PMinh/K5-L3B-DAY06-PhamHoangDucMinh-2A202604114-DataIngestion/results/all_traces.json).
  - Tóm tắt benchmark tự động: [results/benchmark_summary.json](file:///Users/minh/GitHub-PMinh/K5-L3B-DAY06-PhamHoangDucMinh-2A202604114-DataIngestion/results/benchmark_summary.json).
  - Nhật ký thí nghiệm: [artifacts/experiment_log.csv](file:///Users/minh/GitHub-PMinh/K5-L3B-DAY06-PhamHoangDucMinh-2A202604114-DataIngestion/artifacts/experiment_log.csv).
  - Mẫu chấm thủ công Coherence: [results/manual_coherence.json](file:///Users/minh/GitHub-PMinh/K5-L3B-DAY06-PhamHoangDucMinh-2A202604114-DataIngestion/results/manual_coherence.json) (chọn ngẫu nhiên có hệ thống tại đoạn đầu của 10 trang vật lý đầu tiên từ 75 đến 84).
  - Mẫu chấm thủ công Grounding: [results/manual_grounding.json](file:///Users/minh/GitHub-PMinh/K5-L3B-DAY06-PhamHoangDucMinh-2A202604114-DataIngestion/results/manual_grounding.json) (chấm toàn diện trên toàn bộ 6 câu hỏi tập Test `q17`–`q22`).

---

## Phân tích và kết luận

### 1. So sánh chi tiết A–B và B–C

- **So sánh A–B (Fixed-size vs Structure-aware Paragraph)**:
  - **Độ chính xác truy xuất**: Trên tập Test, Strategy A sụp đổ hoàn toàn về độ chính xác: Hit@1 đạt **0.00% (0/6)** và Hit@3 chỉ đạt **16.67% (1/6)**. Trong khi đó, Strategy B nâng Hit@1 lên **33.33% (2/6)** và Hit@3 lên tới **83.33% (5/6)**.
  - **Tính mạch lạc (Coherence)**: Strategy A đạt điểm cực thấp (**0.20/2**) vì có tới 8/10 vị trí bị cắt đứt ngang từ vựng hoặc ngắt đôi cấu trúc câu ở mốc 500 ký tự (ví dụ: `when gov`, `lead to currenc`, `external debt st`). Ngược lại, Strategy B đạt **1.70/2** nhờ tôn trọng ranh giới đoạn văn và câu kết thúc bằng dấu chấm, giúp câu văn tự đứng độc lập và giữ nguyên vẹn ngữ nghĩa.
  - **Tài nguyên**: Strategy B giảm số lượng chunk từ 169 xuống 108 chunk (**giảm 36.1% số vector lưu trữ**), nhờ đó giảm thời gian embedding từ 9.61s xuống 6.22s và tiết kiệm chi phí tương ứng.

- **So sánh B–C (Ảnh hưởng cô lập của Metadata Filter)**:
  - Giữa B và C, cấu trúc chunk và vector là hoàn toàn đồng nhất. Điểm khác biệt duy nhất nằm ở cơ chế lọc metadata khi có yêu cầu.
  - Điểm Hit@1 và Hit@3 tổng thể của B và C trên bộ câu hỏi là tương đương nhau (do kích thước corpus 32 trang chưa quá lớn để gây ra va chạm ngữ nghĩa nặng). Tuy nhiên, **Strategy C đạt tỷ lệ tuân thủ filter 100% (6/6 records)**.
  - Phân tích sâu cho thấy Strategy C đã loại bỏ hoàn toàn các trang "nhiễu" không thuộc phạm vi quan tâm. Ví dụ ở câu `q22`, Strategy B đưa nhầm chunk thuộc trang 95 (thuộc section `fiscal_pressures`) lên Rank 1 vì có từ khóa nợ tương đồng, trong khi Strategy C loại bỏ hoàn toàn trang 95 và chỉ giữ lại đúng các chunk thuộc `food_import` (trang 96 và trang 100). Điều này bảo vệ an toàn tuyệt đối cho các LLM Agent phía sau không bị "ảo giác" chéo chủ đề.

---

### 2. Phân tích 2 ví dụ sai cụ thể (Failure Case Analysis)

#### Ví dụ 1: Câu `q20` trong Strategy A (Lỗi do cắt vụn văn bản cố định)
- **ID câu**: `q20` (Tập Test, dạng `metadata_filter`)
- **Nội dung câu hỏi**: *"In the section on fiscal pressures and consolidation, how long did countries typically delay meaningful consolidation when facing primary deficits far above debt-stabilizing levels?"*
- **Trang nguồn Gold**: Trang 93 (`gold_page: 93`).
- **Đoạn bằng chứng Gold**: *"Where the primary deficit was significantly larger than what would stabilize debt, countries tended to wait three to four years before embarking on meaningful fiscal consolidation"*
- **Kết quả Strategy A**: `hit_at_1 = False`, `hit_at_3 = False`.
  - Kết quả Rank 1 của Strategy A trả về chunk:  
    `"years before embarking on meaningful fiscal consolidation (figure B2.3.2; Di Lorenzo and Lacey 2024)..."`
- **Nguyên nhân thất bại**: Cửa sổ 500 ký tự cắt ngang qua giữa câu văn. Nửa đầu câu (*"Where the primary deficit was significantly larger..."*) bị giữ ở chunk phía trước, còn nửa sau câu bị đẩy sang chunk Rank 1. Hậu quả là chunk Rank 1 mất đi điều kiện chủ ngữ tiền đề ("khi thâm hụt cơ bản lớn hơn mức ổn định nợ"), dẫn tới việc không khớp được bằng chứng gold.
- **Đối chiếu Strategy B & C**: Cả B và C đều đạt `Hit@1 = True` trên câu `q20` vì hàm `by_paragraph` đã gom trọn vẹn toàn bộ câu văn vào một khối ngữ nghĩa 800 ký tự.

#### Ví dụ 2: Câu `q22` trong Strategy C (Lỗi phân mảnh ranh giới danh sách liệt kê)
- **ID câu**: `q22` (Tập Test, dạng `metadata_filter`, section `food_import`)
- **Nội dung câu hỏi**: *"In the context of food import exposure and debt burdens, which specific nutritional food groups exhibit lower import source diversity when external debt relative to exports is high?"*
- **Trang nguồn Gold**: Trang 100 (`gold_page: 100`).
- **Đoạn bằng chứng Gold**: *"Higher debt relative to exports is significantly associated with lower import source diversity for starchy staples and, notably, for animal-source foods, fruits, and vegetables—nutritionally important components of a healthy diet that together account for a large share of its cost"*
- **Kết quả Strategy C**: `hit_at_1 = False`, `hit_at_3 = False`.
  - Rank 1 trả về trang 96 (tổng quan unaffordability), Rank 2 và Rank 3 trả về trang 100.
  - Chunk Rank 3 trang 100 bắt đầu từ: `"cost (figure 2.15). By contrast, higher debt burdens are associated with greater import source diversity for oils and fats..."`
- **Nguyên nhân thất bại**: Câu bằng chứng gốc quá dài và phức tạp (vừa có dấu gạch ngang vừa có ngắt đoạn). Khi chia nhỏ đơn vị văn bản quá giới hạn `max_size`, điểm ngắt rơi đúng vào chữ *"cost"*. Phần danh sách quan trọng (*"starchy staples, animal-source foods..."*) bị nằm ở cuối chunk trước, còn phần giải thích bổ trợ nằm ở chunk sau. Cả hai chunk đều không chứa trọn vẹn 100% xâu ký tự của câu trả lời.
- **Bài học rút ra**: Cần bổ sung thuật toán tách câu thông minh hơn (sentence tokenizer dựa trên NLP như `nltk` hoặc `spacy`) thay vì chỉ dùng regex ngắt câu đơn giản.

---

### 3. Chiến lược lựa chọn, đánh đổi và điều kiện áp dụng

- **Chiến lược được chọn**: **Chiến lược C (Structure-aware Paragraph + Metadata Filtering)**.
- **Lý do lựa chọn**:
  - Đạt điểm Evidence Hit@3 cao nhất (81.82% toàn bộ, 83.33% trên tập Test).
  - Duy trì tính mạch lạc ngữ nghĩa xuất sắc (Coherence 1.70/2) và chất lượng Grounding vượt trội (1.83/2).
  - Tối ưu số lượng chunk (108 chunk so với 169 chunk của baseline, tiết kiệm 36% dung lượng và chi phí embedding).
  - Đảm bảo tính cô lập dữ liệu 100% nhờ Metadata Filter, ngăn chặn triệt để hiện tượng tìm kiếm nhầm ngữ cảnh chéo giữa các phân đoạn tài liệu.
- **Các đánh đổi (Trade-offs)**:
  - *Độ phức tạp tiền xử lý*: Cần thời gian viết logic bóc tách và phân đoạn section cho tài liệu nguồn thay vì chỉ cắt chuỗi trượt đơn giản.
  - *Yêu cầu về truy vấn*: Phía client hoặc orchestrator cần trích xuất được metadata (ví dụ nhận biết người dùng đang hỏi về tài khóa hay nhập khẩu lương thực) trước khi kích hoạt filter trong SQL.
- **Điều kiện áp dụng thực tế**:
  - Cực kỳ phù hợp cho các kho tài liệu học thuật, báo cáo kinh tế, chính sách pháp luật, sổ tay kỹ thuật có cấu trúc chương/mục rõ ràng.

---

### 4. Hạn chế và Hướng cải tiến

- **Hạn chế**:
  - *Tập test còn nhỏ*: Tập test gồm 6 câu hỏi, phản ánh tốt các lỗi định tính nhưng có sai số mẫu nhất định khi ngoại suy thống kê phần trăm.
  - *Chưa xử lý bảng biểu biểu đồ chuyên biệt*: Báo cáo World Bank có nhiều bảng số liệu phức tạp (tables/matrix). Hiện tại pipeline đang coi bảng biểu như văn bản thường, có thể làm vỡ cấu trúc cột của bảng số liệu.
  - *Cắt câu dài chưa hoàn hảo*: Như đã chứng minh ở case `q22`, các câu phức dài trên 300 ký tự có thể bị ngắt đôi nếu thuật toán chia nhỏ chưa nhận thức được cây cú pháp.
- **Hướng cải tiến nếu làm lại hoặc mở rộng**:
  - **Hybrid Retrieval**: Kết hợp Dense Vector Search của pgvector với Sparse Keyword Search (BM25) qua PostgreSQL Full-Text Search (`tsvector`) hoặc Reciprocal Rank Fusion (RRF) để tối ưu hóa truy xuất các con số/mã hiệu chính xác.
  - **Table Parsing chuyên dụng**: Tích hợp các công cụ chuyên sâu như `pdfplumber` hoặc `unstructured` để trích xuất bảng dạng Markdown Table hoặc JSON trước khi chunking.
  - **Dynamic Context Window / Parent-Document Retrieval**: Lưu chunk nhỏ để tìm kiếm vector nhưng trả về chunk lớn (parent context) cho LLM để đảm bảo Grounding Quality luôn đạt điểm tối đa 2/2.
