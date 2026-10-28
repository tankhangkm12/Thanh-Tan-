# Hợp đồng (contracts)

> Template của design-architecture, mục lục của thư mục `06-backend/contracts/`. Thư mục chứa schema đầy đủ của API và event (OpenAPI, JSON Schema, Protobuf…). `API-xx` được định nghĩa ở heading trong `api.md` của service **hoặc** trong một file của thư mục này, không cả hai; file nào định nghĩa `API-xx` phải có mục "Được dùng bởi" link mọi file nhắc nó (`missing-backlink`). Mục có `<!-- required -->` là bắt buộc. File này chỉ liệt kê, không định nghĩa ID nào. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Danh sách hợp đồng
<!-- required -->

Ghi "chưa có file hợp đồng riêng" nếu mọi hợp đồng nằm ngay trong `api.md` của service.

| File | Định dạng | Phạm vi | Viết tay hay sinh | Phiên bản |
| --- | --- | --- | --- | --- |
| <[tên file](tên-file)> | <OpenAPI, JSON Schema, Protobuf> | <service hoặc nhóm API> | <viết tay, sinh từ mã> | <major.minor> |

## Chính sách phiên bản
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Cách đánh phiên bản | <trong đường dẫn, trong header, trong tên event> | |
| Thay đổi cho phép không đổi phiên bản | <thêm trường tùy chọn> | |
| Thay đổi phải tăng phiên bản chính (major) | <xóa trường, đổi nghĩa, đổi kiểu> | |
| Thời gian giữ phiên bản cũ | <số + đơn vị> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Kiểm tra hợp đồng
<!-- required -->

| Kiểm tra | Công cụ | Chạy khi nào | Khi lỗi |
| --- | --- | --- | --- |
| <phát hiện thay đổi phá vỡ, kiểm thử hợp đồng giữa bên gọi và bên được gọi> | <công cụ> | <mỗi pull request> | <chặn merge> |
