# Thuộc tính chất lượng (NFR)

## Yêu cầu phi chức năng
<!-- required -->

| ID | Thuộc tính | Chỉ tiêu (số + đơn vị) | Cách đo | Mốc | Nguồn |
| --- | --- | --- | --- | --- | --- |
| NFR-001 | Thời gian phản hồi API | p95 dưới 300 ms ở tải đỉnh | log truy cập của order-service | 1y | inputs/ba/prd.md mục 5.1 |
| NFR-002 | Sẵn sàng | 99,5% mỗi tháng | giám sát bên ngoài | launch | inputs/ba/prd.md mục 5.2 |
| NFR-003 | Chịu tải | req/s đỉnh theo workload-model.md, không rớt đơn | kiểm thử tải | 3y | A-peak-factor |

## Sẵn sàng và phục hồi
<!-- required -->

| Chỉ số | Giá trị (số + đơn vị) | Nguồn |
| --- | --- | --- |
| Uptime mục tiêu | 99,5% mỗi tháng | NFR-002 |
| RPO | 15 phút | inputs/ba/prd.md mục 5.3 |
| RTO | 4 giờ | inputs/ba/prd.md mục 5.3 |

## Liên kết
<!-- required -->

NFR-001 và NFR-002 truy về FR và ràng buộc C-001 ở [requirements-trace.md](requirements-trace.md); ngân sách và thời hạn ở [constraints.md](constraints.md).
