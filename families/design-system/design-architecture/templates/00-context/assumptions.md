# Giả định

> Template của design-architecture. **File này do script sinh, không viết tay.** Nguồn duy nhất của giả định là `.agent-workspace/capacity/assumptions.yaml` (schema: core/workflow/capacity-schema.md). Orchestrator chạy `calc_capacity.py --assumptions-only` ở G1 (và `calc_capacity.py` đầy đủ từ G5) để sinh file này; `check_numbers.py` báo lỗi nếu file lệch yaml. Muốn đổi giả định thì sửa yaml rồi sinh lại.

Nội dung file sinh gồm:

- đầu file: tiêu đề "Giả định", dòng đánh dấu file sinh, mức dự án và các mốc;
- một bảng `| ID | Mô tả | Đơn vị | <các mốc> | Nguồn |`, mỗi giả định một dòng với ID `A-<tên>` ở ô đầu dòng (đây là nơi **duy nhất** định nghĩa `A-xx`);
- giả định không có thật (0, hệ số phình 1) ghi thêm "lý do" ở cột Nguồn; MAXALIGN ghi thêm nền tảng.

Không có mục `<!-- required -->` vì nội dung do script bảo đảm.
