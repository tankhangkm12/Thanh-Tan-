# Scale, HA và DR

## Autoscale
<!-- required -->

Không autoscale: số instance cố định theo mốc ở [compute-sizing.md](../03-capacity/compute-sizing.md), vì tối thiểu đã đủ cho mốc 3y và ngân sách hạ tầng cố định (C-001).

## HA
<!-- required -->

| Thành phần | Số bản sao | Vùng hoặc khu | Thời gian chuyển sang bản dự phòng (giây) | Điểm hỏng đơn còn lại | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| order-service | 2 instance | vùng chính, khu A và khu B | 120, gồm thời gian kiểm tra sức khỏe của DNS | có: chỉ một vùng, R-003 | NFR-002 |
| order-db | 1 bản sao standby (A-replicas) | khu A (primary) và khu B (standby) | 300, đưa standby lên thủ công | có: chỉ một vùng, R-003 | NFR-002 |

## DR
<!-- required -->

| Kịch bản | RPO (phút) | RTO (phút) | NFR | Cách phục hồi | Diễn tập |
| --- | --- | --- | --- | --- | --- |
| mất một khu | 15 | 240 | NFR-002 | đưa standby ở khu còn lại lên primary | mỗi quý, theo [operations.md](../10-process/operations.md) |
| mất cả vùng chính | 15 | 240 | NFR-002 | dựng hai máy ảo mới, khôi phục từ ổ sao lưu ở vùng khác, xem [backup-recovery.md](../07-data/backup-recovery.md) | mỗi quý, theo [operations.md](../10-process/operations.md) |
| xóa hoặc sửa nhầm dữ liệu | 15 | 240 | NFR-002 | khôi phục tới thời điểm trước lỗi từ WAL | mỗi quý, theo [operations.md](../10-process/operations.md) |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian dựng lại một máy ảo từ cấu hình | 30 phút | NFR-002 | nhật ký dựng |
| uptime tính theo tháng | 99,5% | NFR-002 | kiểm tra HTTP từ bên ngoài |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Ngưỡng lên giai đoạn sau | req/s đỉnh vượt công suất 2 instance, xem [compute-sizing.md](../03-capacity/compute-sizing.md) | NFR-003 |
| Nâng cấp không gián đoạn | cập nhật lần lượt từng máy ảo, gián đoạn 0 giây | NFR-002 |
| Việc định kỳ (giờ mỗi tháng) | thử failover, rà ngưỡng cảnh báo: 1 giờ | C-002 |
