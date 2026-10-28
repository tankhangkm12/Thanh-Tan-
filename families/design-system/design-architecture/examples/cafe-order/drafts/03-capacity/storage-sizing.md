# Dung lượng object storage

<!-- Sinh bởi calc_capacity.py từ capacity/*.yaml. Không sửa tay: sửa yaml rồi chạy lại. -->

Mức dự án: M. Mốc: Ra mắt (launch), 1 năm (1y), 3 năm (3y). 1 năm = 365 ngày, 1 tháng = 365/12 ngày, 1 ngày = 86,400 giây.

Công thức: `file đang giữ = min(file đã tải lên, file/ngày × số ngày giữ)`; `dung lượng = file đang giữ × kích thước trung bình`; `băng thông ra/tháng = lượt xem/ngày × kích thước × (365/12)`.
Giả định xem [assumptions.md](../00-context/assumptions.md).

Không có object storage: `storage.yaml` không khai bucket nào (hoặc không có file). Dung lượng lưu, băng thông ra và chi phí của chúng bằng 0.
