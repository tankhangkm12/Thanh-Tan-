# Bảng của order-db

## Bảng
<!-- required -->

### TBL-orders: orders

- Mục đích: lưu các đơn
- Yêu cầu: FR-001, FR-002, FR-003, NFR-001
- Chủ sở hữu: SVC-order-service
- Khóa trong `tables.yaml`: orders
- Khóa chính và khóa ngoại: id integer, không có khóa ngoại

<!-- BEGIN:calc:orders -->
Tính bởi `calc_capacity.py` (chi tiết và nguồn hằng số: [data-sizing.md](../../../03-capacity/data-sizing.md)). Không sửa tay.

| # | Cột | Kiểu | Byte | Căn lề | Đệm trước | Lý do |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | id | `integer` | 4 | 4 | 0 | khóa chính; 5.000 đơn mỗi ngày ở mốc 3y thì integer (tối đa 2.147.483.647) đủ hơn 400 năm |
| 2 | status | `smallint` | 2 | 2 | 0 | bốn trạng thái cố định, 2 byte đủ |
| 3 | total_cents | `integer` | 4 | 4 | 2 | tiền tính bằng xu; một đơn không vượt 21 triệu USD |
| 4 | created_at | `timestamptz` | 8 | 8 | 4 | mốc tạo đơn, có múi giờ |
| 5 | note | `text` | 31 | 1 | 0 | ghi chú tự do của khách, có thể rỗng |

- Đầu dòng: 23 byte (`tuple_header_bytes`) + null bitmap 1 byte, căn lên bội số MAXALIGN 8 (giả định A-maxalign, nền tảng x86_64) → vị trí dữ liệu 24 byte.
- Dữ liệu các cột (kể cả đệm căn lề): 55 byte; đệm cuối dòng 1 byte (tuple căn lên bội số MAXALIGN).
- Độ dài tuple: 80 byte; + con trỏ dòng 4 byte = **84 byte/dòng**.
- Dòng trên một trang: ⌊(8192 − 24) × fillfactor 1 ÷ 84⌋ = **97**.

| Index | Cột | Byte/mục | Mục/trang |
| --- | --- | --- | --- |
| orders_pkey | id | 20 | 366 |
| orders_created_idx | created_at | 20 | 366 |

| Mốc | Dòng/ngày (giai đoạn) | Dòng đã chèn (tích lũy) | Dòng đang giữ | Trang heap | Heap | Index | Tổng logic (heap + index) | Sau phình (bloat) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ra mắt | 0 | 0 | 0 | 0 | 0.00 B | orders_pkey: 0.00 B, orders_created_idx: 0.00 B | 0.00 B (0 byte) | 0.00 B (0 byte) |
| 1 năm | 1,500 | 547,500 | 547,500 | 5,645 | 44.10 MiB | orders_pkey: 11.69 MiB, orders_created_idx: 11.69 MiB | 67.48 MiB (70,754,304 byte) | 83.31 MiB (87,356,211 byte) |
| 3 năm | 5,000 | 4,197,500 | 4,197,500 | 43,274 | 338.08 MiB | orders_pkey: 89.60 MiB, orders_created_idx: 89.60 MiB | 517.28 MiB (542,408,704 byte) | 638.66 MiB (669,681,254 byte) |

- Cột `id` kiểu `integer` (tối đa 2,147,483,647): cần 5,456,750 giá trị ở mốc 3y (đã chèn 4,197,500 × (1 + biên an toàn 0.3)); còn đủ khoảng 1,174.4 năm sau mốc 3y → **ĐỦ**; kiểu nhỏ nhất đủ: `integer`.
<!-- END:calc:orders -->

### TBL-order-items: order_items

- Mục đích: lưu các dòng món của đơn
- Yêu cầu: FR-001, NFR-001
- Chủ sở hữu: SVC-order-service
- Khóa trong `tables.yaml`: order_items
- Khóa chính và khóa ngoại: id integer, order_id integer tham chiếu TBL-orders

<!-- BEGIN:calc:order_items -->
Tính bởi `calc_capacity.py` (chi tiết và nguồn hằng số: [data-sizing.md](../../../03-capacity/data-sizing.md)). Không sửa tay.

