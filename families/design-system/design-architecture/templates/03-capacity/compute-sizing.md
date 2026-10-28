# Năng lực tính toán (compute-sizing.md)

> Template của design-architecture, **chỉ mô tả**. File này do `calc_capacity.py` sinh từ `capacity/*.yaml` của workspace (schema: core/workflow/capacity-schema.md); Designer không viết tay, không có mục `<!-- required -->`. Orchestrator chạy script ở G5, G7 và G10; Reviewer chạy `calc_capacity.py --check`. `check_numbers.py` tính lại và báo `generated-file-edited` nếu file bị sửa tay. Muốn đổi số thì sửa yaml rồi sinh lại.

## Nội dung file sinh

- Công thức: `instance = max(min_instances, ⌈req/s đỉnh có biên an toàn × tỉ lệ lưu lượng ÷ (req/s mỗi instance × mức dùng mục tiêu)⌉)`.
- Tải lấy từ [workload-model.md](workload-model.md).
- Mỗi service một mục `<service> (SVC-xx)`: tỉ lệ lưu lượng, năng lực mỗi instance (kèm link nguồn benchmark), mức dùng mục tiêu, số instance tối thiểu; bảng theo mốc (req/s phần của service, req/s hiệu dụng mỗi instance, instance theo tải, instance cần).

Đầu vào: `compute.yaml` và `assumptions.yaml`. `SVC-xx` ở đây là nhắc đến, định nghĩa ở `06-backend/`; file định nghĩa SVC phải link ngược về file này trong mục "Được dùng bởi".
