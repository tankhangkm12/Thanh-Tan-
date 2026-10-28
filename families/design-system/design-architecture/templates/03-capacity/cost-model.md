# Mô hình chi phí (cost-model.md)

> Template của design-architecture, **chỉ mô tả**. File này do `calc_capacity.py` sinh từ `capacity/*.yaml` của workspace (schema: core/workflow/capacity-schema.md); Designer không viết tay, không có mục `<!-- required -->`. Orchestrator chạy script ở G5, G7 và G10; Reviewer chạy `calc_capacity.py --check`. `check_numbers.py` tính lại và báo `generated-file-edited` nếu file bị sửa tay. Muốn đổi số thì sửa yaml rồi sinh lại.

## Nội dung file sinh

- Chi phí theo tháng, một đơn vị tiền tệ; 1 GB trong bảng giá là bao nhiêu byte (kèm nguồn).
- Mục "Đơn giá": mỗi mục giá có mô tả, đơn vị, đơn giá, link trang giá chính thức và ngày tra cứu.
- Mục "Chi phí mỗi tháng": bảng `| Khoản | <các mốc> |` gồm compute, lưu trữ database (tính trên **dung lượng cần cấp**), object storage, băng thông ra, tổng. Mốc đỉnh tải chỉ tính compute.

Đầu vào: `pricing.yaml`, kết quả của bốn file trên. Chi phí ngoài hạ tầng (giấy phép, SaaS) không nằm ở đây mà ở [cost-licensing.md](../02-tech-stack/cost-licensing.md).
