# Các giai đoạn scale

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mức S bỏ file này (ngưỡng ghi ở `architecture-style.md`). Mọi ngưỡng là số có đơn vị, lấy từ `capacity/` qua [workload-model.md](../03-capacity/workload-model.md) và [compute-sizing.md](../03-capacity/compute-sizing.md): **dẫn link, không chép lại**; chi phí giai đoạn dẫn link [cost-model.md](../03-capacity/cost-model.md). Phải khớp mục "Giai đoạn scale" của [architecture-style.md](../01-system/architecture-style.md) và "Ngưỡng lên giai đoạn sau" trong các `scaling.md`. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Giai đoạn
<!-- required -->

| Giai đoạn | Ngưỡng bắt đầu (số + đơn vị) | Nguồn của ngưỡng | Thay đổi kiến trúc | Chi phí thêm | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| <tên, ví dụ: ra mắt, 1 năm, 3 năm> | <ví dụ: req/s đỉnh, số dòng, số người dùng> | <link workload-model.md hoặc compute-sizing.md> | <việc phải làm> | <link cost-model.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Dấu hiệu cần chuyển giai đoạn
<!-- required -->

Số liệu vận hành báo sớm là sắp chạm ngưỡng; mỗi dấu hiệu có cảnh báo ở [observability.md](../09-infrastructure/observability.md).

| Giai đoạn kế tiếp | Dấu hiệu | Ngưỡng cảnh báo (số + đơn vị) | Thời gian đệm trước khi chạm ngưỡng thật | Cơ sở |
| --- | --- | --- | --- | --- |
| <tên> | <chỉ số> | <số> | <số + đơn vị> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Thứ tự thay đổi
<!-- required -->

Việc phải làm trước ngưỡng, theo thứ tự, để chuyển giai đoạn không gián đoạn (Q3).

- <giai đoạn: bước 1, bước 2, người phụ trách>

## Rủi ro
<!-- required -->

Rủi ro của việc chuyển giai đoạn (đến muộn, vượt ngân sách) đã khai trong [sổ rủi ro](../11-risks/risk-register.md): <R-xx, …>.
