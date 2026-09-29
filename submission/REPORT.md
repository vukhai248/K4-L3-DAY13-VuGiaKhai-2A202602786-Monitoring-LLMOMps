# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Vũ Gia Khải
- **MSSV:** 2A202602786
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/vukhai248/K4-L3-DAY13-VuGiaKhai-2A202602786-onitoring-LLMOMps
- **Commit SHA cuối:** 1e5a8f3
- **Challenge ID:** day13-k4-l3a-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602786`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Baseline load test (CP0) | `evidence/00-baseline-load-test.txt` |
| Baseline log validator (CP0) | `evidence/00-baseline-validate-logs.txt` |
| Baseline dashboard validator (CP0) | `evidence/00-baseline-validate-dashboard.txt` |
| Baseline pytest (CP0) | `evidence/00-baseline-pytest.txt` |
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

Baseline đo trên starter tại commit `13b6066`, trước khi sửa TODO (xem `evidence/00-baseline-*.txt`).

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Đạt tuyệt đối: đủ required fields, context enrichment, correlation ID và 0 PII leak |
| `validate_dashboard.py` | HỢP LỆ 6/6 | HỢP LỆ 6/6 | `config/dashboard.yaml` đạt đầy đủ contract 6 panel (latency, traffic, errors, cost, tokens, quality) |
| `pytest` | 22 passed | 45 passed | Toàn bộ 45 unit tests và integration tests đều pass 100% |
| Số traces hợp lệ | 0 | 32 | Sinh traffic và chạy challenge workload ghi nhận 32 unique correlation IDs trong structured logs |
| Số PII leak | 0 | 0 | Scrubber hoạt động trước pipeline render JSON; regex che sạch email, phone, cccd, thẻ |
| Latency P95 / TTFT P95 | 450ms / 50ms | 441.8ms / 50ms | Độ trễ thông thường ổn định, TTFT đạt mức 50ms |
| Retrieval success rate | 100% | 100% | Toàn bộ các request thông thường đều truy xuất tài liệu thành công |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  - Tại `CorrelationIdMiddleware` (`app/middleware.py`), trước khi chuyển request sang handler, gọi `clear_contextvars()` để dọn context cũ nhằm loại trừ nguy cơ rò rỉ ID giữa các request.
  - Middleware kiểm tra header `x-request-id`: nếu client gửi đúng định dạng regex `^req-[0-9a-f]{8}$` thì chấp nhận sử dụng; nếu không có hoặc chuỗi chứa ký tự tùy ý (tránh bị tiêm mã độc/PII), middleware tự động sinh ID hợp lệ bằng `f"req-{uuid.uuid4().hex[:8]}"`.
  - ID được bind vào structlog qua `bind_contextvars(correlation_id=correlation_id)` và lưu vào `request.state.correlation_id`.
  - Khi hoàn thành xử lý, middleware gắn correlation ID và thời gian xử lý vào response headers: `x-request-id` và `x-response-time-ms`. Khối `finally` đảm bảo `clear_contextvars()` được gọi lại.
- **Các metadata được ghi vào structured log:**
  - Định dạng JSON structured logs (`data/logs.jsonl`) bao gồm: `ts` (ISO UTC), `level`, `service="api"`, `event` (`request_received`, `response_sent`, `request_failed`), `correlation_id`.
  - Metadata context được bind từ đầu request tại `main.py`: `user_id_hash` (chuỗi sha256 an toàn), `session_id`, `feature`, `model`, `env`.
  - Dòng kết quả `response_sent` bổ sung các trường số liệu quan sát: `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success` và `answer_preview` đã scrub PII.
- **Cách bảo đảm PII được scrub trước khi ghi:**
  - Đăng ký processor `scrub_event` trong `configure_logging()` của structlog. Processor này chạy trước `JsonlFileProcessor` và `JSONRenderer`.
  - Mọi trường dữ liệu kiểu chuỗi hoặc cấu trúc lồng nhau (dict, list) đều được duyệt đệ quy qua `_scrub_value` và áp dụng bộ mẫu regex trong `app/pii.py` (email, phone VN, CCCD 12 số, thẻ tín dụng 16 số, hộ chiếu, địa chỉ VN) để thay thế bằng thẻ `[REDACTED_<NAME>]`.
  - Tiền tố `u` trong hàm `hash_user_id(user_id)` ngăn ngừa việc chuỗi hash ngẫu nhiên chứa toàn chữ số bị hiểu nhầm là số CCCD.
- **Cách kiểm chứng kết quả:**
  - Chạy `tests/test_pii.py` (kiểm thử 11 trường hợp che PII).
  - Chạy `tests/test_correlation_id.py` (kiểm thử định dạng header, chống leak context).
  - Chạy `python scripts/validate_logs.py` kiểm tra toàn bộ file log: Đạt **100/100 điểm**, 0 trường hợp leak PII.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  - Cấu hình project riêng `day13-k4-l3a-2A202602786` trên Langfuse Cloud.
  - Sử dụng API Key riêng của project trong `.env`, gắn tags gồm `["lab", feature, self.model]` và môi trường `dev`.
  - Metadata của trace chứa `correlation_id` khớp từng ký tự với correlation ID được ghi trong `data/logs.jsonl`.
- **Cấu trúc root/retrieval/generation observations:**
  - **Root observation:** Hàm `LabAgent.run` được bao bọc bởi `@observe(name="lab-agent-run", as_type="agent")` ghi nhận tổng quan request và thời gian chạy toàn bộ agent.
  - **Child observation 1 (retrieval):** Phương thức `self._retrieve` được gắn `@observe(name="retrieval", as_type="retriever")` đo thời gian truy xuất tài liệu vector store, ghi nhận metadata `doc_count`.
  - **Child observation 2 (generation):** Phương thức `self._generate` được gắn `@observe(name="generation", as_type="generation")` đo thời gian gọi mô hình ngôn ngữ `FakeLLM`, ghi nhận model name, prompt text, token usage (`input_tokens`, `output_tokens`, `total`), ước lượng chi phí `cost_usd` và `ttft_ms`.
- **Cách nối trace với log:**
  - Middleware sinh `correlation_id` dạng `req-<8-hex>`.
  - Trong `agent.py`, `correlation_id` được truyền vào `propagate_attributes(metadata={"correlation_id": correlation_id})`. Nhờ đó, khi tìm thấy `correlation_id` trong log, ta có thể tra cứu ngay trace tương ứng trên giao diện Langfuse.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1 mang labels `baseline` và `production`.
- **Version/label candidate:** Version 2 mang label `candidate` với điều chỉnh yêu cầu câu trả lời ngắn gọn và cấu trúc hóa hơn.
- **Trace ID của mỗi version:**
  - Baseline (v1): `req-5538734a`, `req-e64e7721`
  - Candidate (v2): `req-ddd698b3`, `req-de10062c`
- **Cách promote và rollback `production`:**
  - Trên Langfuse Project Settings/Prompts, chọn prompt `day13-chat`, gán nhãn `production` sang v2 sau khi chạy đánh giá thành công trên môi trường staging.
  - Khi phát hiện v2 có dấu hiệu tăng độ trễ hoặc token cost, thực hiện rollback tức thì bằng cách chuyển nhãn `production` trỏ lại về v1 trực tiếp trên giao diện mà không cần build hay redeploy ứng dụng.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  - Được định nghĩa chuẩn xác trong `config/dashboard.yaml` dựa trên nguồn log chuẩn `data/logs.jsonl`:
    1. **Latency & TTFT:** Đo P50, P95, P99 của `latency_ms` và P95 của `ttft_ms`. Ngưỡng: P95 <= 3000ms.
    2. **Traffic:** Thống kê số lượng request theo phút (`rate_per_minute >= 1`).
    3. **Errors & Retrieval:** Tỷ lệ lỗi API (`error_rate_pct <= 2%`), phân loại `error_type` và tỷ lệ `tool_success_rate_pct >= 90%`.
    4. **Cost:** Chi phí theo phút và tổng chi phí trong ngày (`total <= $2.5`).
    5. **Tokens:** Tổng số token đầu vào và đầu ra (`tokens <= 50,000`).
    6. **Quality proxy:** Điểm chất lượng trung bình dựa trên heuristic (`mean >= 0.75`).
- **SLO và lý do chọn:**
  - Primary SLO: `fast_successful_requests` với mục tiêu **99.5%** trong chu kỳ 28 ngày.
  - SLI: Tỷ lệ các sự kiện `response_sent` có `latency_ms <= 3000` trên tổng số sự kiện `request_received`.
  - Lý do: Đối với ứng dụng hội thoại LLM, độ trễ trên 3 giây làm ngắt quãng sự tập trung của người dùng; baseline thông thường đạt P95 ~450ms, do đó ngưỡng 3000ms là phù hợp để phát hiện sớm các sự cố nghẽn mạng hoặc chậm truy xuất.
- **Cách tính error budget:**
  - Error budget = 100% - 99.5% = **0.5%**.
  - Với 10,000 requests, hệ thống được phép có tối đa 50 requests bị lỗi hoặc phản hồi vượt quá 3000ms trong chu kỳ đánh giá.
- **Ba alert và runbook tương ứng:**
  1. `high_p95_latency`: Severity `warning`, điều kiện `p95(latency_ms) > 3000ms` duy trì trong 5 phút. Runbook tại `docs/alerts.md#alert-1`.
  2. `high_error_rate`: Severity `critical`, điều kiện `error_rate_pct > 2%` duy trì trong 5 phút. Runbook tại `docs/alerts.md#alert-2`.
  3. `low_retrieval_success_rate`: Severity `warning`, điều kiện `retrieval_success_rate_pct < 90%` duy trì trong 5 phút. Runbook tại `docs/alerts.md#alert-3`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 2026-09-29T09:22:20Z đến 2026-09-29T09:22:45Z
