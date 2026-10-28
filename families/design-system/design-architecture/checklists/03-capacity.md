# Xong khi: 03-capacity

Gate: G5 (chạy lại ở G7 và G10). Trọng tâm G5: Q2, Q4, Q6, Q8. Cả năm file do `calc_capacity.py` sinh: Designer ghi `capacity/*.yaml`, không ghi file ở phần này.

## Đầu vào (capacity/*.yaml)

- [ ] `assumptions.yaml` phủ mọi mốc của mức dự án (S: ra mắt, 1 năm; M: thêm 3 năm; L: thêm 5 năm; XL: thêm đỉnh tải); mỗi giả định có nguồn hoặc lý do.
- [ ] Mỗi database khai đủ bảy khóa: hệ số phình heap và index, WAL, số bản sao, số backup, tỉ lệ TOAST, MAXALIGN (có nền tảng và nguồn); giá trị "không có" (0, phình = 1) có `reason`.
- [ ] `tables.yaml`: mỗi cột có kiểu, `reason`; kiểu chọn theo số (kiểu nhỏ nhất đủ cho mốc xa nhất cộng biên an toàn); cột tăng dần đánh dấu `counter`.
- [ ] `pricing.yaml`: mọi đơn giá có link trang giá chính thức và ngày tra cứu; `compute.yaml`: năng lực mỗi instance có nguồn benchmark.
- [ ] `db-constants/<db>-<major>.yaml` do Researcher ghi, mọi hằng số có link nguồn, link mã nguồn trỏ tag phát hành.

## Đầu ra

- [ ] Cả năm file `workload-model.md`, `data-sizing.md`, `storage-sizing.md`, `compute-sizing.md`, `cost-model.md` có mặt ở mọi mức và do script sinh, không sửa tay (Q4). "Rút gọn" ở mức S nghĩa là ít mốc hơn (chỉ ra mắt và 1 năm), vẫn đủ 5 file.
- [ ] `calc_capacity.py` đầy đủ chạy sạch; `calc_capacity.py --check` (Reviewer) báo khớp.
- [ ] Mỗi bảng trong `tables.md` có cặp `BEGIN/END:calc` và số khớp bản tính lại.
- [ ] `data-sizing.md` có hai con số mỗi database (dung lượng logic, dung lượng cần cấp) và mục TOAST nói rõ chưa mô hình.
- [ ] Chi phí lưu trữ database tính trên dung lượng cần cấp; tổng chi phí từng mốc so được với ngân sách `C-xx`.
- [ ] Người dùng duyệt tải, dung lượng, chi phí từng mốc.

## Chung

- [ ] `check_numbers.py` không báo `generated-file-edited`, `calc-block-edited`, `generated-file-unverified`.
- [ ] Số liệu làm lộ rủi ro (kiểu dữ liệu sắp tràn, chi phí sát ngân sách) đã khai vào sổ rủi ro (Q6).
- [ ] Phần tối ưu ở lớp lưu trữ/tính toán có chỉ số bằng số ở `06-backend` và `07-data` (Q2), lấy từ các số trong phần này.
