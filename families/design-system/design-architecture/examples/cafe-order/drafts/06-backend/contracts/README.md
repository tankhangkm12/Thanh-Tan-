# Hợp đồng (contracts)

## Danh sách hợp đồng
<!-- required -->

Chưa có file hợp đồng riêng: mọi hợp đồng nằm ngay trong [api.md](../services/order-service/api.md).

## Chính sách phiên bản
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Cách đánh phiên bản | trong đường dẫn (`/v1`) | |
| Thay đổi cho phép không đổi phiên bản | thêm trường tùy chọn | |
| Thay đổi phải tăng phiên bản chính | xóa trường, đổi nghĩa, đổi kiểu | |
| Thời gian giữ phiên bản cũ | 90 ngày, khớp [communication.md](../communication.md) | C-002 |

## Kiểm tra hợp đồng
<!-- required -->

| Kiểm tra | Công cụ | Chạy khi nào | Khi lỗi |
| --- | --- | --- | --- |
| kiểm thử hợp đồng giữa order-web và order-service | bộ test hợp đồng trong CI | mỗi pull request | chặn merge |