- **Triệu chứng từ metrics:**
  - Panel **Latency percentiles and TTFT** ghi nhận độ trễ P95 tăng vọt từ mức thông thường (~440ms) lên **3499ms – 15240ms**, vượt xa ngưỡng quy định `latency_threshold_ms: 2000` của challenge và ngưỡng vi phạm SLO 3000ms.
  - Panel **TTFT** duy trì ổn định ở mức 50ms, chứng tỏ không có sự suy giảm hiệu năng tại tầng suy luận của LLM (`FakeLLM.generate`) mà sự cố xảy ra trước khi bắt đầu sinh token đầu tiên.
  - Panel **Errors** không có request nào bị HTTP 5xx hay `request_failed`, cho thấy hệ thống không bị crash mà chỉ bị nghẽn độ trễ.
- **Log line và correlation ID liên quan:**
  - Correlation ID đại diện: `req-12595250`
  - Dòng log trích xuất từ `data/logs.jsonl`:
    ```json
    {"service": "api", "latency_ms": 3499, "ttft_ms": 50, "tokens_in": 36, "tokens_out": 130, "cost_usd": 0.002058, "quality_score": 0.9, "tool_name": "retrieval", "tool_success": true, "payload": {"answer_preview": "Starter answer. You should improve this output logic and add better quality chec..."}, "event": "response_sent", "model": "claude-sonnet-4-5", "user_id_hash": "u4570299f37e2", "session_id": "k4-l3a-challenge-s04", "env": "dev", "feature": "monitoring", "correlation_id": "req-12595250", "level": "info", "ts": "2026-09-29T09:22:29.474864Z"}
    ```