| # | Cột | Kiểu | Byte | Căn lề | Đệm trước | Lý do |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | id | `integer` | 4 | 4 | 0 | khóa chính; 15.000 dòng mỗi ngày ở mốc 3y thì integer đủ hơn 140 năm |
| 2 | order_id | `integer` | 4 | 4 | 0 | khóa ngoại sang orders.id, cùng kiểu với khóa chính |
| 3 | product_id | `smallint` | 2 | 2 | 0 | thực đơn dưới 32.000 món |
| 4 | quantity | `smallint` | 2 | 2 | 0 | số lượng mỗi dòng không vượt 32.000 |
| 5 | unit_cents | `integer` | 4 | 4 | 0 | đơn giá tính bằng xu |

- Đầu dòng: 23 byte (`tuple_header_bytes`) + null bitmap 0 byte, căn lên bội số MAXALIGN 8 (giả định A-maxalign, nền tảng x86_64) → vị trí dữ liệu 24 byte.
- Dữ liệu các cột (kể cả đệm căn lề): 16 byte; đệm cuối dòng 0 byte (tuple căn lên bội số MAXALIGN).
- Độ dài tuple: 40 byte; + con trỏ dòng 4 byte = **44 byte/dòng**.
- Dòng trên một trang: ⌊(8192 − 24) × fillfactor 1 ÷ 44⌋ = **185**.

| Index | Cột | Byte/mục | Mục/trang |
| --- | --- | --- | --- |
| order_items_pkey | id | 20 | 366 |
| order_items_order_idx | order_id | 20 | 366 |

| Mốc | Dòng/ngày (giai đoạn) | Dòng đã chèn (tích lũy) | Dòng đang giữ | Trang heap | Heap | Index | Tổng logic (heap + index) | Sau phình (bloat) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ra mắt | 0 | 0 | 0 | 0 | 0.00 B | order_items_pkey: 0.00 B, order_items_order_idx: 0.00 B | 0.00 B (0 byte) | 0.00 B (0 byte) |
| 1 năm | 4,500 | 1,642,500 | 1,642,500 | 8,879 | 69.37 MiB | order_items_pkey: 35.06 MiB, order_items_order_idx: 35.06 MiB | 139.49 MiB (146,268,160 byte) | 174.40 MiB (182,874,931 byte) |
| 3 năm | 15,000 | 12,592,500 | 12,592,500 | 68,068 | 531.78 MiB | order_items_pkey: 268.80 MiB, order_items_order_idx: 268.80 MiB | 1.04 GiB (1,121,320,960 byte) | 1.31 GiB (1,401,955,942 byte) |

- Cột `id` kiểu `integer` (tối đa 2,147,483,647): cần 16,370,250 giá trị ở mốc 3y (đã chèn 12,592,500 × (1 + biên an toàn 0.3)); còn đủ khoảng 389.9 năm sau mốc 3y → **ĐỦ**; kiểu nhỏ nhất đủ: `integer`.
<!-- END:calc:order_items -->

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| byte mỗi dòng của orders | dưới 100 byte | NFR-001 | calc_capacity.py, xem [data-sizing.md](../../../03-capacity/data-sizing.md) |

## Được dùng bởi
<!-- required -->

- [requirements-trace.md](../../../00-context/requirements-trace.md)
- [FL-001](../../../04-flows/FL-001-dat-don.md)
- [FL-002](../../../04-flows/FL-002-xem-trang-thai.md)
- [FL-003](../../../04-flows/FL-003-cap-nhat-trang-thai.md)
- [data-sizing.md](../../../03-capacity/data-sizing.md)
- [data.md](../../../06-backend/services/order-service/data.md)
- [domain-model.md](../../../06-backend/services/order-service/domain-model.md)
- [erd.md](erd.md)
- [access-patterns.md](access-patterns.md)
- [indexing.md](indexing.md)
- [partitioning-retention.md](partitioning-retention.md)
- [implementation-plan.md](../../../12-roadmap/implementation-plan.md)
