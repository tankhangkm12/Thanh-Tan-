# Xong khi: 12-roadmap

Gate: G9 (cùng 11-risks). Trọng tâm: Q1, Q3, Q4, Q8. Mức S chỉ giữ `implementation-plan.md`; `scaling-stages.md` và `upgrade-roadmap.md` có từ mức M (`profiles.md`).

## scaling-stages.md

- [ ] Mỗi giai đoạn có ngưỡng bắt đầu là số có đơn vị, lấy từ `workload-model.md` hoặc `compute-sizing.md` (dẫn link, không chép lại số tính) (Q3, Q4).
- [ ] Khớp mục "Giai đoạn scale" của `architecture-style.md` và "Ngưỡng lên giai đoạn sau" của các `scaling.md`.
- [ ] Chi phí thêm dẫn link `cost-model.md`.
- [ ] Mỗi dấu hiệu cần chuyển giai đoạn có ngưỡng cảnh báo và cảnh báo tương ứng ở `observability.md`; có thứ tự thay đổi để chuyển không gián đoạn.

## upgrade-roadmap.md

- [ ] Mỗi công nghệ có dòng trong `versions-features.md` đều có ở đây, sắp theo ngày hết hỗ trợ gần nhất trước; ngày hết hỗ trợ dẫn link, không chép (`check_versions.py` kiểm ở nguồn).
- [ ] Hạn xong của mỗi lần nâng cấp trước ngày hết hỗ trợ; công sức ước tính (giờ) có cơ sở và khớp `maintenance.md` (Q3).
- [ ] Thay đổi phá vỡ cần xử lý có link ghi chú phát hành; phụ thuộc giữa các lần nâng cấp khớp `compatibility.md`.
- [ ] Công nghệ hết hỗ trợ trong 12 tháng có `R-xx` trong sổ rủi ro.

## implementation-plan.md

- [ ] Mỗi service, app, database và phần hạ tầng cần dựng có ít nhất một gói; mỗi gói liệt kê tài liệu đầu vào bằng link tới file thật trong `architecture/` (Q1).
- [ ] Mỗi FR trong `requirements-trace.md` thuộc ít nhất một gói.
- [ ] Phụ thuộc giữa gói không có vòng; tiêu chí hoàn thành kiểm được và truy về NFR.
- [ ] Mục "Nguyên tắc cho agent dev" giữ nguyên bốn quy tắc cố định của template (tài liệu là nguồn sự thật, mâu thuẫn thì hỏi, không đổi phiên bản, giao diện theo designer); mục con "Áp dụng cho dự án" đã viết riêng (câu hỏi ghi ở đâu và ai trả lời, ai duyệt đổi phiên bản, tài liệu designer ở đâu), không còn dòng giữ chỗ (`check_profile.py` báo `unfilled-required-section`).

## Chung

- [ ] Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" với ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần không đạt (`check_numbers.py`).
- [ ] `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py --gate G9 --templates …`, `check_workspace.py` sạch.
- [ ] Người dùng duyệt (`G9: duyệt`).
