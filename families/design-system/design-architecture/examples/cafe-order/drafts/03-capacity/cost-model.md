# Mô hình chi phí

<!-- Sinh bởi calc_capacity.py từ capacity/*.yaml. Không sửa tay: sửa yaml rồi chạy lại. -->

Mức dự án: M. Mốc: Ra mắt (launch), 1 năm (1y), 3 năm (3y). 1 năm = 365 ngày, 1 tháng = 365/12 ngày, 1 ngày = 86,400 giây.

Chi phí theo tháng, đơn vị USD. Đơn giá lấy từ `pricing.yaml` (1 GB = 1,073,741,824 byte, [nguồn](https://example.com/pricing/storage#units)); lượng lấy từ [data-sizing.md](data-sizing.md), [storage-sizing.md](storage-sizing.md), [compute-sizing.md](compute-sizing.md).
Lưu trữ database tính theo **dung lượng cần cấp** (sau phình, cộng WAL, bản sao và backup) với đơn giá lưu trữ của database. Mốc đỉnh tải chỉ tính phần compute.

## Đơn giá

| Mục | Mô tả | Đơn vị | Đơn giá | Nguồn | Ngày tra cứu |
| --- | --- | --- | --- | --- | --- |
| compute-instance | VM 2 vCPU, 4 GB RAM | instance-month | 40 | [nguồn](https://example.com/pricing/compute) | 2026-10-12 |
| db-storage | Ổ đĩa cho database | GB-month | 0.115 | [nguồn](https://example.com/pricing/block-storage) | 2026-10-12 |

## Chi phí mỗi tháng

| Khoản | Ra mắt | 1 năm | 3 năm |
| --- | --- | --- | --- |
| Compute (instance × đơn giá) | 80.00 | 80.00 | 80.00 |
| Lưu trữ database (GB cần cấp × đơn giá) | 0.23 | 0.35 | 1.12 |
| Object storage (GB × đơn giá) | 0.00 | 0.00 | 0.00 |
| Băng thông ra (GB × đơn giá) | 0.00 | 0.00 | 0.00 |
| **Tổng** | 80.23 | 80.35 | 81.12 |

Không có object storage: khoản object storage và băng thông ra bằng 0.
