# Dung lượng dữ liệu

<!-- Sinh bởi calc_capacity.py từ capacity/*.yaml. Không sửa tay: sửa yaml rồi chạy lại. -->

Mức dự án: M. Mốc: Ra mắt (launch), 1 năm (1y), 3 năm (3y). 1 năm = 365 ngày, 1 tháng = 365/12 ngày, 1 ngày = 86,400 giây.

Công thức: `dung lượng logic = số trang × kích thước trang`; `số trang = ⌈số dòng ÷ dòng trên trang⌉`; `byte/dòng = tuple (đầu dòng + dữ liệu có đệm căn lề, căn lên MAXALIGN) + con trỏ dòng`; index tính theo mục B-tree. MAXALIGN là giả định theo nền tảng, không phải hằng số của DB.
Ước lượng theo giá trị trung bình. Hai con số: **dung lượng logic** (heap + index như tính từ dòng và trang) và **dung lượng cần cấp** (logic × hệ số phình + WAL, nhân bản sao, cộng backup; xem từng database). Chưa mô hình: TOAST (chỉ ghi tỉ lệ đã khai), bản đồ không gian trống và visibility map, các tầng trong của B-tree, bitmap null của khóa index.
Giả định xem [assumptions.md](../00-context/assumptions.md).

## Hằng số đã dùng

Hằng số của postgresql 16 (file `db-constants/postgresql-16.yaml`, tra cứu 2026-10-12):

| Hằng số | Giá trị | Nguồn |
| --- | --- | --- |
| `page_size_bytes` | 8,192 | [nguồn](https://www.postgresql.org/docs/16/storage-page-layout.html) |
| `page_header_bytes` | 24 | [nguồn](https://www.postgresql.org/docs/16/storage-page-layout.html) |
| `item_pointer_bytes` | 4 | [nguồn](https://www.postgresql.org/docs/16/storage-page-layout.html) |
| `tuple_header_bytes` | 23 | [nguồn](https://www.postgresql.org/docs/16/storage-page-layout.html) |
| `null_bitmap_bits_per_column` | 1 | [nguồn](https://www.postgresql.org/docs/16/storage-page-layout.html) |
| `heap_fillfactor` | 1 | [nguồn](https://www.postgresql.org/docs/16/sql-createtable.html) |
| `varlena_short_header_bytes` | 1 | [nguồn](https://www.postgresql.org/docs/16/datatype-character.html) |
| `varlena_long_header_bytes` | 4 | [nguồn](https://www.postgresql.org/docs/16/datatype-character.html) |
| `varlena_short_max_bytes` | 126 | [nguồn](https://www.postgresql.org/docs/16/datatype-character.html) |
| `index_tuple_header_bytes` | 8 | [nguồn](https://github.com/postgres/postgres/blob/REL_16_4/src/include/access/itup.h) |
| `btree_leaf_fillfactor` | 0.9 | [nguồn](https://www.postgresql.org/docs/16/sql-createindex.html) |
| `btree_page_special_bytes` | 16 | [nguồn](https://github.com/postgres/postgres/blob/REL_16_4/src/include/access/nbtree.h) |

| Kiểu | Kích thước | Căn lề (byte) | Nguồn |
| --- | --- | --- | --- |
| `integer` | 4 byte | 4 | [nguồn](https://www.postgresql.org/docs/16/datatype-numeric.html), căn lề: [nguồn](https://github.com/postgres/postgres/blob/REL_16_4/src/include/catalog/pg_type.dat) |
| `smallint` | 2 byte | 2 | [nguồn](https://www.postgresql.org/docs/16/datatype-numeric.html), căn lề: [nguồn](https://github.com/postgres/postgres/blob/REL_16_4/src/include/catalog/pg_type.dat) |
| `text` | thay đổi | 4 | [nguồn](https://www.postgresql.org/docs/16/datatype-character.html), căn lề: [nguồn](https://github.com/postgres/postgres/blob/REL_16_4/src/include/catalog/pg_type.dat) |
| `timestamptz` | 8 byte | 8 | [nguồn](https://www.postgresql.org/docs/16/datatype-datetime.html), căn lề: [nguồn](https://github.com/postgres/postgres/blob/REL_16_4/src/include/catalog/pg_type.dat) |

## order-db · orders (TBL-orders)

Dòng mới mỗi ngày: A-orders-per-day; dòng ban đầu: 0; giữ lại: 1095 ngày.

### Bố cục dòng

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

### Index (B-tree)

| Index | Cột | Byte/mục | Mục/trang |
| --- | --- | --- | --- |
| orders_pkey | id | 20 | 366 |
| orders_created_idx | created_at | 20 | 366 |

### Theo mốc

| Mốc | Dòng/ngày (giai đoạn) | Dòng đã chèn (tích lũy) | Dòng đang giữ | Trang heap | Heap | Index | Tổng logic (heap + index) | Sau phình (bloat) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ra mắt | 0 | 0 | 0 | 0 | 0.00 B | orders_pkey: 0.00 B, orders_created_idx: 0.00 B | 0.00 B (0 byte) | 0.00 B (0 byte) |
| 1 năm | 1,500 | 547,500 | 547,500 | 5,645 | 44.10 MiB | orders_pkey: 11.69 MiB, orders_created_idx: 11.69 MiB | 67.48 MiB (70,754,304 byte) | 83.31 MiB (87,356,211 byte) |
| 3 năm | 5,000 | 4,197,500 | 4,197,500 | 43,274 | 338.08 MiB | orders_pkey: 89.60 MiB, orders_created_idx: 89.60 MiB | 517.28 MiB (542,408,704 byte) | 638.66 MiB (669,681,254 byte) |

### Cột tăng dần

- Cột `id` kiểu `integer` (tối đa 2,147,483,647): cần 5,456,750 giá trị ở mốc 3y (đã chèn 4,197,500 × (1 + biên an toàn 0.3)); còn đủ khoảng 1,174.4 năm sau mốc 3y → **ĐỦ**; kiểu nhỏ nhất đủ: `integer`.

## order-db · order_items (TBL-order-items)

Dòng mới mỗi ngày: A-order-items-per-day; dòng ban đầu: 0; giữ lại: 1095 ngày.

### Bố cục dòng

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

### Index (B-tree)

| Index | Cột | Byte/mục | Mục/trang |
| --- | --- | --- | --- |
| order_items_pkey | id | 20 | 366 |
| order_items_order_idx | order_id | 20 | 366 |

### Theo mốc

| Mốc | Dòng/ngày (giai đoạn) | Dòng đã chèn (tích lũy) | Dòng đang giữ | Trang heap | Heap | Index | Tổng logic (heap + index) | Sau phình (bloat) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ra mắt | 0 | 0 | 0 | 0 | 0.00 B | order_items_pkey: 0.00 B, order_items_order_idx: 0.00 B | 0.00 B (0 byte) | 0.00 B (0 byte) |
| 1 năm | 4,500 | 1,642,500 | 1,642,500 | 8,879 | 69.37 MiB | order_items_pkey: 35.06 MiB, order_items_order_idx: 35.06 MiB | 139.49 MiB (146,268,160 byte) | 174.40 MiB (182,874,931 byte) |
| 3 năm | 15,000 | 12,592,500 | 12,592,500 | 68,068 | 531.78 MiB | order_items_pkey: 268.80 MiB, order_items_order_idx: 268.80 MiB | 1.04 GiB (1,121,320,960 byte) | 1.31 GiB (1,401,955,942 byte) |

### Cột tăng dần

- Cột `id` kiểu `integer` (tối đa 2,147,483,647): cần 16,370,250 giá trị ở mốc 3y (đã chèn 12,592,500 × (1 + biên an toàn 0.3)); còn đủ khoảng 389.9 năm sau mốc 3y → **ĐỦ**; kiểu nhỏ nhất đủ: `integer`.

## order-db · dung lượng cần cấp

Công thức: `cần cấp = (heap × hệ số phình heap + index × hệ số phình index + WAL) × (1 + số bản sao) + số backup × (heap × hệ số phình heap + index × hệ số phình index)`. Mỗi bản backup bằng dung lượng dữ liệu sau phình, chưa nén.
Giả định: hệ số phình heap A-heap-bloat, hệ số phình index A-index-bloat, WAL A-wal-bytes, bản sao A-replicas, backup A-backups (xem [assumptions.md](../00-context/assumptions.md)).

| Mốc | Dung lượng logic | Hệ số phình heap / index | Dữ liệu sau phình | WAL | Bản sao | Primary + bản sao | Backup | Dung lượng backup | Cần cấp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ra mắt | 0.00 B (0 byte) | 1.2 / 1.3 | 0.00 B (0 byte) | 1.00 GiB (1,073,741,824 byte) | 1 | 2.00 GiB (2,147,483,648 byte) | 2 | 0.00 B (0 byte) | **2.00 GiB (2,147,483,648 byte)** |
| 1 năm | 206.97 MiB (217,022,464 byte) | 1.2 / 1.3 | 257.71 MiB (270,231,142 byte) | 1.00 GiB (1,073,741,824 byte) | 1 | 2.50 GiB (2,687,945,933 byte) | 2 | 515.42 MiB (540,462,285 byte) | **3.01 GiB (3,228,408,218 byte)** |
| 3 năm | 1.55 GiB (1,663,729,664 byte) | 1.2 / 1.3 | 1.93 GiB (2,071,637,197 byte) | 1.00 GiB (1,073,741,824 byte) | 1 | 5.86 GiB (6,290,758,042 byte) | 2 | 3.86 GiB (4,143,274,394 byte) | **9.72 GiB (10,434,032,435 byte)** |

### TOAST (chưa mô hình)

Tỉ lệ cột độ dài thay đổi vượt ngưỡng TOAST đã khai: 0 (A-toast-ratio, lý do: ghi chú đơn chỉ vài chục byte, không cột nào tới ngưỡng TOAST). Đã khai không có cột vượt ngưỡng, nên không có phần nào chưa được tính.
