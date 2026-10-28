# Năng lực tính toán

<!-- Sinh bởi calc_capacity.py từ capacity/*.yaml. Không sửa tay: sửa yaml rồi chạy lại. -->

Mức dự án: M. Mốc: Ra mắt (launch), 1 năm (1y), 3 năm (3y). 1 năm = 365 ngày, 1 tháng = 365/12 ngày, 1 ngày = 86,400 giây.

Công thức: `instance = max(min_instances, ⌈req/s đỉnh có biên an toàn × tỉ lệ lưu lượng ÷ (req/s mỗi instance × mức dùng mục tiêu)⌉)`.
Tải lấy từ [workload-model.md](workload-model.md); giả định xem [assumptions.md](../00-context/assumptions.md).

## order-service (SVC-order-service)

Tỉ lệ lưu lượng 1; năng lực mỗi instance 100 req/s ([nguồn](https://example.com/benchmarks/order-service-with-postgresql-2026-10)); mức dùng mục tiêu 0.7; tối thiểu 2 instance.

| Mốc | req/s phần của service | req/s hiệu dụng/instance | Instance theo tải | Instance |
| --- | --- | --- | --- | --- |
| Ra mắt | 1.35 | 70.00 | 1 | **2** |
| 1 năm | 8.12 | 70.00 | 1 | **2** |
| 3 năm | 27.08 | 70.00 | 1 | **2** |
