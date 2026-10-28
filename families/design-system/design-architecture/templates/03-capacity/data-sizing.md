# Dung lượng dữ liệu (data-sizing.md)

> Template của design-architecture, **chỉ mô tả**. File này do `calc_capacity.py` sinh từ `capacity/*.yaml` của workspace (schema: core/workflow/capacity-schema.md); Designer không viết tay, không có mục `<!-- required -->`. Orchestrator chạy script ở G5, G7 và G10; Reviewer chạy `calc_capacity.py --check`. `check_numbers.py` tính lại và báo `generated-file-edited` nếu file bị sửa tay. Muốn đổi số thì sửa yaml rồi sinh lại.

## Nội dung file sinh

- Công thức: `dung lượng logic = số trang × kích thước trang`; byte/dòng gồm đầu dòng, dữ liệu có đệm căn lề (căn lên MAXALIGN) và con trỏ dòng; index tính theo mục B-tree.
- Mục "Hằng số đã dùng": hằng số của database (phần đầu dòng, căn lề, fillfactor…) và kiểu dữ liệu, mỗi dòng có link nguồn chính thức.
- Mỗi bảng một mục `<db> · <bảng> (TBL-xx)`: bố cục dòng (cột, kiểu, byte, căn lề, đệm, lý do), index, bảng theo mốc (số dòng, dung lượng heap, index), và kiểm tra cột tăng dần (kiểu đủ hay không, kiểu nhỏ nhất đủ).
- Mỗi database một mục "dung lượng cần cấp": **hai con số**, dung lượng logic và dung lượng cần cấp = `(heap × hệ số phình heap + index × hệ số phình index + WAL) × (1 + bản sao) + backup × dữ liệu sau phình`.
- Mục TOAST: nói rõ TOAST chưa được mô hình và ghi tỉ lệ cột vượt ngưỡng đã khai.

Đầu vào: `tables.yaml`, `db-constants/<db>-<major>.yaml`, `database_assumptions` trong `assumptions.yaml`. Số của từng bảng cũng nằm trong khối `BEGIN/END:calc` của [tables.md](../07-data/databases/{db}/tables.md).
