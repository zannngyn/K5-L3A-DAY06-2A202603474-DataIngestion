# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**
  - Sách *Introduction to Sociology 3e* (OpenStax), https://openstax.org/details/books/introduction-sociology-3e, truy cập 2026-11-13. Giấy phép **CC BY-NC-SA 4.0**: dùng phi thương mại, ghi công OpenStax; chunk, text chuẩn hóa và trace có trích nội dung sách giữ cùng giấy phép.
  - File PDF 664 trang vật lý. Chỉ dùng **chương 1 (PDF trang 19–37, 19 trang) và chương 2 (PDF trang 47–67, 21 trang) = 40 trang nội dung**.
  - Quy tắc: đếm trang PDF vật lý (đánh số từ 1) có nội dung chính; loại bìa, mục lục, preface (1–18) và phần cuối chương — key terms, summary, quiz, short answer, further research, references (38–46, 68–76). Chi tiết trong [`data/manifest.json`](../../data/manifest.json).
- **Chuẩn hóa, lỗi và giới hạn:**
  - Đọc bằng pypdf 6.21.4: 40/40 trang có text, 0 trang rỗng, 0 trang lỗi ([`ingestion_log.json`](../../starter/results/ingestion_log.json)).
  - Chuẩn hóa: Unicode NFKC (tách ký tự ghép như `ﬁ`); bỏ header/footer lặp lại và nhãn hộp viết hoa (`SOCIOLOGY IN THE REAL WORLD`...); nối từ có gạch nối bị xuống dòng; dựng lại đoạn văn bằng heuristic độ dài dòng + dấu câu vì pypdf không tách đoạn bằng dòng trống. Giữ nguyên dấu nháy để evidence vẫn khớp. Sau chuẩn hóa còn 121.063 ký tự (text thô: 124.398).
  - Giới hạn: Bảng 1.1 (trang 30) bị trích thành mảnh rời; heuristic dựng đoạn đôi khi dính heading vào cuối đoạn trước (ví dụ "Surveys" ở trang 53); chunk không vượt ranh giới trang nên có mẩu câu ngắn ở đầu/cuối trang.
- **Embedding, vector store, metric, lệnh chạy và chi phí:**
  - Embedding: OpenRouter, `qwen/qwen3-embedding-8b`, **4096 chiều** (mặc định của model). Query có instruction theo model card: `Instruct: Given a question about an introductory sociology textbook, retrieve passages that answer the question\nQuery:{question}`; document không có instruction. Giữ nguyên cho cả 3 cấu hình.
  - Vector store: PostgreSQL 16.16 + pgvector 0.8.7 (Docker). Metric cosine (`<=>`), **exact search, không index** vì HNSW/IVFFlat trên `vector` chỉ hỗ trợ tối đa 2000 chiều; với 503 vector exact search vẫn nhanh (14–30 ms/truy vấn).
  - Chi phí: build index A+B 50.415 token = **0,000504 credit OpenRouter**; embed câu hỏi dev 593 token, test 191 token (< 0,00001 credit). Thời gian embed index: A 105 giây, B 39 giây (phụ thuộc độ trễ mạng/provider).
  - Môi trường: Python 3.11.16, psycopg 3.3.8, python-dotenv 1.2.4. Lệnh chạy (trong `starter/`):
    ```bash
    docker compose -p day6_student_starter up -d --wait
    python scripts/export_chunks.py                  # chunk A/B + log + kiểm evidence
    python scripts/build_index.py                    # embed + upsert A/B
    python -m src.run                                # benchmark dev
    python -m src.run --split test --confirm-test    # benchmark test (sau khi chốt cấu hình)
    ```
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:**
  - Mỗi chunk có `document_id`, `source` (URL sách), `page` (trang PDF), cùng `chapter`, `chapter_title`, `section`, `char_start`, `char_end`.
  - Trường lọc: **`chapter`** (số nguyên 1/2), lấy từ manifest theo khoảng trang — không đoán. Chọn vì sách có nhiều khái niệm lặp lại ở cả hai chương (Max Weber, Frankfurt School, lương tối thiểu, qualitative), nên lọc theo chương có ích thật.
  - `section` (ví dụ `2.2`) lấy từ heading mục có `LEARNING OBJECTIVES` ngay sau; phần mở đầu chương gán `1.0`/`2.0`.

## Cấu hình và benchmark

- **A / B / C:**

  | Cấu hình | Chunk | Truy xuất | Số chunk |
  |---|---|---|---|
  | A | Cửa sổ ký tự cố định 500, overlap 50, trong từng trang | Không lọc | 286 |
  | B | Gom đoạn văn trong từng trang, tối đa 800 ký tự; heading đi kèm đoạn sau; đoạn quá dài cắt theo câu | Không lọc | 217 |
  | C | **Dùng chung chunk và vector với B** | Lọc `chapter` khi câu hỏi có filter | 217 |

  - **B–C khác đúng một yếu tố**: metadata filter. A–B khác cả cách cắt lẫn độ dài tối đa (500 so với 800).
  - Nạp lại không trùng: khóa chính `(strategy, chunk_id)`, chunk ID cố định theo trang và thứ tự; chunk không còn trong lần build mới bị xóa cùng transaction; chunk có text không đổi không gọi embedding lại (lần build thứ 2: 0 token, DB vẫn A=286 / B=217).
