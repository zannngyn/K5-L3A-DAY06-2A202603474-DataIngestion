# NOTE — ghi chú làm lab Day 06

Ghi chú cá nhân để viết báo cáo và trả lời khi bị hỏi. Số liệu dưới đây là số **đã chạy thật** trong phiên làm việc ngày 2026-11-13.

## 1. Corpus và giấy phép

- Sách: **Introduction to Sociology 3e**, OpenStax — `data/introduction-sociology-3e_-_WEB.pdf` (664 trang vật lý, 48MB).
- Giấy phép: **CC BY-NC-SA 4.0** (không phải CC BY như một số sách OpenStax khác).
  - BY: phải ghi công OpenStax + link + giấy phép.
  - NC: chỉ dùng phi thương mại → bài lab OK.
  - SA: chunk, text đã chuẩn hóa, trace có trích nội dung sách giữ cùng giấy phép CC BY-NC-SA 4.0. Code thì không bị ràng buộc.
- Dòng ghi công dùng trong README/báo cáo:
  > Nội dung trích từ *Introduction to Sociology 3e*, OpenStax, CC BY-NC-SA 4.0, https://openstax.org/details/books/introduction-sociology-3e. Đã trích chương 1–2, chuẩn hóa text và chia chunk.
- **Chưa quyết**: có đưa PDF 48MB vào `.gitignore` không (GitHub cho tối đa 100MB/file nên vẫn commit được; nếu bỏ thì người chấm tải lại qua link trong manifest).

## 2. Manifest và quy tắc đếm trang (`data/manifest.json`)

- `page` / `gold_page` = **số trang vật lý của PDF, đếm từ 1** (số trình đọc PDF hiển thị), không phải số in ở chân trang.
- Trang được tính: chương 1 = PDF **19–37** (19 trang), chương 2 = PDF **47–67** (21 trang) → **40 trang nội dung**.
- Trang loại: 1–18 (bìa, mục lục, preface), 38–46 và 68–76 (key terms, summary, quiz, short answer, further research, references).
- Lỗi đã sửa trong bản manifest đầu: lấy nhầm trang 7–27 (mục lục + preface), chỉ 1 chương (không filter được), sai tên chương 1 (đúng là "An Introduction to Sociology").
- **Cần cập nhật**: `char_count` trong manifest = 124.398 là đếm trên text pypdf **thô**; sau chuẩn hóa còn **121.063** ký tự. Ghi cả hai hoặc sửa lại.

## 3. Benchmark (`benchmark/questions.json`)

- 20 câu: **15 dev / 5 test**, chia **trước** khi chạy truy xuất.
- Loại câu: 7 trực tiếp, 6 diễn đạt lại, 3 điều kiện/ngoại lệ, 4 metadata filter.
- 4 câu filter theo `chapter` (2 dev, 2 test), chọn chủ đề có mặt ở **cả hai chương** để filter có tác dụng thật:

  | Câu | Chủ đề | Chương đúng | Chương gây nhiễu |
  |---|---|---|---|
  | q14 | Frankfurt School | 1 (critical theory) | 2 (critical sociology) |
  | q15 | Max Weber | 2 (value neutrality) | 1 (verstehen) |
  | t04 | Lương tối thiểu | 2 (Ehrenreich) | 1 (tranh luận chính sách) |
  | t05 | Qualitative | 1 | 2 |

- Câu hỏi không chứa tên chương hay số trang; giá trị filter coi là ngữ cảnh người dùng cung cấp trước khi truy xuất.
- Evidence: cả 20 `evidence_quote` đã được kiểm bằng script — có nguyên văn trên `gold_page`, cả trước và sau chuẩn hóa.
- Câu hỏi viết bằng tiếng Anh (cùng ngôn ngữ với sách).
- **Không được sửa 5 câu test sau khi đã xem kết quả.** Nếu lỡ sửa thì phải ghi rõ, không coi là holdout độc lập.
- **Phải khai trong báo cáo**: bộ câu hỏi soạn với hỗ trợ AI (Claude Code); cách kiểm tra = script đối chiếu evidence với text PDF + tự đọc lại từng câu.

## 4. Đọc và chuẩn hóa (`starter/src/ingestion.py`)

