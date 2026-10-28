# Quy trình thay đổi dữ liệu

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Công cụ và quy tắc migration của từng database nằm ở `migration-strategy.md` trong `07-data/databases/<db>/`: file này **dẫn link**, chỉ nói quy trình cho con người và các thay đổi xuyên database. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Migration schema
<!-- required -->

| Database | Quy tắc | Nơi đã viết |
| --- | --- | --- |
| <db> | <công cụ, thứ tự so với triển khai mã> | <[migration-strategy.md](../07-data/databases/db/migration-strategy.md)> |

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Ai duyệt migration | <vai trò> | |
| Thử trên môi trường nào trước | <staging, bản sao dữ liệu ẩn danh> | |
| Thời gian khóa tối đa cho phép (giây) | <số, khớp migration-strategy.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Backfill
<!-- required -->

Ghi "không có backfill" nếu dự án chưa cần.

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Cách chạy | <job nền, theo lô> | |
| Kích thước lô (số dòng) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Tốc độ tối đa để không ảnh hưởng tải thật | <dòng mỗi giây> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Dừng và chạy lại | <idempotent, ghi mốc đã xử lý> | |
| Cửa sổ chạy | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Sửa dữ liệu thủ công
<!-- required -->

| Mục | Giá trị |
| --- | --- |
| Khi nào được phép | <điều kiện> |
| Ai thực hiện và ai duyệt | <vai trò> |
| Ghi vết | <câu lệnh, người làm, lý do, thời điểm lưu ở đâu> |
| Sao lưu trước khi sửa | <bắt buộc, cách> |

## Xác minh sau thay đổi
<!-- required -->

| Kiểm tra | Cách kiểm | Khi lệch |
| --- | --- | --- |
| <số dòng, tổng kiểm, đối soát> | <câu truy vấn, báo cáo> | <rollback theo delivery.md, sửa tiếp> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <thời gian khóa bảng dài nhất khi migration (giây)> | <số> | <NFR-xx> | <nhật ký migration> |
| <ảnh hưởng của backfill lên p95 độ trễ> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |
