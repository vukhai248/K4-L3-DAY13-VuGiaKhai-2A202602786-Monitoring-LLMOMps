# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: High P95 Latency (`high_p95_latency`)
- Severity: warning
- Duration: 5m
- Kênh thông báo: Slack (#alerts-llmops)
- SLI/SLO liên quan: Primary SLO `fast_successful_requests` (ngưỡng latency_ms <= 3000ms)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng phải chờ quá 3 giây để nhận phản hồi, gây đứt quãng trải nghiệm hỏi đáp
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency & TTFT trên Dashboard xem độ trễ tăng ở TTFT (LLM generation) hay trước TTFT (retrieval/processing).
  2. Lọc file `data/logs.jsonl` tìm các event `response_sent` có `latency_ms > 3000` trong 5 phút qua và lấy `correlation_id`.
  3. Mở trace tương ứng trên Langfuse theo `correlation_id` để xác định span chậm nhất (`retrieval` hay `generation`).
- Mitigation tạm thời:
  - Nếu span `retrieval` chậm: kiểm tra tải của vector store, tạm thời giảm số lượng document cần fetch hoặc bật local cache.
  - Nếu span `generation` chậm: kiểm tra độ dài input/output token hoặc chuyển bớt traffic sang fallback model.
- Owner: oncall-llmops

## Alert 2

- Tên: High API Error Rate (`high_error_rate`)
- Severity: critical
- Duration: 5m
- Kênh thông báo: Slack (#alerts-critical-llmops)
- SLI/SLO liên quan: Guardrail `error_rate_pct_max: 2` (tỷ lệ lỗi tối đa không quá 2%)
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Tỷ lệ request thất bại cao, người dùng nhận thông báo lỗi hệ thống và không nhận được câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Errors trên Dashboard để phân loại lỗi theo `error_type` và HTTP status code.
  2. Tìm các dòng `event == "request_failed"` trong `data/logs.jsonl` để lấy exception traceback và `correlation_id`.
  3. Mở trace trên Langfuse để xem bước nào gây crash (middleware, retrieval hay LLM call).
- Mitigation tạm thời:
  - Bật circuit breaker đối với dependency bên ngoài đang gặp sự cố.
  - Rollback bản release hoặc prompt version mới nhất nếu sự cố phát sinh ngay sau đợt cập nhật.
  - Restart dịch vụ API pod/instance nếu phát hiện rò rỉ tài nguyên.
- Owner: oncall-llmops

## Alert 3

- Tên: Low Retrieval Success Rate (`low_retrieval_success_rate`)
- Severity: warning
- Duration: 5m
- Kênh thông báo: Slack (#alerts-llmops)
- SLI/SLO liên quan: Guardrail `retrieval_success_rate_pct_min: 90` (tỷ lệ retrieval thành công tối thiểu 90%)
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90%` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Mô hình thiếu ngữ cảnh chính xác, câu trả lời có nguy cơ bị hallucination hoặc rơi về fallback chung
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Errors trên Dashboard xem tỷ lệ `tool_success` của tool `retrieval`.
  2. Tìm log trong `data/logs.jsonl` có `tool_name == "retrieval"` và `tool_success == false` để xác định mã lỗi vector store.
  3. Mở trace trên Langfuse kiểm tra span `retrieval` xem có bị lỗi timeout, connection refused hoặc bad query không.
- Mitigation tạm thời:
  - Chuyển sang sử dụng fallback corpus lưu sẵn trong bộ nhớ để bảo đảm trả lời tạm thời cho người dùng.
  - Kiểm tra kết nối mạng và tài nguyên của dịch vụ vector store; scale up cụm vector search nếu quá tải.
- Owner: oncall-llmops