- `load_pdf`: đọc từng trang bằng pypdf 6.21.4; trang rỗng/lỗi vẫn giữ lại và gắn cờ. Kết quả: 40/40 trang có text, 0 rỗng, 0 lỗi.
- `normalize_text`:
  - NFKC (tách ký tự ghép `ﬁ` → `fi`).
  - Bỏ header/footer lặp lại (`8     1 • An Introduction to Sociology`, `Access for free at openstax.org`) và nhãn callout viết hoa (`SOCIOLOGY IN THE REAL WORLD`, `BIG PICTURE`...).
  - Nối từ có gạch nối bị xuống dòng (`single-\nparent` → `single-parent`).
  - Dựng lại đoạn văn bằng heuristic (pypdf **không** tách đoạn bằng dòng trống): dòng ngắn + kết thúc bằng dấu câu → hết đoạn; dòng ngắn không dấu câu → heading.
  - **Không** đổi dấu nháy cong để evidence vẫn khớp.
- `load_corpus`: chỉ đọc 40 trang trong manifest, gắn metadata `chapter`, `chapter_title`, `section` (theo heading `1.2 ...` có `LEARNING OBJECTIVES` ngay sau; phần mở đầu chương = `1.0`/`2.0`).

## 5. Chunking (`starter/src/chunking.py`)

| | A — `fixed_size` | B — `by_paragraph` |
|---|---|---|
| Tham số | 500 ký tự, overlap 50 | tối đa 800 ký tự |
| Cách cắt | cửa sổ ký tự, có thể cắt giữa chữ (cố ý, baseline) | gom đoạn văn; heading đi kèm đoạn sau; đoạn quá dài cắt theo câu |
| Số chunk | 286 | 217 |
| Độ dài | 59–500, TB 466.3 | 37–848, TB 556.6 |
| Evidence nằm trọn trong 1 chunk | 20/20 | 20/20 |

- Chunk ID ổn định: `{document_id}-p{page:03d}-{fixed|para}-{idx:03d}` → chạy lại ra đúng ID cũ (md5 file chunk giống hệt giữa 2 lần chạy).
- A–B khác **cả** cách cắt **lẫn** độ dài tối đa (500 vs 800) — đã chọn 800 để B giữ trọn đoạn; phải nói rõ khi so sánh A–B.

**Giới hạn đã biết (đưa vào báo cáo):**
- B có chunk tới 848 ký tự (> 800) vì heading (< 80 ký tự) được giữ chung với đoạn sau.
- Chunk **không vượt ranh giới trang** → có vài chunk B rất ngắn là mẩu câu bị cắt ở đầu/cuối trang (vd. `cultural value placed on appearance?”`). Đổi lại `page` luôn chính xác.
- **Bảng 1.1 (trang 30)** bị pypdf trích thành nhiều mảnh rời — chưa xử lý.
- `section` lấy theo vị trí đầu chunk: chunk bắt đầu ở phần mở đầu chương nhưng chứa heading 2.1 vẫn bị gắn `2.0`.

## 6. Embedding (`starter/src/embeddings.py`)

- Provider: **OpenRouter**, model **`qwen/qwen3-embedding-8b`**, endpoint `POST https://openrouter.ai/api/v1/embeddings`.
- Key để ở `starter/.env` (`OPENROUTER_API_KEY`) — file đã nằm trong `.gitignore`. Không commit, không dán key vào chat.
- Query có instruction, document không (theo model card Qwen3-Embedding):
  `Instruct: Given a question about an introductory sociology textbook, retrieve passages that answer the question\nQuery:{question}`
  → dùng giống nhau cho A/B/C (hằng `QUERY_INSTRUCTION`).
- Gửi theo lô 32; retry có backoff + jitter **chỉ** cho 408/429/5xx/lỗi mạng; lỗi khác (vd. 401 key sai) dừng ngay. **Không bao giờ** fallback sang vector giả.
- Kèm `provider.data_collection: "deny"` để yêu cầu provider không giữ dữ liệu.
- Giá: $0.01 / 1 triệu token (trang model OpenRouter).

## 7. Số chiều vector

### Đang dùng: 4096 chiều

- **4096 là số chiều mặc định (và tối đa)** của Qwen3-Embedding-8B.
- Model hỗ trợ **MRL** (Matryoshka Representation Learning): được huấn luyện sao cho **k chiều đầu tiên** của vector vẫn là một embedding dùng được, với k từ 32 đến 4096.
- Lý do giữ 4096:
  1. Trên OpenRouter, `supported_parameters` của model này **rỗng** → tham số `dimensions` của API có thể không được provider tôn trọng. Giữ mặc định là an toàn nhất, và code kiểm tra mỗi vector trả về đủ 4096 chiều.
  2. Corpus nhỏ (503 vector) → chi phí lưu trữ và tốc độ tìm kiếm không phải vấn đề.
  3. Bài lab yêu cầu giữ **cùng model + cùng số chiều** cho cả 3 cấu hình; chọn mức đầy đủ để không phải bàn về mất mát chất lượng do cắt chiều.
