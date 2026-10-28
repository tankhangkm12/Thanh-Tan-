# Giao tiếp giữa các thành phần

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Quy tắc chung cho mọi service; ngoại lệ của một service ghi ở `dependencies.md` của service đó. Kênh bất đồng bộ định nghĩa ở [messaging.md](../07-data/messaging.md). File này chỉ nhắc ID, không đặt `API-`, `EVT-`… ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Khi nào đồng bộ, khi nào bất đồng bộ
<!-- required -->

| Tình huống | Kiểu | Lý do |
| --- | --- | --- |
| <ví dụ: cần kết quả ngay để trả lời người dùng> | <đồng bộ> | <NFR-xx hoặc C-xx> |
| <ví dụ: việc có thể chậm, không chặn người dùng> | <bất đồng bộ> | <NFR-xx hoặc C-xx> |

## Gateway và định tuyến
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Điểm vào từ client | <gateway, load balancer, gọi thẳng service> | |
| Việc gateway làm | <xác thực, giới hạn tần suất, định tuyến> | |
| Giới hạn kích thước request (KB) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Thời gian chờ và thử lại mặc định
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Thời gian chờ gọi đồng bộ giữa service (ms) | <số; nhỏ hơn thời gian chờ của bên gọi> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Số lần thử lại | <số, chỉ với thao tác idempotent> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Backoff | <cách tăng, jitter> | |
| Ngắt mạch (circuit breaker) | <ngưỡng lỗi (phần trăm), thời gian mở (giây)> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Hành vi khi bên được gọi hỏng | <hạ cấp, báo lỗi, xếp hàng> | |

## Bất đồng bộ
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Kênh | <link tới kênh trong messaging.md> | |
| Quy tắc đặt tên và phiên bản event | <cách đặt, khi nào tăng phiên bản> | |
| Xử lý event lỗi | <số lần thử, hàng đợi lỗi, theo messaging.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Phiên bản và tương thích
<!-- required -->

Cách đổi API, event mà không làm hỏng bên đang dùng; chi tiết hợp đồng ở [contracts/README.md](contracts/README.md).

- Quy tắc tương thích: <thêm trường được, xóa hay đổi nghĩa phải tăng phiên bản>
- Thời gian giữ phiên bản cũ: <số + đơn vị, cơ sở>

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <p95 độ trễ cộng thêm do gateway> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |
| <tỉ lệ request phải thử lại> | <phần trăm> | <NFR-xx> | <công cụ, vị trí đo> |
