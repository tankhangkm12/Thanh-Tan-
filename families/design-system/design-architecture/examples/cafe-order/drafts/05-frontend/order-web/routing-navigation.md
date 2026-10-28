# Màn hình, route và API

## Bảng route
<!-- required -->

| Route | Màn hình (SCR) | Dữ liệu cần | API gọi | Vai trò được vào | Chiến lược render |
| --- | --- | --- | --- | --- | --- |
| `/orders/new` | SCR-order-form | giỏ (mã món, số lượng) và ghi chú | API-create-order | mọi người | CSR |
| `/orders/:id` | SCR-order-status | trạng thái đơn và các món; `:id` là mã tra cứu | API-get-order | khách giữ mã tra cứu | CSR |
| `/staff/orders/:id` | SCR-staff-update | đơn cần đổi và trạng thái mới | API-get-order, API-update-status | nhân viên | CSR |

## Điều hướng
<!-- required -->

| Quy tắc | Giá trị | Cơ sở |
| --- | --- | --- |
| Liên kết sâu (deep link) | mọi route mở được trực tiếp; route của nhân viên chưa có khóa thì hỏi khóa rồi quay lại route cũ | |
| Hành vi nút quay lại | giữ giỏ chưa gửi ở `/orders/new` | |
| Chặn route theo quyền | kiểm ở guard route, xem [auth-session.md](auth-session.md) | |
| Tải trước dữ liệu (prefetch) | không dùng | |

## Câu hỏi cho designer
<!-- required -->

Không có.

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian chuyển route (p95) | 200 ms | NFR-001 | bước đo hiệu năng trong CI, trên thiết bị chuẩn |
| kích thước gói mã tải thêm khi vào route | 60 KB | NFR-001 | báo cáo kích thước gói của Vite |
