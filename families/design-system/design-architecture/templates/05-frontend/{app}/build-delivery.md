# Build và phân phối

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Đo và thi hành ngân sách ở [performance-budget.md](../performance-budget.md). Phiên bản framework và ngày hết hỗ trợ lấy từ [versions-features.md](../../02-tech-stack/versions-features.md), không chép lại. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Build
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Công cụ build | <tên, phiên bản chốt, link versions-features.md> | |
| Chia gói mã (code splitting) | <theo route, theo module> | |
| Loại bỏ mã thừa, nén | <cách> | |
| Kích thước gói tối đa mỗi route (KB) | <số, khớp performance-budget.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Phân phối
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Nơi phục vụ | <CDN, kho ứng dụng, cửa hàng ứng dụng> | |
| Cache asset | <tên file có hash, thời gian giữ (giây)> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Ảnh theo kích thước thiết bị | <các kích thước (px), định dạng, ai tạo> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Cập nhật cho người dùng đang mở bản cũ | <tải lại, cập nhật nền, ép cập nhật bản mobile> | |
| Rollback | <cách quay về bản trước, thời gian (phút)> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <tỉ lệ trúng cache CDN> | <phần trăm> | <NFR-xx> | <log CDN> |
| <thời gian build đầy đủ> | <phút> | <NFR-xx> | <CI> |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Scale phân phối | <CDN hay kho ứng dụng gánh được tải đỉnh nào; ngưỡng cần đổi cách phân phối> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Ngày hết hỗ trợ gần nhất của framework | <YYYY-MM-DD, link> | |
| Đường nâng cấp framework | <bản kế tiếp, việc phải làm, thay đổi phá vỡ> | |
| Cập nhật thư viện phụ thuộc | <tần suất, cách kiểm lỗ hổng> | |
| Bảo trì mỗi tháng (giờ) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
