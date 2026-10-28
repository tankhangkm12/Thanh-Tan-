# Xong khi: 10-process

Gate: G8 (cùng 08-security và 09-infrastructure). Trọng tâm: Q1, Q2, Q3, Q4, Q6, Q8. Mức S bỏ cả phần này (`profiles.md`).

## delivery.md

- [ ] Mô hình nhánh, quy tắc review, quy tắc đặt phiên bản; tần suất và cửa sổ phát hành có cơ sở (ví dụ tránh giờ cao điểm trong `workload-model.md`).
- [ ] Rollback: điều kiện, người quyết định, thời gian tối đa (phút) khớp `ci-cd.md`.
- [ ] "Tối ưu": chỉ số bằng số, đơn vị, NFR, cách đo (Q2); "Bảo trì" có giờ mỗi tháng kèm cơ sở (Q3).

## data-change.md

- [ ] Mỗi database có dòng dẫn link `migration-strategy.md`; không chép lại quy tắc; thời gian khóa tối đa (giây) khớp file đó.
- [ ] Backfill: lô, tốc độ tối đa, dừng và chạy lại được, cửa sổ chạy, mỗi con số kèm cơ sở; hoặc ghi "không có backfill".
- [ ] Sửa dữ liệu thủ công: điều kiện, người làm và duyệt, ghi vết, sao lưu trước.
- [ ] Có cách xác minh sau thay đổi; "Tối ưu" có chỉ số bằng số (Q2).

## maintenance.md

- [ ] Mỗi công nghệ trong `versions-features.md` có dòng trong lịch nâng cấp, dẫn link tới dòng đó (không chép ngày hết hỗ trợ); khớp `upgrade-roadmap.md` khi có (Q3, Q4).
- [ ] Vá lỗi: tần suất và hạn tối đa (ngày) khớp `secrets-compliance.md` khi có.
- [ ] "Tổng gánh nặng bảo trì": tổng giờ mỗi tháng so với năng lực team ở `C-xx`, có kết luận đủ hay thiếu (Q3).
- [ ] Dọn dẹp có quy tắc và thời gian giữ; "Tối ưu" có chỉ số bằng số.

## operations.md

- [ ] Mức sự cố có thời gian phản hồi (phút) kèm cơ sở; trực và leo thang khớp số người của team.
- [ ] Mỗi cảnh báo mức nghiêm trọng ở `observability.md` có một runbook; hậu kiểm khai rủi ro mới vào sổ (Q6).
- [ ] Diễn tập khôi phục và failover khớp `backup-recovery.md` và `scaling-ha.md`; tiêu chí đạt là số.
- [ ] "Tối ưu": chỉ số bằng số, đơn vị, NFR (Q2).

## Chung

- [ ] Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" với ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần không đạt (`check_numbers.py`).
- [ ] `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py --gate G8 --templates …`, `check_workspace.py` sạch.
- [ ] Rủi ro quy trình (thiếu người, phụ thuộc một người) đã khai vào sổ rủi ro (Q6).
- [ ] Người dùng duyệt (`G8: duyệt`).
