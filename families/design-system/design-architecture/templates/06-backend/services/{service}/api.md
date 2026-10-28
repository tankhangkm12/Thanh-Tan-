# API của service

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mỗi API một heading cấp 3 `### API-xxx: <phương thức đường dẫn>`: `API-xx` được định nghĩa ở heading đó, chỉ ở đây hoặc ở `06-backend/contracts/`. Frontend và luồng nhắc API bằng ID, không bằng đường dẫn thô. Schema đầy đủ có thể nằm ở `06-backend/contracts/` và được link tới. Không đặt `FR-` ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Danh sách API
<!-- required -->

| API | Mô tả | Yêu cầu (FR) | Xác thực |
| --- | --- | --- | --- |
| API-xxx | <việc API làm> | <FR-xx> | <vai trò được gọi> |

## Chi tiết từng API
<!-- required -->

### API-xxx: <phương thức đường dẫn>

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Yêu cầu vào | <trường, kiểu, bắt buộc hay không, giới hạn kích thước (byte)> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Phản hồi thành công | <mã, trường> | |
| Lỗi | <mã, điều kiện, thông điệp theo error model của cross-cutting.md> | |
| Idempotency | <khóa, thời gian giữ (giây)> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Giới hạn tần suất | <số request / giây / người dùng> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

Chỉ số mục tiêu của API, bằng số và đơn vị, truy về NFR (Q2).

| API | Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- | --- |
| <API-xx> | <p95 độ trễ> | <ví dụ: < 200 ms> | <NFR-xx> | <công cụ, vị trí đo> |

## Được dùng bởi
<!-- required -->

Link tới mọi file nhắc một API của file này (frontend, luồng, service gọi); thiếu link là lỗi `missing-backlink`.

- <[tên file](đường-dẫn-tương-đối.md)>