- Hệ quả với pgvector:
  - Kiểu `vector` lưu được tới 16.000 chiều → 4096 OK.
  - Index **HNSW/IVFFlat trên `vector` chỉ hỗ trợ tối đa 2000 chiều** (trên `halfvec` tối đa 4000) → **không tạo được index** cho 4096 chiều.
  - Vì vậy đang dùng **exact search** (quét toàn bộ, so cosine từng vector): kết quả đúng tuyệt đối, với 503 vector vẫn nhanh.
- Dung lượng: mỗi chiều là float4 (4 byte) → 4096 × 4 ≈ **16KB/vector**, 503 vector ≈ 8MB.

### Nếu giảm số chiều thì sao?

| Khía cạnh | Ảnh hưởng khi giảm (vd. 4096 → 1024) |
|---|---|
| Chất lượng truy xuất | Thường giảm nhẹ, vì vector mang ít thông tin hơn. Với model MRL mức giảm nhỏ hơn nhiều so với cắt bừa, nhưng **chưa đo trên corpus này** — không được khẳng định con số |
| Dung lượng lưu | Giảm tỷ lệ thuận: 1024 chiều ≈ 4KB/vector (giảm 4 lần) |
| Tốc độ tìm kiếm | Exact search nhanh hơn (ít phép nhân hơn) |
| Index | ≤ 2000 chiều → tạo được **HNSW** → tìm kiếm gần đúng (ANN), rất nhanh khi có hàng trăm nghìn vector; đổi lại có thể bỏ sót kết quả (recall < 100%), và filter kết hợp HNSW có thể trả ít hơn top-k |
| Chi phí API | **Không đổi** — tính theo token đầu vào, không theo số chiều đầu ra |

Cách làm nếu muốn giảm:
- **Cách 1 — nhờ API cắt**: gửi `dimensions: 1024`. Phải kiểm tra vector trả về có đúng 1024 chiều không, vì OpenRouter không cam kết hỗ trợ tham số này cho model.
- **Cách 2 — tự cắt phía mình** (dựa vào MRL): lấy 1024 phần tử đầu của vector 4096, rồi **chuẩn hóa lại độ dài về 1** (L2 normalize). Không cần gọi API lại cho document đã có.
- Dù cách nào, phải: áp dụng **giống hệt** cho vector document và vector query; tạo lại cột `vector(1024)` (bảng hiện tại là `vector(4096)`, code sẽ báo lỗi nếu lệch); nạp lại toàn bộ.
- Nếu làm thí nghiệm này: đây là **thí nghiệm thêm**, phải giữ nguyên số chiều giữa A/B/C, chọn trên dev, ghi rõ trong báo cáo — không được dùng tập test để chọn số chiều.

## 8. Lưu trữ (`starter/src/store.py`)

- PostgreSQL 16 + pgvector 0.8.7 (Docker, cổng `127.0.0.1:55433`).
- Bảng `chunks`, khóa chính `(strategy, chunk_id)`; cột `document_id, source, page, chapter, section, text, metadata (jsonb), content_hash, model, embedding vector(4096)`.
- Nạp lại không trùng: `INSERT ... ON CONFLICT DO UPDATE`; chunk cũ không còn trong lần build mới bị xóa trong **cùng transaction**.
- Chunk có text không đổi (so `content_hash`) → **không gọi embedding lại** → chạy lại tốn 0 token.
- Tìm kiếm: cosine distance `<=>`, `score = 1 - distance`, exact search.
- Filter chỉ nhận whitelist `chapter`, `section`, `document_id`; giá trị luôn truyền qua tham số SQL (đã thử giá trị kiểu SQL injection → trả `[]`).
- **Cấu hình C không lưu riêng**: dùng lại vector của B + filter lúc truy vấn → B–C khác đúng một yếu tố (filter).

## 9. Kết quả build index (đã chạy)

| | Chunk | Token | Chi phí (credit OpenRouter) | Thời gian embed |
|---|---:|---:|---:|---:|
| A | 286 | 26.539 | 0.000265 | 105 giây |
| B | 217 | 23.842 | 0.000238 | 39 giây |

- Chạy lần 2: 0 chunk embed lại, 0 token, DB vẫn A=286 / B=217, 0 khóa trùng.
- `cost_credits` là **credit OpenRouter**, không phải USD.
- Log mỗi lần chạy: `starter/results/index_runs.jsonl`.
- Câu thử "Max Weber ethical concern" (gold p65, chương 2): A top-1 đúng trang nhưng chunk bắt đầu giữa chữ; B top-1 đúng đoạn, hạng 2–3 là Weber chương 1; C (filter chương 2) loại được chunk chương 1. **Chỉ là 1 câu, chưa phải kết quả benchmark.**

