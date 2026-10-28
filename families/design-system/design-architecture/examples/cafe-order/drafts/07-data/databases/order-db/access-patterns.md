# Mẫu truy cập của order-db

## Mẫu truy cập
<!-- required -->

| Mẫu | Đọc / ghi | Bảng | Luồng | Tần suất (số + đơn vị) | Độ trễ mục tiêu (ms) | Index phục vụ | Cơ sở |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ghi đơn và các dòng món | ghi | TBL-orders, TBL-order-items | FL-001 | A-orders-per-day | 50 ms | orders_pkey | NFR-001 |
| đọc đơn theo mã | đọc | TBL-orders | FL-002 | A-requests-per-user | 20 ms | orders_pkey | NFR-001 |
| lấy các dòng món của đơn | đọc | TBL-order-items | FL-002 | A-requests-per-user | 20 ms | order_items_order_idx | NFR-001 |

## Truy vấn nặng

Không có truy vấn nặng.