- **Trace ID và span gây ảnh hưởng:**
  - Trace tương ứng với `correlation_id: req-12595250`.
  - Cây trace quan sát trong request:
    - Root span `lab-agent-run`: tổng thời gian 3499ms.
    - Child span `retrieval` (loại `retriever`): tiêu tốn tới **3350ms** (chiếm ~96% tổng thời gian request).
    - Child span `generation` (loại `generation`): chỉ tốn **150ms** với `ttft_ms = 50ms`.
  - Span gây ảnh hưởng chính và là nguyên nhân gây chậm là span `retrieval`.
- **Root cause:**
  - Sự cố tắc nghẽn I/O tại khâu truy xuất dữ liệu vector store (`rag_slow` thêm 2.5s độ trễ trong hàm `retrieve()`), khiến toàn bộ tiến trình của agent bị chặn kéo dài trước khi chuyển prompt sang mô hình ngôn ngữ.
- **Fix action:**
  - Đặt timeout tối đa (ví dụ 1000ms) cho phương thức `retrieve()`. Nếu hết thời gian mà chưa nhận được kết quả, tự động fallback sử dụng ngữ cảnh mặc định đã cache trong RAM thay vì chặn toàn bộ luồng xử lý.
  - Xây dựng cache phân tán (như Redis) hoặc in-memory cache cho các embedding vector và kết quả câu hỏi thường gặp để giảm tải trực tiếp lên vector database.
