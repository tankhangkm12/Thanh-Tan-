# Cache

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Cache chỉ là bản sao: nguồn sự thật ở [overview.md](overview.md). Dự án không dùng cache thì hồ sơ dự án ghi `07-data/cache.md` là `bỏ` kèm lý do (Q8). File này chỉ nhắc ID, không đặt `TBL-`, `API-`… ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Dữ liệu được cache
<!-- required -->

| Dữ liệu | Nguồn | Khóa cache | Thời gian sống (giây) | Cách vô hiệu hóa | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| <tên> | <TBL-xx hoặc API-xx> | <mẫu khóa> | <số> | <khi ghi, hết hạn, theo event> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Chiến lược
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Mẫu dùng | <cache-aside, write-through> | |
| Bộ nhớ tối đa (MB) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Chính sách loại bỏ khi đầy | <LRU, LFU> | |
| Chống dồn request khi một khóa hết hạn | <khóa tạm, làm mới sớm> | |

## Khi cache hỏng hoặc trống
<!-- required -->

| Tình huống | Hành vi | Tải lên nguồn (req/s) | Cơ sở |
| --- | --- | --- | --- |
| <cache mất, khởi động nguội> | <đọc thẳng nguồn, hạ cấp> | <số, từ workload-model.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <tỉ lệ trúng cache> | <phần trăm> | <NFR-xx> | <metric của cache> |
| <p95 độ trễ đọc cache> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Đơn vị scale | <node, shard> | |
| Ngưỡng lên giai đoạn sau | <số kích hoạt> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Đường nâng cấp | <phiên bản, ngày hết hỗ trợ lấy từ versions-features.md> | |
| Bảo trì mỗi tháng (giờ) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
