# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

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

## Nguồn dữ liệu và giấy phép

Corpus của bài làm này trích từ sách giáo khoa mở của OpenStax:

| Mục | Thông tin |
|---|---|
| Tên sách | *Introduction to Sociology 3e* |
| Tác giả chính (Senior Contributing Authors) | Tonja R. Conerly (San Jacinto College, Texas Southern University & University of South Carolina); Kathleen Holmes (Northern Essex Community College); Asha Lal Tamang (Minneapolis Community and Technical College & North Hennepin Community College) |
| Nhà xuất bản | OpenStax, Rice University, 6100 Main Street MS-375, Houston, Texas 77005 |
| Bản quyền | ©2026 Rice University (theo trang bản quyền của file PDF đã tải) |
| Năm xuất bản lần đầu | 2021 |
| ISBN bản số | 978-1-951693-36-7 |
| Nguồn | https://openstax.org/details/books/introduction-sociology-3e (truy cập 2026-11-13) |
| Giấy phép | [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/) |

**Giấy phép cho phép:** chia sẻ, phối lại và phát triển tiếp nội dung sách **chỉ cho mục đích phi thương mại**, với điều kiện:

- **BY — Ghi công:** ghi rõ nguồn như bảng trên và dẫn link giấy phép.
- **NC — Phi thương mại:** không dùng cho mục đích thương mại. Bài lab này là bài tập học thuật, phi thương mại.
- **SA — Chia sẻ tương tự:** mọi bản phái sinh phải phát hành theo cùng giấy phép CC BY-NC-SA 4.0.



> **Access for free at openstax.org.**

> Textbook content produced by OpenStax is licensed under a Creative Commons Attribution Non-Commercial ShareAlike 4.0 International License (CC BY-NC-SA 4.0). Under this license, any user of this textbook or the textbook contents herein can share, remix, and build upon the content for noncommercial purposes only. Any adaptations must be shared under the same type of license. In any case of sharing the original or adapted material, whether in whole or in part, the user must provide proper attribution as follows: […] If you noncommercially redistribute part of this textbook, then you must retain in every digital format page view (including but not limited to PDF and HTML) and on every physical printed page the following attribution: “Access for free at openstax.org.” […] If you use this textbook as a bibliographic reference, please include https://openstax.org/details/books/introduction-sociology-3e in your citation.

**Phần đã dùng và các thay đổi:**

- Chỉ dùng chương 1 *An Introduction to Sociology* (trang PDF 19–37) và chương 2 *Sociological Research* (trang PDF 47–67), tổng 40 trang. Chi tiết trong [`data/manifest.json`](data/manifest.json).
- Thay đổi: trích text bằng pypdf, chuẩn hóa Unicode (NFKC), bỏ header/footer và nhãn hộp, dựng lại đoạn văn, chia chunk và tạo embedding. Nội dung câu chữ không bị sửa.

**Các file trong repo chứa nội dung sách** (bản gốc hoặc bản phái sinh) và do đó thuộc giấy phép **CC BY-NC-SA 4.0**:

- `data/introduction-sociology-3e_-_WEB.pdf`
- `starter/results/chunks_A.jsonl`, `starter/results/chunks_B.jsonl`
- `starter/results/traces_dev.jsonl`, `starter/results/traces_test.jsonl`
- `starter/results/audit_coherence.csv`, `starter/results/audit_metadata.csv`, `starter/results/audit_grounding.csv`
- `benchmark/questions.json` (trường `evidence_quote` trích nguyên văn)
- `demo/index.html` (nhúng trích đoạn chunk)

Mã nguồn của bài làm không phải bản phái sinh của sách và không chịu giấy phép này.
The source code of the assignment is not a derivative work of the book and is not subject to this license.

**Nhãn hiệu:** tên và logo OpenStax, OpenStax CNX, OpenStax Tutor, Connexions, Rice University, cùng ảnh bìa sách **không** thuộc phạm vi giấy phép trên và không được sao chép nếu chưa có sự đồng ý của Rice University.
**Trademark:** The names and logos of OpenStax, OpenStax CNX, OpenStax Tutor, Connexions, Rice University, and book cover images are not covered by the above license and may not be copied without Rice University's consent.

Câu hỏi về giấy phép: support@openstax.org.
License questions: support@openstax.org.