- **Preventive measure:**
  - Kích hoạt alert cảnh báo sớm `high_p95_latency` và `low_retrieval_success_rate` đẩy thông báo về kênh Slack `#alerts-llmops`.
  - Giám sát độ trễ riêng biệt cho từng span qua distributed tracing, đặt SLO nội bộ cho thành phần retrieval là P95 < 500ms.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  - Thiết kế `CorrelationIdMiddleware` tự động sinh mã mới nếu header `x-request-id` của client không tuân thủ mẫu regex `req-<8-hex>`. Quyết định này giúp bảo vệ hệ thống khỏi các cuộc tấn công injection hoặc việc người dùng vô tình truyền PII trong HTTP header.
  - Thêm tiền tố `u` cho hàm `hash_user_id` để ngăn ngừa xác suất ngẫu nhiên sinh ra chuỗi 12 chữ số thuần túy bị validator nhận diện nhầm thành số CCCD Việt Nam.
  - Dùng `@observe` decorator chuẩn Langfuse v4 tạo child observation cho `retrieval` và `generation` giúp trace waterfall phân tách rõ ràng thời gian từng thành phần.
- **Một lỗi/blocker đã gặp:**
  - Khi gửi batch span tới Langfuse Cloud, kết nối gặp mã lỗi `401 Unauthorized` hoặc gián đoạn mạng timeout.
- **Cách tìm nguyên nhân và xử lý:**
  - Đọc log lỗi chi tiết từ OpenTelemetry exporter; kiểm tra thấy việc thiếu hoặc sai key không được làm sập ứng dụng API.
  - Xử lý: Thiết kế lớp bọc `tracing.py` và `prompt_management.py` theo nguyên tắc Defensive Coding, bắt ngoại lệ và tự động chuyển sang chế độ fallback an toàn trong bộ nhớ (`local-v1`), đảm bảo API luôn phản hồi 200 OK cho người dùng cuối.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics:** Cho biết **khi nào** hệ thống có vấn đề và **loại triệu chứng** là gì (ví dụ: P95 latency tăng vượt 3000ms lúc 09:22).
  - **Logs:** Thu hẹp phạm vi để xác định **request cụ thể nào** bị ảnh hưởng (dựa vào `correlation_id` của request có `latency_ms` cao bất thường).
  - **Traces:** Cung cấp góc nhìn chi tiết nhất về **bước/span nào** bên trong request là nguyên nhân gốc rễ (ví dụ: span `retrieval` tốn 3.35s trong khi span `generation` chỉ tốn 0.15s).
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - Prompt là một phần của mã nguồn logic trong hệ thống AI; việc versioning prompt trên Langfuse giúp truy vết chính xác chất lượng đầu ra gắn liền với phiên bản prompt nào.
  - Theo dõi token và cost giúp ngăn chặn hiện tượng bùng nổ chi phí (cost spike) do prompt injection hoặc lặp vô tận.
  - Khả năng rollback nhãn `production` về phiên bản cũ là chốt chặn an toàn sống còn để khắc phục sự cố ngay lập tức mà không cần quy trình redeploy hạ tầng phức tạp.
- **Điều quan trọng nhất đã học:**
  - Xây dựng hệ thống quan sát toàn diện (Observability) là nền tảng cốt lõi để vận hành dịch vụ AI đáng tin cậy. Nếu không có correlation ID và child spans, một request AI gặp sự cố sẽ hoàn toàn là một "hộp đen" không thể debug.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  - Các thử nghiệm được chạy trên workload thực tế và challenge chính thức của lớp K4-L3A. Hệ thống hoạt động ổn định và đáp ứng 100% các tiêu chí đánh giá của bài lab.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo cá nhân và commit SHA cuối đã được nộp trên LMS/Codelabs.

