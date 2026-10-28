# Phân vùng, giữ dữ liệu và scale của <db>

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc (Q3: đường scale). Thời gian giữ lấy từ `retention_days` trong `capacity/tables.yaml`; dung lượng lấy từ [data-sizing.md](../../../03-capacity/data-sizing.md), dẫn link, không chép số. Không đặt ID ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Phân vùng
<!-- required -->

Bảng nào phân vùng, theo khóa nào, kích thước mỗi phân vùng. Không bảng nào cần phân vùng thì ghi "không phân vùng" kèm ngưỡng số khi sẽ cần.

| Bảng | Khóa phân vùng | Kích thước mỗi phân vùng (số + đơn vị) | Ngưỡng bắt đầu phân vùng | Cơ sở |
| --- | --- | --- | --- | --- |
| <TBL-xx> | <cột> | <số> | <ví dụ: > 100 triệu dòng> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Thời gian giữ dữ liệu
<!-- required -->

| Bảng | Giữ (ngày) | Cách xóa hoặc lưu trữ | Nguồn yêu cầu (C-xx / NFR-xx) |
| --- | --- | --- | --- |
| <TBL-xx> | <số> | <xóa theo phân vùng, chuyển lạnh> | <C-xx> |

## Scale
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Đơn vị scale | <nâng cấu hình primary, thêm bản sao đọc, shard> | |
| Giới hạn trước khi phải đổi (số + đơn vị) | <dung lượng, req/s> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Ngưỡng lên giai đoạn sau | <số kích hoạt, link scaling-stages.md nếu có> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Số bản sao theo mốc | <link giả định trong assumptions.md> | |