## 10. Tiêu chí chọn cấu hình — chốt 2026-11-13, TRƯỚC khi chạy test

1. Evidence Hit@3 trên **dev** cao nhất.
2. Bằng nhau → Hit@1 trên dev cao hơn.
3. Vẫn bằng → ít chunk hơn / chi phí thấp hơn.

Tập test chỉ chạy **sau** khi đã chọn cấu hình theo tiêu chí trên (`run.py` bắt buộc cờ `--split test --confirm-test`). Đã ghi cùng nội dung vào cột `notes` của `artifacts/experiment_log.csv`.

**Mẫu chấm coherence** (chọn trước khi có điểm, không phụ thuộc benchmark): 10 trang cách đều 4 trang — 19, 23, 27, 31, 35, 49, 53, 57, 61, 65; mỗi trang lấy chunk chứa **điểm giữa** text đã chuẩn hóa, chấm cho A và B (C dùng chung chunk với B nên coherence giống B).

### Kết quả dev (`python -m src.run`, 15 câu, chạy 2026-11-13)

| Config | Hit@1 | Evidence Hit@3 | Filter compliance | Chunks |
|---|---|---|---|---|
| A | 13/15 | 15/15 | 0/2 | 286 |
| B | 14/15 | 15/15 | 0/2 | 217 |
| C | 14/15 | 15/15 | 2/2 | 217 |

- Câu trượt Hit@1 (đều có hit ở hạng 2):
  - **q05** (A, B, C): top-1 là chunk trang 24 về Sieyès/Comte — cùng chủ đề "nguồn gốc thuật ngữ sociology" nhưng không phải câu về sách của Spencer (trang 25).
  - **q15** (chỉ A): top-1 đúng trang 65 nhưng chunk cố định bị cắt nên không chứa trọn evidence; chunk chứa evidence đứng hạng 2 → ví dụ lỗi do cắt cứng.
- Filter: q14/q15 không filter (A, B) thì top-3 lẫn chunk chương khác (Critical Sociology ch2, Weber ch1); C loại được hết.
- **Hit@3 = 15/15 ở cả ba cấu hình → benchmark dev bị "trần"**, không phân biệt được cấu hình bằng Hit@3. Phải nói rõ trong báo cáo (corpus nhỏ, câu hỏi bám sát câu văn gốc).
- **Theo tiêu chí ở trên, B và C hòa nhau** (Hit@3, Hit@1, số chunk, chi phí đều bằng).
- **Bậc 4 bổ sung (chốt 2026-11-13, sau khi xem dev, TRƯỚC khi chạy test):** hòa ở 3 bậc trên → chọn cấu hình có filter compliance trên dev cao hơn. Lý do: B và C chỉ khác đúng ở filter. → **Chọn C** (2/2 so với 0/2). Phải ghi trong báo cáo rằng bậc 4 được thêm sau khi xem kết quả dev.

### Kết quả test (`python -m src.run --split test --confirm-test`, 5 câu, chạy 2026-11-13 sau khi đã chọn C)

| Config | Hit@1 | Evidence Hit@3 | Filter compliance | Câu trượt Hit@3 |
|---|---|---|---|---|
| A | 2/5 | 4/5 | 0/2 | t04 |
| B | 2/5 | 4/5 | 2/2 | t01 |
| C (đã chọn) | 2/5 | 4/5 | 2/2 | t01 |

- Test thấp hơn dev nhiều (Hit@1 40% so với 87–93%). **Không chỉnh gì theo test** — ghi nguyên.
- Kiểu lỗi chung: top-1 **đúng trang gold** nhưng là chunk **bên cạnh**, không chứa nguyên văn evidence; evidence thường đứng hạng 2–3.
- **t01** (B, C trượt; A trúng hạng 1): chunk B chứa câu "case studies are useful when the single case is unique" không vào top-3; top-1 là chunk liệt kê ví dụ case study cùng trang 62. A trúng nhờ chunk cố định gom đúng đoạn chuyển ý.
- **t04** (A trượt; B, C trúng hạng 1): A không filter nên hạng 2 lẫn chunk chương 1 về lương tối thiểu (p27); chunk A trên trang 59 bị cắt mất câu nêu tên Ehrenreich. B dù không filter vẫn trả top-3 toàn chương 2 → filter không phải yếu tố quyết định ở câu này.
- **t03** (C, hạng 1): top-1 là chú thích FIGURE 1.9 "The research of Kenneth and Mamie Clark helped the Supreme Court decide..." — **trả lời đúng câu hỏi** nhưng không chứa nguyên văn evidence → bị tính miss Hit@1. Ứng viên `manual_override` (GUIDE cho phép người chấm xác nhận bằng chứng tương đương) — phải tự quyết và ghi lý do.
- Kết luận chọn C dựa trên dev; trên test B và C bằng nhau về Hit@1/Hit@3, khác biệt filter chỉ thấy ở compliance (và B cũng đạt 2/2 trên test). Mẫu test 5 câu quá nhỏ để khẳng định cấu hình nào tốt hơn.

