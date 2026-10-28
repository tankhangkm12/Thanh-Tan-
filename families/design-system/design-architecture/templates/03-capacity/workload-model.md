# Mô hình tải (workload-model.md)

> Template của design-architecture, **chỉ mô tả**. File này do `calc_capacity.py` sinh từ `capacity/*.yaml` của workspace (schema: core/workflow/capacity-schema.md); Designer không viết tay, không có mục `<!-- required -->`. Orchestrator chạy script ở G5, G7 và G10; Reviewer chạy `calc_capacity.py --check`. `check_numbers.py` tính lại và báo `generated-file-edited` nếu file bị sửa tay. Muốn đổi số thì sửa yaml rồi sinh lại.

## Nội dung file sinh

- Đầu file: dòng đánh dấu file sinh, mức dự án, các mốc (S: ra mắt, 1 năm; M: thêm 3 năm; L: thêm 5 năm; XL: thêm đỉnh tải), quy ước 1 năm = 365 ngày, 1 ngày = 86 400 giây.
- Công thức: `req/s đỉnh = DAU × request/người/ngày ÷ 86 400 × hệ số đỉnh`, rồi `× (1 + biên an toàn)`.
- Một bảng `| Đại lượng | Công thức | <các mốc> |`: DAU, request/người/ngày, request/ngày, req/s trung bình, hệ số đỉnh, req/s đỉnh, biên an toàn, req/s đỉnh có biên an toàn. Mỗi giả định ghi ID `A-xx` và link [assumptions.md](../00-context/assumptions.md).

Đầu vào: khối `workload` và các giả định của `assumptions.yaml`.
