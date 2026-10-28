# Xong khi: 04-flows

Gate: G6. Trọng tâm: Q1, Q6, Q8. Luồng được duyệt trước khi thiết kế chi tiết (G7), nên ID của `06-backend/` và `07-data/` có thể chưa định nghĩa ở gate này.

## flow-index.md

- [ ] Mỗi file `FL-*.md` có một dòng trong "Danh sách luồng", link đúng file; tần suất là số có đơn vị và trỏ giả định `A-xx`.
- [ ] Mục "Yêu cầu chưa có luồng" rỗng (ghi "không có FR nào thiếu luồng") hoặc mỗi FR còn thiếu có lý do; gate không qua nếu còn FR thiếu luồng.

## FL-xxx-{tên}.md (mỗi luồng)

- [ ] `FL-…` định nghĩa ở heading; tên file bắt đầu bằng đúng ID đó.
- [ ] Mục "Yêu cầu liên quan" nhắc FR bằng ID (mỗi luồng ít nhất một FR; mỗi FR của BA có luồng — `check_trace.py` báo `fr-without-flow`) (Q1).
- [ ] Sơ đồ tuần tự nêu đúng thành phần tham gia bằng ID (`SVC-`, `API-`, `TBL-`, `BKT-`, `EVT-`), không có quyết định về giao diện (Q7).
- [ ] "Lỗi và xử lý" có dòng cho mỗi bước có thể hỏng; thử lại và thời gian chờ là số có đơn vị.
- [ ] "Dữ liệu chạm tới" liệt kê mọi bảng, bucket, event trong sơ đồ bằng ID; từ G7 mỗi ID có ở `07-data/` (`check_trace.py` báo `data-ref-missing`).
- [ ] "Tối ưu" có chỉ số bằng số, đơn vị và NFR (Q2); không từ mơ hồ thiếu số.
- [ ] "Rủi ro" liệt kê `R-xx` hoặc nói rõ không có rủi ro mới (Q6).
- [ ] Không định nghĩa `FR-`, `TBL-`, `SVC-`… ở ô đầu dòng bảng của file luồng.

## Chung cho cả phần

- [ ] Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" với ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần không đạt (`check_numbers.py`).
- [ ] `check_trace.py --gate G6`, `check_links.py`, `check_numbers.py`, `check_profile.py --gate G6 --templates …`, `check_workspace.py` sạch.
- [ ] Người dùng duyệt luồng (`G6: duyệt`) trước khi thiết kế chi tiết.
