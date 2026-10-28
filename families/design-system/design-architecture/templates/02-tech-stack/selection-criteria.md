# Tiêu chí lựa chọn (TC)

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Đây là nơi **định nghĩa** `TC-xx` (ô đầu dòng bảng). Tiêu chí được duyệt ở G2, **trước khi** nêu tên bất kỳ công nghệ nào: không ghi tên công nghệ hay ứng viên ở file này. Tiêu chí không truy về FR, NFR hoặc ràng buộc thì không được dùng.

## Tiêu chí loại trừ
<!-- required -->

Ứng viên vi phạm một tiêu chí loại trừ bị gạt, không được chấm.

| ID | Tiêu chí | Truy về (FR / NFR / C) | Ngưỡng (số + đơn vị) | Cách kiểm |
| --- | --- | --- | --- | --- |
| TC-xxx | <điều ứng viên bắt buộc đáp ứng> | <FR-xx, NFR-xx hoặc C-xx> | <ngưỡng, hoặc "có / không"> | <tài liệu, spike hoặc kiểm tra nào> |

## Tiêu chí có trọng số
<!-- required -->

Trọng số do người dùng duyệt. Điểm thô 0–5 mỗi tiêu chí; tổng theo công thức Σ(điểm × trọng số) / (5 × Σ trọng số) × 100.

| ID | Tiêu chí | Truy về (FR / NFR / C) | Trọng số | Cách chấm 0–5 |
| --- | --- | --- | --- | --- |
| TC-xxx | <điều cần so sánh> | <FR-xx, NFR-xx hoặc C-xx> | <số> | <0 là …, 5 là …> |

## Áp dụng cho
<!-- required -->

Mỗi tiêu chí dùng cho lớp stack hoặc quyết định kiến trúc nào.

Không đặt `TC-xx` ở ô đầu dòng (chỉ hai bảng trên định nghĩa TC).

| Áp dụng cho | Tiêu chí |
| --- | --- |
| <lớp hoặc quyết định> | <TC-xx, …> |
