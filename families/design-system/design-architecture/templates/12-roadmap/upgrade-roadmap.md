# Lộ trình nâng cấp theo ngày hết hỗ trợ

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mức S bỏ file này. Phiên bản và ngày hết hỗ trợ lấy từ [versions-features.md](../02-tech-stack/versions-features.md): **dẫn link tới dòng đó, không chép lại**; `check_versions.py` kiểm ngày ở đó. Đổi phiên bản sau khi stack đã chốt đi qua chế độ nâng cấp và ghi vào `CHANGELOG.md`. Giờ làm khớp [maintenance.md](../10-process/maintenance.md). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Lộ trình
<!-- required -->

Sắp theo ngày hết hỗ trợ gần nhất trước.

| Công nghệ | Dòng trong ma trận | Bản kế tiếp | Hạn bắt đầu (YYYY-MM-DD) | Hạn xong (YYYY-MM-DD) | Thay đổi phá vỡ cần xử lý | Công sức ước tính (giờ) | Cơ sở ước tính |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <tên> | <[liên kết](../02-tech-stack/versions-features.md)> | <major.minor> | <ngày> | <ngày, trước ngày hết hỗ trợ> | <link ghi chú phát hành> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Phụ thuộc giữa các lần nâng cấp
<!-- required -->

| Nâng cấp | Phải làm sau | Lý do |
| --- | --- | --- |
| <công nghệ> | <công nghệ khác, hoặc "không"> | <tương thích theo compatibility.md> |

## Rủi ro
<!-- required -->

Rủi ro nâng cấp (hết hỗ trợ trong 12 tháng, thay đổi phá vỡ lớn) đã khai trong [sổ rủi ro](../11-risks/risk-register.md): <R-xx, …>.