- **Benchmark:** [`benchmark/questions.json`](../../benchmark/questions.json), 20 câu tiếng Anh, chia **15 dev / 5 test trước khi chạy**. Loại câu: 7 trực tiếp, 6 diễn đạt lại, 3 điều kiện/ngoại lệ, 4 metadata filter (q14, q15 dev; t04, t05 test). Câu filter chọn chủ đề xuất hiện ở cả hai chương để filter có tác dụng thật; câu hỏi không chứa tên chương/số trang, filter coi là ngữ cảnh người dùng cung cấp trước. Evidence: cả 20 `evidence_quote` đã kiểm bằng script — có nguyên văn trên `gold_page`, trước và sau chuẩn hóa, và nằm trọn trong 1 chunk ở cả A và B.
- **Tiêu chí chọn chiến lược (chốt trước khi xem test):** (1) Evidence Hit@3 dev cao nhất; (2) hòa → Hit@1 dev; (3) hòa → ít chunk/chi phí thấp hơn. Sau khi xem dev, B và C hòa cả ba bậc, nên **thêm bậc 4 — filter compliance trên dev — sau khi xem dev nhưng trước khi chạy test**. Theo bậc 4 chọn **C**. Ghi trong [`artifacts/experiment_log.csv`](../../artifacts/experiment_log.csv).

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 13/15 | 15/15 | 286 | embed index 105 s; tìm 23,8 ms/câu | 0,000265 credit (index) |
| B | dev | 14/15 | 15/15 | 217 | embed index 39 s; tìm 16,6 ms/câu | 0,000238 credit (index) |
| C | dev | 14/15 | 15/15 | 217 | dùng index B; tìm 19,4 ms/câu | 0 thêm |
| A | test | 2/5 | 4/5 | 286 | tìm 29,6 ms/câu | — |
| B | test | 2/5 | 4/5 | 217 | tìm 22,3 ms/câu | — |
| C | test | 2/5 | 4/5 | 217 | tìm 14,5 ms/câu | — |

Embed câu hỏi dùng chung cho A/B/C: dev 15 câu 593 token, test 5 câu 191 token. Thời gian tìm kiếm đo trên máy local, chỉ mang tính tham khảo.

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 1,0 (10) | 15/15 | dev 0/2 · test 0/2 | 0 / 1 / 4 câu — 1,8 |
| B | 1,8 (10) | 15/15 | dev 0/2 · test 2/2 | 1 / 0 / 4 câu — 1,6 |
| C | = B (dùng chung chunk) | 15/15 | dev 2/2 · test 2/2 | 1 / 0 / 4 câu — 1,6 |

"Grounding 0/1/2" là **số câu** đạt mỗi mức điểm trên 5 câu test, không phải điểm.

**Đường dẫn trace, nhãn thủ công và cách chọn mẫu:**
- Trace top-3 đầy đủ: [`traces_dev.jsonl`](../../starter/results/traces_dev.jsonl), [`traces_test.jsonl`](../../starter/results/traces_test.jsonl); tổng hợp: `summary_{dev,test}.{json,md}`; metadata lần chạy: `run_meta_{dev,test}.json`.
- Nhãn: [`audit_coherence.csv`](../../starter/results/audit_coherence.csv), [`audit_metadata.csv`](../../starter/results/audit_metadata.csv), [`audit_grounding.csv`](../../starter/results/audit_grounding.csv).
- Coherence: 10 vị trí chọn **trước khi có điểm**, không phụ thuộc benchmark — trang 19, 23, 27, 31, 35, 49, 53, 57, 61, 65, mỗi trang lấy chunk chứa điểm giữa text đã chuẩn hóa.
- Metadata: 5 câu test × top-3 × 3 cấu hình = 45 bản ghi, đối chiếu với text thô của PDF độc lập với code pipeline. Grounding: 5 câu test × 3 cấu hình, chấm trên toàn văn top-3, không dựa vào Hit tự động.
- **Người chấm**: Văn

## Phân tích và kết luận

