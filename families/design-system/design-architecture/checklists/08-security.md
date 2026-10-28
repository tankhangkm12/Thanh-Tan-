# Xong khi: 08-security

Gate: G8 (cùng 09-infrastructure và 10-process). Trọng tâm: Q1, Q3, Q4, Q6, Q8. Mức S bỏ cả phần này (`profiles.md`).

## authz-matrix.md

- [ ] Mỗi vai trò truy về FR; mọi API của `06-backend/` nằm trong ít nhất một hàng của ma trận, mọi màn hình `SCR-xx` có quyền vào (khớp `auth-session.md` của app) (Q1).
- [ ] Mỗi ô là `được`, `không` hoặc `có điều kiện`, và ô `có điều kiện` có quy tắc ở "Quy tắc theo dữ liệu".
- [ ] Quy tắc theo dữ liệu truy về FR, NFR hoặc C; cách kiểm khớp `cross-cutting.md`.
- [ ] Có "Tối ưu" và "Bảo trì" (giờ mỗi tháng kèm cơ sở) (Q2, Q3).

## threat-model.md

- [ ] Mỗi tài sản có nơi lưu bằng ID thật (`TBL-`, `BKT-`) hoặc kho bí mật, và truy về FR hoặc C.
- [ ] Mỗi mối đe dọa có tài sản, biện pháp, nơi biện pháp nằm, và `R-xx` có trong sổ rủi ro (Q6); điểm không chấm lại ở đây.
- [ ] Ranh giới tin cậy có cơ chế kiểm soát cho từng ranh giới.
- [ ] "Rủi ro còn lại": mỗi dòng trỏ `R-xx`; từ 15 điểm thì đã được người dùng chấp nhận (`risks/acceptance.md`).

## secrets-compliance.md

- [ ] Bí mật có nơi lưu, chu kỳ xoay (ngày) kèm cơ sở; không có bí mật trong mã, log hay image.
- [ ] Mã hóa khi truyền và khi lưu, có người giữ khóa và chu kỳ xoay.
- [ ] Dữ liệu cá nhân: thời gian giữ khớp `partitioning-retention.md` và `object-storage.md`; hoặc ghi "không lưu" kèm nguồn.
- [ ] Tuân thủ truy về `C-xx` và văn bản chính thức; "không có quy định riêng" kèm nguồn (Q1, Q4).
- [ ] Hạn vá lỗ hổng (ngày) theo mức nghiêm trọng có cơ sở; có "Tối ưu" và "Bảo trì" (Q2, Q3).

## Chung

- [ ] Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" với ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần không đạt (`check_numbers.py`).
- [ ] `check_links.py`, `check_numbers.py`, `check_profile.py --gate G8 --templates …`, `check_workspace.py` sạch.
- [ ] Rủi ro bảo mật mới đã khai vào sổ rủi ro (Q6).
- [ ] Người dùng duyệt (`G8: duyệt`).
