# Quan sát: SLO, metric, cảnh báo

## SLI và SLO
<!-- required -->

| Luồng hoặc dịch vụ | SLI | SLO (số + đơn vị) | Cửa sổ tính (ngày) | NFR |
| --- | --- | --- | --- | --- |
| đặt đơn (FL-001) | tỉ lệ request thành công | 99,5% | 30 | NFR-002 |
| đặt đơn (FL-001) | p95 độ trễ | 300 ms | 30 | NFR-001 |
| xem trạng thái đơn (FL-002) | p95 độ trễ | 100 ms | 30 | NFR-001 |

## Metric, log và trace
<!-- required -->

| Loại | Thu gì | Công cụ | Thời gian giữ (ngày) | Cơ sở |
| --- | --- | --- | --- | --- |
| metric hạ tầng | CPU, bộ nhớ, ổ đĩa của máy ảo; độ trễ nhân bản PostgreSQL | giám sát của nhà cung cấp hạ tầng | 90 | C-001 |
| log truy cập | API, mã HTTP, thời gian xử lý, correlationId | log JSON của order-service | 30 | C-001 |
| kiểm tra từ bên ngoài | tình trạng cổng 443 | kiểm tra HTTP định kỳ từ bên ngoài | 90 | NFR-002 |

## Cảnh báo
<!-- required -->

| Cảnh báo | Điều kiện (ngưỡng + thời gian) | Mức | Ai nhận | Việc phải làm | Dấu hiệu sớm của |
| --- | --- | --- | --- | --- | --- |
| CPU máy ảo cao | CPU trên 70% trong 15 phút (NFR-001) | cảnh báo | nhân viên vận hành, kênh chat của team | theo [operations.md](../10-process/operations.md) | R-003 |
| lỗi máy chủ tăng | tỉ lệ 5xx trên 1% trong 5 phút (NFR-002) | khẩn | nhân viên vận hành, kênh chat của team | theo [operations.md](../10-process/operations.md) | không |
| ngân sách hiệu năng bị vượt | bước đo hiệu năng trong CI báo LCP trên 2,5 s ở mọi lần chạy trong 7 ngày liên tiếp (NFR-001) | cảnh báo | thành viên frontend | theo [operations.md](../10-process/operations.md) | R-001 |
| dò mã tra cứu | một IP nhận trên 20 lỗi không tìm thấy trong 5 phút (NFR-003) | cảnh báo | nhân viên vận hành | theo [operations.md](../10-process/operations.md) | R-004 |
| khôi phục thử vượt RTO | thời gian khôi phục trong buổi diễn tập trên 240 phút (NFR-002) | cảnh báo | nhân viên vận hành | theo [operations.md](../10-process/operations.md) | R-002 |
| khóa quá hạn xoay | một khóa nhân viên quá 90 ngày chưa xoay (C-002) | cảnh báo | nhân viên vận hành | theo [operations.md](../10-process/operations.md) | R-005 |

## Báo lỗi và đo thực tế phía client
<!-- required -->

- Nơi nhận: log truy cập của order-service; không dùng công cụ báo lỗi bên thứ ba
- Cảnh báo liên quan: lỗi máy chủ tăng, ngân sách hiệu năng bị vượt

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| số cảnh báo giả mỗi tuần | 2 | NFR-002 | lịch sử cảnh báo |
| thời gian từ lúc sự cố đến lúc phát hiện (p95) | 5 phút | NFR-002 | nhật ký sự cố |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| rà ngưỡng cảnh báo, dọn dữ liệu quan sát cũ | mỗi tháng | 1 giờ | C-002 |
