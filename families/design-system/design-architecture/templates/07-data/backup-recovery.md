# Sao lưu và khôi phục

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. RPO và RTO truy về NFR (`quality-attributes.md`) và phải khớp [scaling-ha.md](../09-infrastructure/scaling-ha.md) (có từ mức M); dung lượng bản sao lưu lấy từ `calc_capacity.py` (giả định `backups` của database), **dẫn link [data-sizing.md](../03-capacity/data-sizing.md), không chép lại**. Quy trình diễn tập chi tiết ở [operations.md](../10-process/operations.md). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## RPO và RTO
<!-- required -->

| Kho | RPO (phút) | RTO (phút) | NFR | Cách đạt |
| --- | --- | --- | --- | --- |
| <database, object storage> | <số> | <số> | <NFR-xx> | <nhật ký ghi trước, bản sao, sao lưu theo lịch> |

## Lịch sao lưu
<!-- required -->

| Kho | Loại sao lưu | Tần suất | Thời gian giữ (ngày) | Nơi lưu | Mã hóa | Cơ sở |
| --- | --- | --- | --- | --- | --- | --- |
| <kho> | <đầy đủ, gia tăng, liên tục> | <giờ, ngày> | <số> | <vị trí khác vùng với dữ liệu gốc> | <khi lưu, khi truyền> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Diễn tập khôi phục
<!-- required -->

Bản sao lưu chưa từng khôi phục thử thì chưa coi là có.

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Tần suất diễn tập | <tháng, quý> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Phạm vi mỗi lần | <khôi phục kho nào, vào môi trường nào> | |
| Tiêu chí đạt | <thời gian khôi phục thực đo (phút) không vượt RTO, dữ liệu mất không vượt RPO> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Nơi ghi kết quả | <đường dẫn> | |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <thời gian khôi phục thực đo trong diễn tập> | <số + đơn vị> | <NFR-xx> | <báo cáo diễn tập> |
| <thời gian chạy một lần sao lưu> | <số + đơn vị> | <NFR-xx> | <log sao lưu> |

## Nâng cấp và bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <kiểm bản sao lưu còn đọc được, rà thời gian giữ, xoay khóa mã hóa> | <tuần, tháng> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Rủi ro
<!-- required -->

Rủi ro mất dữ liệu và khôi phục đã khai trong [sổ rủi ro](../11-risks/risk-register.md): <R-xx, …>.
