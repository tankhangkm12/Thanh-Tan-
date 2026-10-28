# Mô hình tải

<!-- Sinh bởi calc_capacity.py từ capacity/*.yaml. Không sửa tay: sửa yaml rồi chạy lại. -->

Mức dự án: M. Mốc: Ra mắt (launch), 1 năm (1y), 3 năm (3y). 1 năm = 365 ngày, 1 tháng = 365/12 ngày, 1 ngày = 86,400 giây.

Công thức: `req/s đỉnh = DAU × request/người/ngày ÷ 86,400 × hệ số đỉnh`; có biên an toàn: `× (1 + biên an toàn)`.
Giả định (xem [assumptions.md](../00-context/assumptions.md)): A-dau, A-requests-per-user, A-peak-factor, A-safety-margin.

| Đại lượng | Công thức | Ra mắt | 1 năm | 3 năm |
| --- | --- | --- | --- | --- |
| DAU (A-dau) | giả định | 500 | 3,000 | 10,000 |
| Request/người/ngày (A-requests-per-user) | giả định | 30 | 30 | 30 |
| Request/ngày | DAU × request/người/ngày | 15,000 | 90,000 | 300,000 |
| req/s trung bình | request/ngày ÷ 86,400 | 0.17 | 1.04 | 3.47 |
| Hệ số đỉnh (A-peak-factor) | giả định | 6.00 | 6.00 | 6.00 |
| req/s đỉnh | req/s trung bình × hệ số đỉnh | 1.04 | 6.25 | 20.83 |
| Biên an toàn (A-safety-margin) | giả định | 0.30 | 0.30 | 0.30 |
| req/s đỉnh có biên an toàn | req/s đỉnh × (1 + biên an toàn) | 1.35 | 8.12 | 27.08 |