### Chấm tay 

| Strategy | Coherence TB /2 (n) | Metadata đủ và đúng | Filter compliance (test) | Grounding 0/1/2 | Grounding TB /2 |
|---|---|---|---|---|---|
| A | 1.0 (10) | 15/15 | 0/2 | 0 / 1 / 4 | 1.8 |
| B | 1.8 (10) | 15/15 | 2/2 | 1 / 0 / 4 | 1.6 |
| C | = B (dùng chung chunk) | 15/15 | 2/2 | 1 / 0 / 4 | 1.6 |

- File `starter/results/audit_*.csv` không ghi người chấm; việc nhãn ban đầu do LLM chấm được ghi trong báo cáo (mục "Kết quả" và "Sử dụng AI").
- Cách chấm:
  - Coherence: đọc toàn văn chunk, theo thang 0–2 của GUIDE.
  - Grounding: đọc cả top-3, theo thang 0–2 của GUIDE; không dựa vào `auto_hit@3`.
  - Metadata: đối chiếu độc lập với text thô của PDF (3 đoạn trích có trên đúng trang, trang thuộc khoảng trang của chương, mục xác định từ heading trong text thô) — **không** dùng lại code pipeline.
- Nhận xét: A coherence 1.0 vì mọi chunk đều cắt giữa từ/câu. B có 2 chunk được 1 điểm (pos03: câu đuôi của hộp + heading + chú thích; pos07: heading "Surveys" dính vào cuối đoạn trước — lỗi dựng đoạn).
- Grounding A cao hơn B/C trên test chỉ vì **t01** (A 2 điểm, B/C 0 điểm) — 1 câu, mẫu 5 câu → không kết luận A tốt hơn.
- Metadata 45/45 đúng nhưng mẫu chỉ gồm các trang không có lỗi `section` đã biết (chunk bắt đầu ở phần mở đầu chương) → nói rõ giới hạn này.
- **Bắt buộc trước khi nộp**: tự đọc lại và sửa nhãn nếu không đồng ý. Báo cáo phải ghi: nhãn ban đầu do LLM chấm, học viên đã duyệt lại, người chấm là tác giả → có nguy cơ thiên lệch.

## 11. Lệnh chạy (từ thư mục `starter/`)

```bash
source .venv/bin/activate
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py        # kiểm tra DB + pgvector
python scripts/export_chunks.py      # xuất chunk A/B + results/ingestion_log.json + kiểm evidence
python scripts/build_index.py        # embed + upsert A/B, chạy thử 1 câu
python -m src.run                    # benchmark dev: traces/summary/run_meta + audit_coherence.csv
python -m src.run --split test --confirm-test   # CHỈ sau khi chốt cấu hình trên dev
```

## 12. Việc còn lại

- [x] `evaluation.py` + `run.py`: chạy dev 15 câu × A/B/C, lưu trace top-3.
- [x] Chốt phân xử hòa (bậc 4 → C), chạy test; số liệu đã điền vào `artifacts/experiment_log.csv` (cột `hypothesis` vẫn để trống — tự viết).
- [ ] Quyết định `manual_override` cho t03 (và các ca tương tự) — ghi lý do.
- [ ] **Tự duyệt lại** 3 file `starter/results/audit_*.csv`, sửa nhãn nếu cần.
- [ ] Đọc, sửa và đổi tên bản nháp báo cáo `report/individual/DRAFT_MSSV_HoTen.md` → `<MSSV>_<HoTen>.md`; điền các chỗ `<...>`.
- [ ] Điền `STUDENT.md`, `artifacts/experiment_log.csv`, báo cáo `report/individual/<MSSV>_<HoTen>.md`, README cách chạy.
- [ ] Cập nhật `char_count` trong manifest; quyết định `.gitignore` cho PDF.
- [ ] Commit (đang ở nhánh `feat/ingestion-chunking`, chưa commit gì).
