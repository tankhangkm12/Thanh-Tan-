# Phụ thuộc của service

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Nhắc service, hệ thống ngoài bằng ID hoặc link; thời gian chờ và số lần thử lại là số có đơn vị. Không đặt ID ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Phụ thuộc đồng bộ
<!-- required -->

Service mà service này gọi trực tiếp. Không có thì ghi "không có".

| Gọi tới | API | Thời gian chờ (ms) | Thử lại (lần) | Cách xử lý khi hỏng | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| <SVC-xx> | <API-xx> | <số> | <số> | <ngắt mạch, giá trị mặc định, báo lỗi> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Phụ thuộc bất đồng bộ
<!-- required -->

Event hoặc hàng đợi qua [messaging](../../../07-data/messaging.md). Không có thì ghi "không có".

| Kênh | EVT | Hướng | Hậu quả khi kênh chậm hoặc mất |
| --- | --- | --- | --- |
| <tên> | <EVT-xx> | <phát, nhận> | <mô tả> |

## Hệ thống ngoài
<!-- required -->

Cách gọi, lỗi và phương án thay thế nằm ở [integrations.md](../../../01-system/integrations.md). Không có thì ghi "không có".

| Hệ thống | Giao thức | Thời gian chờ (ms) | Phương án dự phòng | Cơ sở |
| --- | --- | --- | --- | --- |
| <tên> | <REST, SDK…> | <số> | <phương án> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
