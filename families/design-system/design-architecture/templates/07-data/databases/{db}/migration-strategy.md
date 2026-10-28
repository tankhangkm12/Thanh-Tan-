# Migration, nâng cấp và bảo trì của <db>

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc (Q3: nâng cấp, bảo trì). Phiên bản và ngày hết hỗ trợ lấy từ [versions-features.md](../../../02-tech-stack/versions-features.md). Không đặt ID ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Migration schema
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Công cụ | <tên, phiên bản chốt> | |
| Quy tắc thay đổi an toàn | <thêm cột có mặc định, tạo index đồng thời, không khóa bảng quá giây> | |
| Thời gian khóa tối đa cho phép (giây) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Cách rollback | <migration ngược, khôi phục từ backup> | |
| Quy trình backfill | <batch kích thước (dòng), giờ chạy, cách kiểm> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Nâng cấp
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Phiên bản hiện tại và ngày hết hỗ trợ | <major.minor, YYYY-MM-DD, link versions-features.md> | |
| Đường nâng cấp | <bản kế tiếp, cách nâng (tại chỗ, dump, logical replication), thay đổi phá vỡ> | |
| Gián đoạn tối đa (giây) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Diễn tập trước khi nâng | <môi trường, tần suất> | |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <dọn bloat, phân tích thống kê, kiểm tra backup> | <ngày, tuần, tháng> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
