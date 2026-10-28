# T-<xxx>: <tên task>

- **Gate:** <G0–G10>
- **Giao cho:** <Planner | Researcher | Designer | Reviewer>
- **Trạng thái:** <mở | đang làm | chờ soát | đóng>
- **Phụ thuộc:** <T-xxx, hoặc không có>
- **Tạo:** <YYYY-MM-DD>

## Mô tả

<Làm gì, vì sao, trong phạm vi nào. Một đoạn ngắn.>

## Đầu vào

<!-- Chỉ những file Orchestrator truyền cho agent; agent không đọc gì ngoài danh sách này. -->

- <đường dẫn file>

## Đầu ra

<!-- Chỉ những file agent được ghi (theo permissions.md). -->

- <đường dẫn file>

## Xong khi

<!-- Mỗi mục kiểm được: một lệnh script, hoặc một điều Reviewer xác nhận. Không dùng từ mơ hồ không kèm số. -->

- [ ] <điều kiện kiểm được 1>
- [ ] <điều kiện kiểm được 2>
- [ ] Script áp cho gate chạy sạch: <tên script>
- [ ] Reviewer soát đủ Q1–Q8, không còn lỗi chặn trong `reviews/`

## Ghi chú

<Phát sinh trong lúc làm. Rủi ro mới khai vào sổ rủi ro, ghi ID R-xx ở đây.>
