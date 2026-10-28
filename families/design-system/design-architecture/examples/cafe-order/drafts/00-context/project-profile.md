# Hồ sơ dự án

## Mức áp dụng
<!-- required -->

Mức: M

Lý do chọn mức: sản phẩm thật cho một team, 3.000 người dùng sau 1 năm (A-dau), chưa cần hội đồng 5 phiếu hay spike.

Mốc tính số liệu của mức M: launch, 1y, 3y.

## Hồ sơ
<!-- required -->

| Mục | Giá trị (kèm đơn vị) | Nguồn |
| --- | --- | --- |
| Quy mô người dùng | 500 người dùng ra mắt, 3.000 người dùng sau 1 năm | A-dau |
| Dữ liệu dự kiến | 1.500 đơn/ngày sau 1 năm | A-orders-per-day |
| Mức độ quan trọng | Ngừng bán mang đi trong giờ cao điểm; không lưu dữ liệu thanh toán | inputs/ba/prd.md mục 2 |
| Số người trong team | 3 người | inputs/ba/prd.md mục 6 |
| Ngân sách | 300 USD mỗi tháng | inputs/ba/prd.md mục 6 |
| Thời hạn | 2027-03-01 | inputs/ba/prd.md mục 6 |
| Tuân thủ | Không có quy định riêng | inputs/ba/prd.md mục 7 |

## Phần áp dụng
<!-- required -->

| Phần | Áp dụng | Lý do (Q8) |
| --- | --- | --- |
| 00-context | có | mọi dự án có |
| 01-system | có | mức M giữ đủ |
| 02-tech-stack | có | mọi dự án có |
| 03-capacity | có | mức M giữ đủ, ba mốc |
| 04-flows | có | mọi dự án có |
| 05-frontend | có | mức M giữ đủ |
| 06-backend | có | mọi dự án có |
| 07-data | có | mọi dự án có |
| 07-data/object-storage.md | bỏ | dự án không lưu ảnh hay tài liệu, nên không có bucket |
| 07-data/cache.md | bỏ | tải đỉnh ở [workload-model.md](../03-capacity/workload-model.md) thấp, database đáp ứng trực tiếp nên chưa cần cache |
| 07-data/messaging.md | bỏ | mọi thao tác đồng bộ, không có event hay hàng đợi |
| 08-security | có | mức M giữ đủ |
| 09-infrastructure | có | mức M giữ đủ |
| 10-process | có | mức M giữ đủ |
| 11-risks | có | mức M giữ đủ |
| 12-roadmap | có | mức M giữ đủ |
