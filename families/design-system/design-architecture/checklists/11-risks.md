# Xong khi: 11-risks

Gate: G9 (cùng 12-roadmap). Trọng tâm: Q6, Q1, Q8. Sổ rủi ro có ở mọi mức; mức S rút gọn: chỉ ghi rủi ro từ 8 điểm trở lên. Sổ rủi ro được khai dần từ G2, G9 là lần rà cuối.

## risk-register.md

- [ ] File chỉ có một bảng (bảng rủi ro); mọi nội dung khác là danh sách. Bảng có đủ cột ID, "Khả năng × Tác động", "Thành phần liên quan", "Trạng thái" (`check_workspace.py` báo `risk-register-malformed`, `check_links.py` báo `risk-without-components-column`).
- [ ] `R-xx` định nghĩa ở ô đầu dòng, chỉ ở file này; không trùng (`duplicate-id`).
- [ ] Mỗi rủi ro: mô tả cụ thể kèm hậu quả, nhóm, điểm ghi dạng `4 × 3 = 12` (mỗi thang 1–5, điểm đúng bằng tích), dấu hiệu sớm bằng số có ngưỡng, giảm thiểu, phương án dự phòng.
- [ ] Cột "Thành phần liên quan" có ID `SVC-`/`TBL-`/`BKT-`/`EVT-`/`API-` hoặc link tới file trong `02-tech-stack/` (Q6; `check_links.py` báo `risk-without-components`).
- [ ] Trạng thái là một trong: đang theo dõi, đang giảm thiểu, đã chấp nhận, đã đóng.
- [ ] Từ 8 điểm: có giảm thiểu và dấu hiệu sớm; từ 15 điểm: giảm thiểu hoặc `đã chấp nhận` với dòng tương ứng trong `risks/acceptance.md` (R-xx, điểm khớp, nguyên văn `R-xx: chấp nhận`, ngày) và ngược lại (`check_workspace.py` báo `acceptance-missing`, `acceptance-orphan`, `risk-unresolved` từ G9).
- [ ] Dấu hiệu sớm có ô cơ sở (ID hoặc link) cho ngưỡng và có cảnh báo trong `observability.md` (mức S: cách theo dõi thủ công).
- [ ] Mọi rủi ro đã nêu ở brief quyết định, `versions-features.md`, `threat-model.md`, `scaling-ha.md`, `layers/{layer}.md` đều có trong sổ (Q6).
- [ ] Mọi rủi ro từ 15 điểm trở lên đã được giảm thiểu, chấp nhận hoặc đóng trước khi phát hành.

## Chung

- [ ] Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" với ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần không đạt (`check_numbers.py`).
- [ ] `check_links.py`, `check_numbers.py`, `check_profile.py --gate G9 --templates …`, `check_workspace.py` sạch.
- [ ] Người dùng duyệt (`G9: duyệt`).
