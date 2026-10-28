# Index của order-db

## Index
<!-- required -->

| Index | Bảng | Cột | Loại | Mẫu truy cập phục vụ | Lý do |
| --- | --- | --- | --- | --- | --- |
| orders_pkey | TBL-orders | id | B-tree | đọc đơn theo mã | khóa chính |
| orders_created_idx | TBL-orders | created_at | B-tree | báo cáo theo ngày | nhân viên xem đơn theo thời gian |
| order_items_pkey | TBL-order-items | id | B-tree | khóa chính | khóa chính |
| order_items_order_idx | TBL-order-items | order_id | B-tree | lấy dòng món theo đơn | tra theo khóa ngoại |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| số index tối đa mỗi bảng | 2 index | NFR-001 | đếm trong tables.yaml |
