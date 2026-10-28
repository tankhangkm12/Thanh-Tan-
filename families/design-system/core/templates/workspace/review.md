# Báo cáo soát R-<xxx>: <phần>

> Reviewer ghi vào `reviews/R-xxx-<phần>.md`. Reviewer chỉ báo cáo, không sửa bản nháp. Chỉ đọc bản nháp, template, checklist, nguồn gốc (BA, `capacity/assumptions.yaml`) và kết quả script; không đọc brief hay lý luận của Designer. Báo cáo này **không phải duyệt gate**: chỉ người dùng duyệt.

- **Gate:** <G0–G10>
- **Phần soát:** <đường dẫn các file bản nháp>
- **Ngày soát:** <YYYY-MM-DD>
- **Model Designer của phần này:** <tên>
- **Model Reviewer:** <tên, phải khác model Designer>
- **Trọng tâm gate:** <các Q ghi trong `stages.md` cho gate này; Q6 và Q8 luôn là trọng tâm>

## Kết quả soát

- **Lỗi chặn:** <số lượng>
- **Góp ý:** <số lượng>
- **Kết luận:** <không còn lỗi chặn | còn <n> lỗi chặn, gate chưa qua được>

## Script đã chạy lại

<!-- Reviewer tự chạy lại, không tin báo cáo của Designer. Kết quả đầy đủ ở `checks/`. -->

| Script | Kết quả | File kết quả |
| --- | --- | --- |
| <check_workspace.py> | <sạch | n lỗi> | <checks/workspace-YYYY-MM-DD.md> |

## Soát theo Q1–Q8

<!-- Soát đủ cả tám. Trọng tâm gate đánh dấu ★. Mỗi nhận xét có link file và dòng. -->

| Q | Tiêu chí | Trọng tâm | Kết quả | Ghi chú |
| --- | --- | --- | --- | --- |
| Q1 | Đúng FR / NFR / ràng buộc | <★ | —> | <đạt | có lỗi chặn | chỉ góp ý> | <...> |
| Q2 | Tối ưu theo từng tầng | | | |
| Q3 | Mở rộng, nâng cấp, bảo trì | | | |
| Q4 | Số liệu thật | | | |
| Q5 | Kiểu dữ liệu, kiến trúc, stack, phiên bản | | | |
| Q6 | Quản lý rủi ro | ★ | | |
| Q7 | Frontend: kiến trúc sâu, không đụng GUI | | <không áp dụng khi hồ sơ bỏ frontend> | |
| Q8 | Phù hợp với dự án | ★ | | |

## Lỗi chặn

<!-- Gate không qua cho tới khi sửa. Gồm mọi lỗi mà quality-criteria.md liệt kê là "Lỗi chặn" và mọi lỗi do script báo. Không có thì ghi "không có". -->

### B-<01>: <tên ngắn>

- **Tiêu chí:** <Q?>
- **Vị trí:** <đường dẫn:dòng>
- **Vấn đề:** <điều sai, trích đúng đoạn>
- **Vì sao chặn:** <điều khoản trong quality-criteria.md hoặc script nào báo>
- **Hướng sửa:** <gợi ý ngắn; Designer quyết cách sửa>

## Góp ý

<!-- Không chặn gate; Designer xem xét, người dùng quyết có sửa không. Không có thì ghi "không có". -->

### S-<01>: <tên ngắn>

- **Tiêu chí:** <Q?>
- **Vị trí:** <đường dẫn:dòng>
- **Góp ý:** <...>

## Soát sổ rủi ro (Q6)

- **Rủi ro mới từ giai đoạn vừa làm đã khai chưa:** <đã đủ | thiếu: ...>
- **Điểm cần chấm lại:** <R-xx: lý do, hoặc không có>
- **Rủi ro ≥ 15 điểm:** <đã giảm thiểu hoặc có dòng chấp nhận theo ID ở `risks/acceptance.md` | còn tồn: R-xx>
