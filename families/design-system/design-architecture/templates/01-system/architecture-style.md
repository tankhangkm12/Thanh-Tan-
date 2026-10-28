# Kiểu kiến trúc và giai đoạn scale

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Kiểu kiến trúc là quyết định khó đảo ngược nên qua hội đồng ở G3 (`D-xxx`). Ngưỡng chuyển giai đoạn là số, lấy từ `capacity/` và khớp [scaling-stages.md](../12-roadmap/scaling-stages.md) (mức S không có file đó, khi đó ghi ngưỡng ở đây). File này chỉ nhắc ID, không đặt `NFR-`, `D-`… ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Kiểu đã chọn
<!-- required -->

- Kiểu: <monolith, modular monolith, microservices, kết hợp>
- Quyết định: <D-xxx>

## Lý do
<!-- required -->

| Điều kiện | Nguồn | Vì sao kiểu này đáp ứng |
| --- | --- | --- |
| <điều kiện> | <NFR-xx, C-xx hoặc TC-xx> | <giải thích, kèm số nếu có> |

## Phương án đã loại
<!-- required -->

| Phương án | Vì sao loại | Nguồn |
| --- | --- | --- |
| <kiểu khác> | <lý do> | <NFR-xx, C-xx, TC-xx hoặc D-xxx> |

## Giai đoạn scale
<!-- required -->

| Giai đoạn | Kiểu ở giai đoạn này | Ngưỡng bắt đầu (số + đơn vị) | Việc phải làm khi chuyển | Cơ sở |
| --- | --- | --- | --- | --- |
| <giai đoạn> | <kiểu> | <số kích hoạt> | <việc> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Gánh nặng vận hành
<!-- required -->

Chi phí nâng cấp và bảo trì riêng của kiểu này (số dịch vụ phải vá, pipeline phải giữ), để team có đủ người (Q3).

| Việc | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <việc> | <ngày, tuần, tháng> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Rủi ro
<!-- required -->

Rủi ro của kiểu kiến trúc (phức tạp vận hành, chia sai ranh giới) đã khai trong [sổ rủi ro](../11-risks/risk-register.md): <R-xx, …>.
