# Dung lượng object storage (storage-sizing.md)

> Template của design-architecture, **chỉ mô tả**. File này do `calc_capacity.py` sinh từ `capacity/*.yaml` của workspace (schema: core/workflow/capacity-schema.md); Designer không viết tay, không có mục `<!-- required -->`. Orchestrator chạy script ở G5, G7 và G10; Reviewer chạy `calc_capacity.py --check`. `check_numbers.py` tính lại và báo `generated-file-edited` nếu file bị sửa tay. Muốn đổi số thì sửa yaml rồi sinh lại.

## Nội dung file sinh

- Công thức: `file đang giữ = min(file đã tải lên, file/ngày × số ngày giữ)`; `dung lượng = file đang giữ × kích thước trung bình`; `băng thông ra/tháng = lượt xem/ngày × kích thước × (365/12)`.
- Mỗi bucket một mục `<bucket> (BKT-xx)`: tham số (file/ngày, kích thước trung bình, thời gian giữ, lượt xem/ngày) và bảng theo mốc (file đã tải lên, file đang giữ, dung lượng lưu, lượt xem, băng thông ra/tháng).

Đầu vào: `storage.yaml` và `assumptions.yaml`. Dự án không có object storage (không có `storage.yaml`, hoặc `buckets: {}`) thì file ghi "Không có object storage" và chi phí object storage, băng thông ra bằng 0.
