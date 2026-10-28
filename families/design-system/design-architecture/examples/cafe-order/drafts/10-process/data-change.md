# Quy trình thay đổi dữ liệu

## Migration schema
<!-- required -->

| Database | Quy tắc | Nơi đã viết |
| --- | --- | --- |
| order-db | migration chạy trước khi triển khai mã mới, tương thích ngược với mã cũ | [migration-strategy.md](../07-data/databases/order-db/migration-strategy.md) |

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Ai duyệt migration | thành viên backend khác người viết | |
| Thử trên môi trường nào trước | staging, dữ liệu giả lập | |
| Thời gian khóa tối đa cho phép (giây) | 2, khớp [migration-strategy.md](../07-data/databases/order-db/migration-strategy.md) | NFR-002 |

## Backfill
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Cách chạy | job nền, theo lô | |
| Kích thước lô (số dòng) | 1.000, khớp [migration-strategy.md](../07-data/databases/order-db/migration-strategy.md) | NFR-001 |
| Tốc độ tối đa để không ảnh hưởng tải thật | 500 dòng/giây | NFR-001 |
| Dừng và chạy lại | idempotent, ghi mốc dòng đã xử lý | |
| Cửa sổ chạy | 22:00 đến 05:00, ngoài giờ cao điểm | NFR-001 |

## Sửa dữ liệu thủ công
<!-- required -->

| Mục | Giá trị |
| --- | --- |
| Khi nào được phép | sửa lỗi dữ liệu mà API không làm được, kèm lý do bằng văn bản |
| Ai thực hiện và ai duyệt | nhân viên vận hành thực hiện, thành viên backend duyệt |
| Ghi vết | câu lệnh, người làm, lý do, thời điểm lưu trong wiki vận hành của team |
| Sao lưu trước khi sửa | bắt buộc: sao lưu đầy đủ theo [backup-recovery.md](../07-data/backup-recovery.md) |

## Xác minh sau thay đổi
<!-- required -->

| Kiểm tra | Cách kiểm | Khi lệch |
| --- | --- | --- |
| số dòng và tổng kiểm của bảng bị đổi | câu truy vấn đếm và tổng kiểm trước và sau | rollback theo [delivery.md](delivery.md), sửa tiếp |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian khóa bảng dài nhất khi migration | 2 giây | NFR-002 | nhật ký migration |
| ảnh hưởng của backfill lên p95 độ trễ | 20 ms | NFR-001 | log truy cập của order-service |
