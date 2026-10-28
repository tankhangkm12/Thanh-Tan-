# Dữ liệu của service

## Dữ liệu sở hữu
<!-- required -->

| Loại | ID | Vai trò | Lượng ghi (số + đơn vị) |
| --- | --- | --- | --- |
| bảng | TBL-orders | các đơn | A-orders-per-day |
| bảng | TBL-order-items | các dòng món | A-order-items-per-day |

## Dữ liệu truy cập
<!-- required -->

Không truy cập dữ liệu của service khác.

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| số truy vấn tối đa mỗi request | 3 truy vấn | NFR-001 | log truy vấn |
