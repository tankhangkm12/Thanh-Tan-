# Giả định

<!-- Sinh bởi calc_capacity.py từ capacity/*.yaml. Không sửa tay: sửa yaml rồi chạy lại. -->

Mức dự án: M. Mốc: Ra mắt (launch), 1 năm (1y), 3 năm (3y).

| ID | Mô tả | Đơn vị | Ra mắt | 1 năm | 3 năm | Nguồn |
| --- | --- | --- | --- | --- | --- | --- |
| A-dau | Người dùng hoạt động mỗi ngày | người dùng | 500 | 3,000 | 10,000 | inputs/ba/prd.md mục 4.1 |
| A-requests-per-user | Request mỗi người dùng mỗi ngày | request/người/ngày | 30 | 30 | 30 | inputs/ba/prd.md mục 4.2 |
| A-peak-factor | Hệ số đỉnh so với trung bình | lần | 6 | 6 | 6 | người dùng duyệt ở G1 |
| A-safety-margin | Biên an toàn cộng lên tải đỉnh | tỉ lệ | 0.3 | 0.3 | 0.3 | người dùng duyệt ở G1 |
| A-orders-per-day | Đơn mới mỗi ngày (trung bình trong giai đoạn kết thúc ở mốc) | dòng/ngày | 0 | 1,500 | 5,000 | inputs/ba/prd.md mục 4.3 |
| A-order-items-per-day | Dòng món trong đơn mới mỗi ngày (trung bình trong giai đoạn kết thúc ở mốc) | dòng/ngày | 0 | 4,500 | 15,000 | ước lượng của BA: 3 món mỗi đơn, inputs/ba/prd.md mục 4.3 |
| A-note-bytes | Độ dài trung bình ghi chú đơn | byte | 30 | 30 | 30 | ước lượng của BA |
| A-maxalign | MAXALIGN của PostgreSQL trên máy chủ triển khai (nền tảng: x86_64) | byte | 8 | 8 | 8 | đo bằng pg_controldata trên máy đích, https://www.postgresql.org/docs/16/app-pgcontroldata.html |
| A-heap-bloat | Hệ số phình heap | lần | 1.2 | 1.2 | 1.2 | ước lượng mẫu, vacuum tự động bình thường |
| A-index-bloat | Hệ số phình index | lần | 1.3 | 1.3 | 1.3 | ước lượng mẫu |
| A-wal-bytes | Dung lượng WAL giữ lại | byte | 1,073,741,824 | 1,073,741,824 | 1,073,741,824 | ước lượng mẫu (1 GiB) |
| A-replicas | Số bản sao | bản | 1 | 1 | 1 | ước lượng mẫu, một bản sao cho sẵn sàng cao |
| A-backups | Số bản backup giữ lại | bản | 2 | 2 | 2 | ước lượng mẫu, hai bản gần nhất |
| A-toast-ratio | Tỉ lệ cột độ dài thay đổi vượt ngưỡng TOAST | tỉ lệ | 0 | 0 | 0 | ước lượng mẫu; lý do: ghi chú đơn chỉ vài chục byte, không cột nào tới ngưỡng TOAST |
