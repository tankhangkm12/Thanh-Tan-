# Scale, HA và DR

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Số instance theo mốc lấy từ [compute-sizing.md](../03-capacity/compute-sizing.md) (dẫn link, không chép lại). RPO và RTO phải khớp [backup-recovery.md](../07-data/backup-recovery.md) và truy về NFR ở `quality-attributes.md`. Mức XL ghi DR chi tiết (xem đoạn cuối mục DR); mức thấp hơn ghi mục DR ngắn gọn. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Autoscale
<!-- required -->

Ghi "không autoscale" kèm lý do nếu số instance cố định.

| Thành phần | Chỉ số kích hoạt | Ngưỡng | Số instance tối thiểu | Số instance tối đa | Thời gian nghỉ giữa hai lần (giây) | Cơ sở |
| --- | --- | --- | --- | --- | --- | --- |
| <tên> | <CPU, req/s, độ dài hàng đợi> | <số + đơn vị> | <số, từ compute-sizing.md> | <số, từ compute-sizing.md> | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## HA
<!-- required -->

| Thành phần | Số bản sao | Vùng hoặc khu | Thời gian chuyển sang bản dự phòng (giây) | Điểm hỏng đơn còn lại | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| <tên> | <số> | <vùng, khu> | <số> | <có, không; nếu có thì R-xx> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## DR
<!-- required -->

| Kịch bản | RPO (phút) | RTO (phút) | NFR | Cách phục hồi | Diễn tập |
| --- | --- | --- | --- | --- | --- |
| <mất một khu, mất một vùng, hỏng dữ liệu> | <số> | <số> | <NFR-xx> | <chuyển sang vùng khác, khôi phục từ sao lưu> | <tần suất, link operations.md> |

Mức XL ghi thêm: thứ tự khôi phục các thành phần, người ra quyết định chuyển DR, cách quay lại vùng chính.

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <thời gian từ lúc quá tải đến lúc có instance mới sẵn sàng> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |
| <uptime tính theo tháng> | <phần trăm> | <NFR-xx> | <giám sát bên ngoài> |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Ngưỡng lên giai đoạn sau | <số kích hoạt, link scaling-stages.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Nâng cấp không gián đoạn | <cách làm, gián đoạn tối đa (giây)> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Việc định kỳ (giờ mỗi tháng) | <kiểm thử failover, rà ngưỡng autoscale: giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
