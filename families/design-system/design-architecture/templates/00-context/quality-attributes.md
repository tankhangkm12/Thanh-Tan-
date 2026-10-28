# Thuộc tính chất lượng (NFR)

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Đây là nơi **định nghĩa** `NFR-xx` (ô đầu dòng bảng). Mỗi NFR có chỉ tiêu bằng số kèm đơn vị; từ như "nhanh", "lớn", "đủ dùng" không kèm số là lỗi chặn (Q4). Số đầu vào (DAU, tốc độ tăng…) là giả định `A-xx` trong [assumptions.md](assumptions.md), không viết lại ở đây.

## Yêu cầu phi chức năng
<!-- required -->

| ID | Thuộc tính | Chỉ tiêu (số + đơn vị) | Cách đo | Mốc | Nguồn |
| --- | --- | --- | --- | --- | --- |
| NFR-xxx | <hiệu năng, sẵn sàng, bảo mật, khả năng mở rộng…> | <ví dụ: p95 < 300 ms ở tải đỉnh> | <công cụ, vị trí đo> | <ra mắt, 1 năm…> | <BA, A-xx hoặc người dùng duyệt> |

## Sẵn sàng và phục hồi
<!-- required -->

| Chỉ số | Giá trị (số + đơn vị) | Nguồn |
| --- | --- | --- |
| Uptime mục tiêu | <phần trăm mỗi tháng> | <NFR-xx> |
| RPO | <phút hoặc giờ> | <NFR-xx> |
| RTO | <phút hoặc giờ> | <NFR-xx> |

## Liên kết
<!-- required -->

<mỗi NFR truy về FR hoặc ràng buộc nào, kèm link tới [requirements-trace.md](requirements-trace.md) hoặc [constraints.md](constraints.md)>
