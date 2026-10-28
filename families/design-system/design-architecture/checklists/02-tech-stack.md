# Xong khi: 02-tech-stack

Gate: G2 (`selection-criteria.md`) và G4 (các file còn lại). Trọng tâm G2: Q1, Q5, Q6, Q8. Trọng tâm G4: Q4, Q5, Q6, Q8. Reviewer đánh dấu từng dòng.

## selection-criteria.md (G2)

- [ ] Mọi TC có `TC-…` ở ô đầu dòng của bảng loại trừ hoặc bảng có trọng số (chỉ file này định nghĩa `TC-xx`).
- [ ] Mỗi TC truy về ít nhất một FR, NFR hoặc `C-xx` đã được định nghĩa (Q1); TC không có nguồn bị gạt.
- [ ] Không có tên công nghệ hay ứng viên nào trong file (duyệt trước ứng viên).
- [ ] Tiêu chí loại trừ có ngưỡng bằng số hoặc "có / không" kiểm được; tiêu chí có trọng số có trọng số và cách chấm 0–5.
- [ ] Mỗi TC có mục "Áp dụng cho"; trọng số khớp `brief.md` của hội đồng sau này.
- [ ] Người dùng duyệt tiêu chí và trọng số (`G2: duyệt`).

## README.md (G4)

- [ ] Một bảng duy nhất có cột Lớp, Công nghệ, Phiên bản, TC đáp ứng; mỗi công nghệ một dòng.
- [ ] Mỗi phiên bản là major.minor (lớp third-party được thêm `YYYY-MM-DD` hoặc "SaaS, không phiên bản"); không `latest`.
- [ ] Mỗi công nghệ có dòng cùng tên và cùng phiên bản trong `versions-features.md`.
- [ ] Mỗi quyết định `D-xxx` của lớp có dòng trong mục "Quyết định", kèm rủi ro.
- [ ] Mục "Kiểm tra chéo" tóm tắt kết quả, link tới compatibility, cost-licensing, team-readiness.

## layers/{layer}.md (G4)

- [ ] Mỗi lớp có trong README có đúng một file; lớp không dùng không có file.
- [ ] Nhắc ít nhất một `TC-xx` đã định nghĩa (`check_links.py` báo `layer-without-tc`); không đặt TC ở ô đầu dòng.
- [ ] Mục "Tối ưu": mỗi chỉ số có số, đơn vị, NFR và cách đo (Q2).
- [ ] Mục "Scale, nâng cấp, bảo trì": mỗi công nghệ đủ đơn vị scale, giới hạn, ngưỡng lên giai đoạn sau, đường nâng cấp, giờ bảo trì mỗi tháng và cơ sở ước tính (Q3).
- [ ] Mục "Rủi ro" liệt kê `R-xx` đã khai (Q6).
- [ ] Mọi dữ kiện kèm link nguồn chính thức (Q4).

## versions-features.md (G4)

- [ ] Một bảng duy nhất có cột "Công nghệ"; đủ cột phiên bản chốt, vòng đời (hết hỗ trợ), tính năng, giới hạn và lỗi đã biết, thay đổi phá vỡ, tương thích, rủi ro.
- [ ] Mỗi dòng: major.minor, ngày hết hỗ trợ (hoặc "chưa công bố") kèm link http(s) chính thức; ngày hết hỗ trợ sau ngày phát hành.
- [ ] Không có phiên bản đã hết hỗ trợ; phiên bản hết hỗ trợ trong 12 tháng có link `R-xx` ở cột Rủi ro.
- [ ] Mỗi tính năng dự án dựa vào ghi phiên bản tối thiểu; mỗi giới hạn có link issue hoặc release note.
- [ ] Mục "Chính sách bản vá" có đủ các lớp.
- [ ] `check_versions.py` sạch.

## compatibility.md, cost-licensing.md, team-readiness.md, exit-strategy.md (G4)

- [ ] compatibility: mọi cặp lớp liền kề có dòng, kết quả có bằng chứng; xung đột có cách xử lý và `R-xx` (hoặc ghi "không có xung đột" kèm ngày).
- [ ] cost-licensing: giấy phép từng công nghệ có link; đơn giá có nguồn và ngày tra cứu; tổng chi phí từng mốc so với `C-xx` ngân sách.
- [ ] team-readiness: khoảng trống kỹ năng có số; mỗi khoảng trống có kế hoạch và `R-xx` (Q6).
- [ ] exit-strategy: mỗi công nghệ có phương án thay thế, chi phí chuyển và điều kiện kích hoạt bằng số (Q3).

## Chung cho cả phần

- [ ] Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" với ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần không đạt (`check_numbers.py`).
- [ ] `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py --gate G4 --templates …`, `check_workspace.py` sạch.
- [ ] Mỗi quyết định và mỗi dòng phiên bản đã sinh rủi ro vào sổ (Q6).
- [ ] Mức XL: mỗi lớp bắt buộc có spike `đạt` trên đề bài hiện tại.
