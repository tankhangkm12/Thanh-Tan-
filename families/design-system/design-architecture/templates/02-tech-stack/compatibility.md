# Tương thích giữa các lớp

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Kiểm tra chéo sau khi chốt từng lớp: từng lớp phù hợp riêng lẻ chưa đủ, ghép lại cũng phải khớp (Q5). Phiên bản lấy từ [versions-features.md](versions-features.md).

## Ma trận tương thích
<!-- required -->

| Cặp (A ↔ B) | Phiên bản A | Phiên bản B | Kết quả | Bằng chứng |
| --- | --- | --- | --- | --- |
| <lớp A ↔ lớp B> | <major.minor> | <major.minor> | <tương thích / tương thích có điều kiện / xung đột> | <link tài liệu chính thức hoặc kết quả spike> |

## Xung đột và cách xử lý
<!-- required -->

Không có xung đột thì ghi "không có xung đột" kèm ngày kiểm tra.

| Xung đột | Cách xử lý | Rủi ro |
| --- | --- | --- |
| <mô tả> | <đổi phiên bản nào, hay chấp nhận> | <R-xx> |
