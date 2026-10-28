# Quan sát: SLO, metric, cảnh báo

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. SLO truy về NFR ở `quality-attributes.md`. Ngưỡng cảnh báo bằng số, kèm cơ sở. Mỗi "dấu hiệu sớm" trong sổ rủi ro (`risk-register.md`) phải có cảnh báo tương ứng ở đây. File này chỉ nhắc ID, không đặt ID ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## SLI và SLO
<!-- required -->

| Luồng hoặc dịch vụ | SLI | SLO (số + đơn vị) | Cửa sổ tính (ngày) | NFR |
| --- | --- | --- | --- | --- |
| <tên, kèm FL-xx> | <tỉ lệ thành công, p95 độ trễ> | <ví dụ: 99,5%> | <số> | <NFR-xx> |

## Metric, log và trace
<!-- required -->

| Loại | Thu gì | Công cụ | Thời gian giữ (ngày) | Cơ sở |
| --- | --- | --- | --- | --- |
| <metric hạ tầng, metric ứng dụng, log, trace> | <chỉ số chính> | <công cụ> | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Cảnh báo
<!-- required -->

| Cảnh báo | Điều kiện (ngưỡng + thời gian) | Mức | Ai nhận | Việc phải làm | Dấu hiệu sớm của |
| --- | --- | --- | --- | --- | --- |
| <tên> | <ví dụ: CPU database trên 70% trong 15 phút> | <khẩn, cảnh báo, thông tin> | <vai trò, kênh> | <link hướng dẫn trong operations.md> | <R-xx, hoặc "không"> |

## Báo lỗi và đo thực tế phía client
<!-- required -->

Phần frontend (RUM, báo lỗi client) thu về đâu và gộp vào cảnh báo nào; ghi "không có frontend" nếu dự án không có.

- Nơi nhận: <công cụ, tài khoản>
- Cảnh báo liên quan: <tên cảnh báo ở bảng trên>

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <số cảnh báo giả mỗi tuần> | <số> | <NFR-xx> | <lịch sử cảnh báo> |
| <thời gian từ lúc sự cố đến lúc phát hiện (p95)> | <số + đơn vị> | <NFR-xx> | <nhật ký sự cố> |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <rà ngưỡng cảnh báo, dọn dữ liệu quan sát cũ> | <tuần, tháng> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
