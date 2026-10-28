# Scale, nâng cấp, bảo trì của service

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc (Q2, Q3). Số instance theo mốc do `calc_capacity.py` tính ở [compute-sizing.md](../../../03-capacity/compute-sizing.md): **dẫn link, không chép lại**. Phiên bản và ngày hết hỗ trợ lấy từ [versions-features.md](../../../02-tech-stack/versions-features.md). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Scale
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Đơn vị scale | <instance, shard…> | |
| Có trạng thái trong bộ nhớ không | <có / không; nếu có, cách chia sẻ> | |
| Giới hạn một instance (số + đơn vị) | <req/s mỗi instance> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Số instance theo mốc | <link tới mục SVC-xx trong compute-sizing.md> | |
| Điểm nghẽn tiếp theo | <thành phần, ngưỡng số khi chạm> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Ngưỡng lên giai đoạn sau | <số kích hoạt, link scaling-stages.md nếu có> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Nâng cấp
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Runtime và framework | <tên, phiên bản chốt, link versions-features.md> | |
| Ngày hết hỗ trợ gần nhất | <YYYY-MM-DD, link> | |
| Đường nâng cấp | <bản kế tiếp, việc phải làm, thay đổi phá vỡ> | |
| Cách nâng cấp không gián đoạn | <rolling, blue-green; thời gian gián đoạn tối đa (giây)> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <vá bảo mật, xoay khóa, dọn dữ liệu> | <ngày, tuần, tháng> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <mức dùng CPU ở tải đỉnh> | <phần trăm> | <NFR-xx> | <công cụ, vị trí đo> |
| <thời gian khởi động một instance> | <giây> | <NFR-xx> | <công cụ, vị trí đo> |
