# Mô hình miền

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mô hình miền ở mức nghiệp vụ; kiểu và byte từng cột nằm ở `07-data/databases/<db>/tables.md`. Không đặt ID ở ô đầu dòng bảng.

## Thực thể
<!-- required -->

| Thực thể | Mô tả | Danh tính | Lưu ở bảng |
| --- | --- | --- | --- |
| <tên> | <một câu> | <khóa tự nhiên hay sinh> | <TBL-xx> |

## Quy tắc bất biến
<!-- required -->

| Quy tắc | Áp dụng cho | Nguồn (FR / NFR / C) | Cách bảo đảm |
| --- | --- | --- | --- |
| <điều luôn đúng> | <thực thể> | <FR-xx> | <ràng buộc DB, kiểm tra ở service> |

## Vòng đời trạng thái

Các trạng thái và chuyển trạng thái hợp lệ của thực thể chính; không có thì ghi "thực thể không có trạng thái".
