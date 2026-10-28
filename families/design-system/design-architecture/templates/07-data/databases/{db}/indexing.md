# Index của <db>

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Kích thước index do `calc_capacity.py` tính trong khối calc của [tables.md](tables.md) và [data-sizing.md](../../../03-capacity/data-sizing.md): dẫn link, không chép số. Không đặt ID ở ô đầu dòng bảng.

## Index
<!-- required -->

Tên index trùng tên trong `capacity/tables.yaml`.

| Index | Bảng | Cột | Loại | Mẫu truy cập phục vụ | Lý do |
| --- | --- | --- | --- | --- | --- |
| <tên> | <TBL-xx> | <cột, thứ tự> | <B-tree…> | <mẫu trong access-patterns.md> | <vì sao cần; chi phí ghi chấp nhận> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <số index tối đa mỗi bảng> | <số> | <NFR-xx> | <đếm từ tables.yaml> |
| <tỉ lệ tổng index / heap tối đa> | <phần trăm> | <NFR-xx> | <lấy từ data-sizing.md> |
