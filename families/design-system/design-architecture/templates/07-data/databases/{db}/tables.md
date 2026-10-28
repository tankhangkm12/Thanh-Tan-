# Bảng của <db>

> Template của design-architecture, một thư mục mỗi database (`07-data/databases/<db>/`). Mục có `<!-- required -->` là bắt buộc. Mỗi bảng một heading cấp 3 `### TBL-xxx: <tên bảng>`: `TBL-xx` được định nghĩa ở heading đó, chỉ ở file này, và tên ID trùng khóa `id` trong `capacity/tables.yaml`. Mỗi bảng có **một cặp dấu** `BEGIN:calc:<bảng>` / `END:calc:<bảng>` (viết trong comment HTML, xem dưới heading của bảng), với `<bảng>` là khóa của bảng trong `tables.yaml`. Designer đặt cặp dấu với nội dung `chờ script`; **chỉ `calc_capacity.py` điền giữa hai dấu** (bố cục dòng: từng cột có kiểu, số byte, căn lề và lý do; index; số theo mốc). Phần ngoài cặp dấu do Designer viết. Không sửa tay giữa hai dấu; không chép số của khối vào chỗ khác.

## Bảng
<!-- required -->

### TBL-xxx: <tên bảng>

- Mục đích: <bảng lưu gì>
- Yêu cầu: <FR-xx, NFR-xx>
- Chủ sở hữu: <SVC-xx>
- Khóa trong `tables.yaml`: <bảng>
- Khóa chính và khóa ngoại: <cột, kiểu; hội đồng đã quyết ở D-xxx nếu là bảng tăng nhanh>

<!-- BEGIN:calc:<bảng> -->
chờ script
<!-- END:calc:<bảng> -->

## Tối ưu
<!-- required -->

Chỉ số của lược đồ, bằng số và đơn vị, truy về NFR (Q2). Số liệu lấy từ [data-sizing.md](../../../03-capacity/data-sizing.md), dẫn link, không chép lại.

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <byte mỗi dòng tối đa> | <số> | <NFR-xx> | <calc_capacity.py hoặc đo thật> |
| <mức dùng giá trị tối đa của cột tăng dần ở mốc xa nhất> | <phần trăm> | <NFR-xx> | <calc_capacity.py> |

## Được dùng bởi
<!-- required -->

Link tới mọi file nhắc một `TBL-xx` của file này (luồng, service, capacity, requirements-trace…); thiếu link là lỗi `missing-backlink`.

- <[tên file](đường-dẫn-tương-đối.md)>
