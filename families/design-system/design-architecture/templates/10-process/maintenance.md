# Bảo trì và nâng cấp định kỳ

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Ngày hết hỗ trợ và phiên bản lấy từ [versions-features.md](../02-tech-stack/versions-features.md), lộ trình nâng cấp ở [upgrade-roadmap.md](../12-roadmap/upgrade-roadmap.md) (có từ mức M): **dẫn link, không chép lại**. Giờ bảo trì ở file này là tổng hợp từ mục "Bảo trì" của các phần khác và so với số người của team ở `constraints.md`. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Lịch nâng cấp phiên bản
<!-- required -->

| Thành phần | Nơi ghi phiên bản và ngày hết hỗ trợ | Bắt đầu nâng cấp trước ngày hết hỗ trợ (tháng) | Người phụ trách | Cơ sở |
| --- | --- | --- | --- | --- |
| <công nghệ> | <link dòng trong versions-features.md> | <số> | <vai trò> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

Đổi phiên bản sau khi stack đã chốt đi qua chế độ nâng cấp và ghi vào `CHANGELOG.md`.

## Vá lỗi định kỳ
<!-- required -->

| Loại vá | Tần suất | Quy trình | Hạn tối đa (ngày) | Cơ sở |
| --- | --- | --- | --- | --- |
| <bản vá bảo mật, bản vá phụ thuộc> | <tuần, tháng> | <ai kiểm, thử ở đâu, triển khai theo delivery.md> | <số, khớp secrets-compliance.md nếu có> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tổng gánh nặng bảo trì
<!-- required -->

| Việc | Nơi ghi chi tiết | Giờ mỗi tháng |
| --- | --- | --- |
| <việc> | <[liên kết](đường-dẫn.md)> | <giờ> |

Tổng giờ mỗi tháng: <số>; so với năng lực team ở <C-xx>: <đủ, thiếu, và cách xử lý nếu thiếu>.

## Dọn dẹp
<!-- required -->

| Đối tượng | Quy tắc dọn | Tần suất | Cơ sở |
| --- | --- | --- | --- |
| <log, artifact cũ, môi trường tạm, dữ liệu hết hạn> | <giữ bao lâu (ngày), ai xóa> | <tuần, tháng> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <số thành phần đã hết hỗ trợ> | <số> | <NFR-xx> | <check_versions.py, versions-features.md> |
| <thời gian vá lỗ hổng nghiêm trọng (p95)> | <số + đơn vị> | <NFR-xx> | <nhật ký vá> |
