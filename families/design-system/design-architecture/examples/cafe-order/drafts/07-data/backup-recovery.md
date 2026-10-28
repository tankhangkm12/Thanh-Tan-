# Sao lưu và khôi phục

## RPO và RTO
<!-- required -->

| Kho | RPO (phút) | RTO (phút) | NFR | Cách đạt |
| --- | --- | --- | --- | --- |
| order-db | 15 | 240 | NFR-002 | lưu liên tục nhật ký ghi trước (WAL), bản sao standby, sao lưu đầy đủ theo lịch |

## Lịch sao lưu
<!-- required -->

| Kho | Loại sao lưu | Tần suất | Thời gian giữ (ngày) | Nơi lưu | Mã hóa | Cơ sở |
| --- | --- | --- | --- | --- | --- | --- |
| order-db | đầy đủ, kèm lưu liên tục WAL để khôi phục tới thời điểm | mỗi ngày | 2 | ổ đĩa sao lưu ở vùng khác với dữ liệu gốc | khi lưu và khi truyền | A-backups |

## Diễn tập khôi phục
<!-- required -->

Bản sao lưu chưa từng khôi phục thử thì chưa coi là có.

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Tần suất diễn tập | mỗi quý, lần đầu trước ngày ra mắt | NFR-002 |
| Phạm vi mỗi lần | khôi phục order-db vào môi trường staging | |
| Tiêu chí đạt | thời gian khôi phục thực đo không vượt 240 phút, dữ liệu mất không vượt 15 phút | NFR-002 |
| Nơi ghi kết quả | báo cáo diễn tập trong wiki vận hành của team | |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian khôi phục thực đo trong diễn tập | 120 phút | NFR-002 | báo cáo diễn tập |
| thời gian chạy một lần sao lưu | 30 phút | NFR-002 | log sao lưu |

## Nâng cấp và bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| kiểm bản sao lưu còn đọc được, rà thời gian giữ, xoay khóa mã hóa | mỗi tháng | 1 giờ | C-002 |

## Rủi ro
<!-- required -->

Rủi ro khôi phục vượt RTO đã khai trong [sổ rủi ro](../11-risks/risk-register.md): R-002.
