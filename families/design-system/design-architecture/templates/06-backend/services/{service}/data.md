# Dữ liệu của service

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Nhắc bảng và bucket bằng ID (`TBL-`, `BKT-`); chúng được định nghĩa ở `07-data/`. Không đặt ID ở ô đầu dòng bảng.

## Dữ liệu sở hữu
<!-- required -->

Chỉ service này được ghi.

| Loại | ID | Vai trò | Lượng ghi (số + đơn vị) |
| --- | --- | --- | --- |
| <bảng, bucket> | <TBL-xx hoặc BKT-xx> | <lưu gì> | <dòng/ngày, lấy từ A-xx> |

## Dữ liệu truy cập
<!-- required -->

Dữ liệu của service khác mà service này đọc, và đường đọc (qua API hay truy vấn trực tiếp). Không có thì ghi "không truy cập dữ liệu của service khác".

| Loại | ID | Chủ sở hữu | Cách đọc |
| --- | --- | --- | --- |
| <bảng, bucket> | <TBL-xx> | <SVC-xx> | <API-xx hoặc truy vấn> |

## Tối ưu
<!-- required -->

Chỉ số truy cập dữ liệu, bằng số và đơn vị, truy về NFR (Q2).

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <số truy vấn tối đa mỗi request> | <số> | <NFR-xx> | <công cụ, vị trí đo> |
| <tỉ lệ cache hit> | <phần trăm> | <NFR-xx> | <công cụ, vị trí đo> |
