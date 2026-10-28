# Mạng, offline và đồng bộ

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Chỉ kỹ thuật: gọi API, thử lại, offline, đồng bộ. Cách trình bày trạng thái "mất mạng" là việc của designer; cần designer quyết thì ghi `CH-xxx` vào `questions.md` (Q7). API nhắc bằng `API-xx`; cột đầu của bảng không phải ID. Điều kiện mạng lấy từ [device-matrix.md](../device-matrix.md). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Gọi API
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Thời gian chờ mỗi request (ms) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Thử lại | <số lần, chỉ với API nào, backoff> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Khóa idempotency khi thử lại | <API-xx dùng khóa nào, theo `api.md`> | |
| Hủy request khi rời màn hình | <có, không> | |
| Xử lý lỗi | <theo error model của cross-cutting.md> | |

## Offline và đồng bộ
<!-- required -->

Mức hỗ trợ offline phải lấy từ NFR; không có NFR đòi thì ghi "không hỗ trợ offline" và lý do.

| Dữ liệu hoặc thao tác | Mức hỗ trợ | Lưu ở đâu | Dung lượng tối đa (MB) | Cách đồng bộ khi có mạng | Xử lý xung đột | Cơ sở |
| --- | --- | --- | --- | --- | --- | --- |
| <tên> | <chỉ đọc, ghi vào hàng đợi, đầy đủ> | <nơi lưu> | <số> | <hàng đợi, theo thứ tự, gộp> | <bản máy chủ thắng, hỏi người dùng> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <dữ liệu truyền mỗi phiên trên mạng chậm (KB)> | <số> | <NFR-xx> | <công cụ, vị trí đo> |
| <thời gian đồng bộ hàng đợi sau khi có mạng (p95)> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |
