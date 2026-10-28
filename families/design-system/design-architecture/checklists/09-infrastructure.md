# Xong khi: 09-infrastructure

Gate: G8 (cùng 08-security và 10-process). Trọng tâm: Q1, Q2, Q3, Q4, Q6, Q8. Mức S bỏ cả phần này (`profiles.md`); mức XL ghi DR chi tiết.

## topology.md

- [ ] Mỗi thành phần hạ tầng chứa ít nhất một container của `containers.md`; mỗi container có chỗ chạy.
- [ ] Cỡ và số lượng dẫn link `compute-sizing.md`, chi phí dẫn link `cost-model.md`; không chép số (Q4).
- [ ] Mạng: phân tách, điểm vào, luồng ra; chu kỳ gia hạn chứng chỉ có cơ sở.
- [ ] "Nâng cấp": phiên bản và ngày hết hỗ trợ khớp `versions-features.md`; "Bảo trì": giờ mỗi tháng kèm cơ sở (Q3).
- [ ] "Tối ưu": chỉ số bằng số, đơn vị, NFR (Q2).

## environments.md

- [ ] Mỗi môi trường có mục đích, cỡ so với production (phần trăm) kèm cơ sở, loại dữ liệu.
- [ ] Dữ liệu thật chỉ ở production, hoặc ẩn danh có quy trình; cấu hình và bí mật theo môi trường khớp `secrets-compliance.md`.
- [ ] Có "Tối ưu" và "Bảo trì".

## scaling-ha.md

- [ ] Autoscale có chỉ số kích hoạt, ngưỡng, min và max khớp `compute-sizing.md`, thời gian nghỉ; hoặc "không autoscale" kèm lý do (Q3).
- [ ] HA: số bản sao, thời gian chuyển sang bản dự phòng (giây), điểm hỏng đơn còn lại trỏ `R-xx` (Q6).
- [ ] DR: RPO và RTO bằng số, truy về NFR, khớp `backup-recovery.md`; có diễn tập. Mức XL ghi thứ tự khôi phục, người quyết định, cách quay lại.
- [ ] Uptime mục tiêu khớp NFR; "Tối ưu" và "Scale, nâng cấp, bảo trì" có số và cơ sở (Q2, Q3).

## observability.md

- [ ] Mỗi SLO truy về NFR; SLI là số đo được; cửa sổ tính có đơn vị.
- [ ] Cảnh báo có ngưỡng bằng số kèm thời gian, người nhận và việc phải làm (link `operations.md`).
- [ ] Mỗi "dấu hiệu sớm" trong sổ rủi ro có cảnh báo ở đây (Q6).
- [ ] RUM và báo lỗi client có nơi nhận khi dự án có frontend.

## ci-cd.md

- [ ] Pipeline có thời gian tối đa mỗi giai đoạn; cổng chất lượng có ngưỡng bằng số (gồm ngân sách hiệu năng frontend và kiểm hợp đồng khi có).
- [ ] Triển khai: chiến lược, điều kiện rollback tự động, thời gian rollback (phút) kèm cơ sở; thay đổi schema theo `migration-strategy.md`.
- [ ] Bí mật trong pipeline khớp `secrets-compliance.md`; có "Tối ưu" và "Nâng cấp và bảo trì".

## Chung

- [ ] Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" với ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần không đạt (`check_numbers.py`).
- [ ] `calc_capacity.py --check`, `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py --gate G8 --templates …`, `check_workspace.py` sạch.
- [ ] Rủi ro hạ tầng mới đã khai vào sổ rủi ro (Q6).
- [ ] Người dùng duyệt (`G8: duyệt`).
