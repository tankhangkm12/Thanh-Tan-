# Phân vùng, giữ dữ liệu và scale của order-db

## Phân vùng
<!-- required -->

Không phân vùng; xét lại khi bảng vượt 100 triệu dòng (NFR-001).

| Bảng | Khóa phân vùng | Kích thước mỗi phân vùng (số + đơn vị) | Ngưỡng bắt đầu phân vùng | Cơ sở |
| --- | --- | --- | --- | --- |
| TBL-orders | không | không có | 100 triệu dòng | [data-sizing.md](../../../03-capacity/data-sizing.md) |

## Thời gian giữ dữ liệu
<!-- required -->

| Bảng | Giữ (ngày) | Cách xóa hoặc lưu trữ | Nguồn yêu cầu (C-xx / NFR-xx) |
| --- | --- | --- | --- |
| TBL-orders | 1095 ngày | xóa theo lô hằng đêm | C-001 |

## Scale
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Đơn vị scale | nâng cấu hình primary, thêm bản sao đọc | |
| Giới hạn trước khi phải đổi (số + đơn vị) | CPU primary 70% | NFR-001 |
| Ngưỡng lên giai đoạn sau | CPU primary trên 70% trong 15 phút | NFR-001 |
| Số bản sao theo mốc | A-replicas | |
