# Xong khi: 00-context

Gate: G0 (`project-profile.md`) và G1 (các file còn lại). Trọng tâm G1: Q1, Q4, Q6, Q8. Reviewer đánh dấu từng dòng; thiếu một dòng là lỗi chặn trừ khi ghi "góp ý".

## project-profile.md (G0)

- [ ] Có dòng `Mức: S|M|L|XL` với đúng một mức, kèm lý do dẫn số trong bảng Hồ sơ (Q8).
- [ ] Bảng Hồ sơ đủ 7 mục (người dùng, dữ liệu, mức độ quan trọng, team, ngân sách, thời hạn, tuân thủ), mỗi mục có số kèm đơn vị và nguồn.
- [ ] Bảng `| Phần | Áp dụng |` đủ 13 dòng `00-context` … `12-roadmap`, mỗi dòng `có` / `rút gọn` / `bỏ` và có lý do.
- [ ] Các phần bị bỏ khớp bảng mức trong [profiles.md](../profiles.md); không có phần bỏ mà vẫn có file.
- [ ] `check_profile.py --gate G0` sạch.

## requirements-trace.md

- [ ] Mọi FR của BA có một dòng, ID `FR-…` ở ô đầu dòng, nguồn BA ghi file và mục.
- [ ] Mọi FR có ít nhất một NFR hoặc ràng buộc liên quan, hoặc ghi rõ "không có" kèm lý do (Q1).
- [ ] Mọi NFR xuất hiện ở mục "Phủ yêu cầu phi chức năng" (mỗi NFR một dòng gạch đầu dòng).
- [ ] Cột FL, SVC, TBL/BKT: "—" ở G1; điền đủ ở G6 và G7 (không FR nào không có luồng ở G6).
- [ ] Không định nghĩa `NFR-xx` hay `C-xx` ở ô đầu dòng bảng này.

## quality-attributes.md

- [ ] Mọi NFR có chỉ tiêu bằng số, đơn vị, cách đo và mốc (Q4).
- [ ] Không có từ mơ hồ ("nhanh", "lớn", "đủ dùng", "scale tốt") thiếu số.
- [ ] Uptime, RPO, RTO có giá trị và nguồn NFR.
- [ ] Số đầu vào (DAU, tăng trưởng…) trỏ tới `A-xx`, không lặp giá trị.
- [ ] `check_numbers.py` sạch.

## constraints.md

- [ ] Mọi ràng buộc có `C-…` ở ô đầu dòng (chỉ file này định nghĩa `C-xx`), loại, giá trị kèm đơn vị và nguồn.
- [ ] Ngân sách, team, hạ tầng, pháp lý, thời hạn đều có dòng, hoặc ghi "không có" kèm nguồn.
- [ ] Mục "Ràng buộc có thể nới" có đủ hoặc ghi rõ không có; ID `C-xx` không nằm ở ô đầu dòng của bảng này.

## assumptions.md

- [ ] Là bản sinh từ `capacity/assumptions.yaml` (`calc_capacity.py --assumptions-only`), không sửa tay; `check_numbers.py` không báo lệch.
- [ ] Mỗi giả định có nguồn hoặc lý do; giả định "không có" (0, phình = 1) có lý do (Q4, Q6).
- [ ] Bao phủ mọi mốc của mức dự án (S: ra mắt, 1 năm; M: + 3 năm; L: + 5 năm; XL: + đỉnh tải).

## glossary.md

- [ ] Mọi thuật ngữ nghiệp vụ dùng trong FR có định nghĩa một câu; không thuật ngữ nào định nghĩa hai lần.

## Chung cho cả phần

- [ ] `check_links.py`, `check_numbers.py`, `check_profile.py --gate G1 --templates …`, `check_workspace.py` sạch.
- [ ] Rủi ro phát sinh (thiếu thông tin BA, giả định mong manh) đã khai vào sổ rủi ro (Q6).
