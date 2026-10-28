# Màn hình, route và API

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. File này nối kiến trúc với designer qua ID màn hình: `SCR-xx` lấy từ tài liệu của designer (`inputs/ui-design/`), file này **không định nghĩa** SCR và chỉ ghi route, dữ liệu cần, API gọi. API nhắc bằng `API-xx` (định nghĩa ở `06-backend/`), không ghi đường dẫn thô như `GET /orders`. Cột đầu của bảng là route, không phải ID. Điều kiến trúc cần designer làm thêm (ví dụ trạng thái khi mất mạng) ghi thành câu hỏi `CH-xxx` trong `questions.md`, không tự quyết phần nhìn. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Bảng route
<!-- required -->

| Route | Màn hình (SCR) | Dữ liệu cần | API gọi | Vai trò được vào | Chiến lược render |
| --- | --- | --- | --- | --- | --- |
| <đường dẫn route> | <SCR-xx> | <dữ liệu màn hình hiển thị, không phải cách hiển thị> | <API-xx, …> | <vai trò> | <CSR, SSR, SSG> |

## Điều hướng
<!-- required -->

| Quy tắc | Giá trị | Cơ sở |
| --- | --- | --- |
| Liên kết sâu (deep link) | <route nào mở được trực tiếp, xử lý khi chưa đăng nhập> | |
| Hành vi nút quay lại | <giữ trạng thái gì> | |
| Chặn route theo quyền | <nơi kiểm, link auth-session.md> | |
| Tải trước dữ liệu (prefetch) | <route nào, khi nào, giới hạn dữ liệu (KB)> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Câu hỏi cho designer
<!-- required -->

Điều kiến trúc cần designer quyết. Ghi "không có" nếu chưa có.

- <CH-xxx: điều cần hỏi, vì sao kiến trúc cần>

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <thời gian chuyển route (p95)> | <ví dụ: < 300 ms> | <NFR-xx> | <RUM, công cụ> |
| <kích thước gói mã tải khi vào route (KB)> | <số> | <NFR-xx> | <công cụ phân tích gói> |