- **Retrieval:** Dev bị "trần": Hit@3 = 15/15 ở cả ba cấu hình nên không phân biệt được bằng Hit@3; khác biệt chỉ ở Hit@1 (A 13 so với B/C 14). Test thấp hơn hẳn (Hit@1 2/5, Hit@3 4/5 ở cả ba). Lỗi chủ yếu là hạng 1 **đúng trang gold nhưng là chunk bên cạnh**, không chứa nguyên văn evidence.
- **So sánh A–B (chunking):** B giữ trọn ý tốt hơn rõ rệt (coherence 1,8 so với 1,0; mọi chunk A cắt giữa từ/câu) và cần ít chunk hơn (217 so với 286, rẻ hơn khi embed). Về Hit, B hơn A một câu ở dev; ở test hòa.
- **So sánh B–C (metadata filter):** Hit@1/Hit@3 không đổi ở cả dev và test. Filter chỉ tác động đến **phạm vi** top-3: trên dev, B lẫn chunk chương khác ở cả 2 câu filter (0/2), C loại hết (2/2). Trên test, B tự trả đúng chương (2/2) nên filter không tạo khác biệt.
- **Ví dụ lỗi:**
  1. **q15** (dev, A, gold trang 65): hạng 1 đúng trang nhưng chunk cố định bị cắt nên không chứa trọn câu "value neutrality"; chunk chứa evidence đứng hạng 2. B/C trúng hạng 1 → lỗi do cắt cứng.
  2. **t01** (test, B/C, gold trang 62): chunk B chứa câu "case studies are useful when the single case is unique" không vào top-3; top-3 chỉ có định nghĩa case study và câu "most sociologists do not use case studies" → grounding 0. A trúng hạng 1 → ví dụ hiếm khi cắt cứng thắng cắt theo đoạn.
  3. **t04** (test, A, gold trang 59): không filter nên hạng 2 lẫn chunk chương 1 về lương tối thiểu (trang 27); chunk A trang 59 mất câu nêu tên Ehrenreich và *Nickel and Dimed* → grounding 1.
  4. **t03** (test, B/C): hạng 1 là chú thích hình 1.9 nêu "Kenneth and Mamie Clark" — trả lời đúng nhưng không chứa nguyên văn evidence nên tự động bị tính trượt Hit@1; grounding thủ công vẫn 2. Cho thấy so khớp nguyên văn quá nghiêm. tại đây quyết định manual override
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:** Chọn **C** theo tiêu chí đã chốt. Lý do thực chất: chunk theo đoạn dễ đọc và ít chunk hơn; filter đảm bảo top-3 đúng phạm vi khi người dùng chỉ định chương — có ích khi khái niệm lặp lại giữa các chương. Đánh đổi: chunk dài không đều (37–848 ký tự), phụ thuộc chất lượng heuristic dựng đoạn; filter chỉ dùng được khi người dùng cung cấp phạm vi và metadata đáng tin.
- **Hạn chế:**
  - Test chỉ 5 câu, dev 15 câu: chênh 1 câu = 7–20 điểm phần trăm; không đủ để khẳng định cấu hình nào tốt hơn ngoài corpus này.
  - Câu hỏi viết bám sát câu văn gốc → dev dễ, Hit@3 bão hòa.
  - Định nghĩa hit yêu cầu chứa nguyên văn evidence → bỏ sót bằng chứng tương đương (t03).
  - Bậc phân xử thứ 4 được thêm sau khi xem dev (trước test).
  - Mẫu metadata không chứa ca lỗi `section` đã biết (chunk bắt đầu ở phần mở đầu chương bị gán `x.0`), nên 45/45 không chứng minh trường này luôn đúng.
  - Thời gian embed phụ thuộc mạng/provider; chi phí tính bằng credit OpenRouter.
  - Nhãn thủ công do LLM chấm trước, tác giả duyệt lại → không độc lập.
- **Nếu làm lại hoặc mở rộng:**
  - Viết câu hỏi diễn đạt xa câu gốc hơn và tăng số câu test để benchmark phân biệt được cấu hình.
  - Cho chunk B vượt ranh giới trang (lưu danh sách trang) để tránh mẩu câu ngắn ở đầu/cuối trang.
  - Nhận diện heading tốt hơn (dùng vị trí/cỡ chữ trong PDF) để sửa lỗi heading dính đoạn và bảng bị vỡ.
  - Thử hybrid dense + BM25, và thử giảm số chiều (MRL) để dùng được index HNSW — chọn trên dev, giữ nguyên giữa các cấu hình.

## Sử dụng AI và cách kiểm tra

- Công cụ: Claude Code (model Claude Opus 5.5) hỗ trợ viết code pipeline, soạn bộ câu hỏi.
- Cách kiểm tra:
  - Evidence: script đối chiếu từng `evidence_quote` với text PDF trên đúng trang.
  - Kết quả Hit: tự đọc trace của các câu trượt và câu có filter, đối chiếu với kết quả tự động.
  - Nạp lại: chạy build index 2 lần, kiểm tra 0 dòng trùng.
  - Nhánh lỗi: thử key sai, filter ngoài whitelist, giá trị filter kiểu SQL injection.
- Toàn bộ số liệu trong báo cáo lấy từ các file trong `starter/results/`, không có số tự đặt.
