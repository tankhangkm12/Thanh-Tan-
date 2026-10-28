# Môi trường

## Danh sách môi trường
<!-- required -->

| Môi trường | Mục đích | Cỡ so với production (phần trăm) | Dữ liệu | Ai truy cập | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| dev | phát triển trên máy lập trình viên | 25% | giả lập | lập trình viên | D-004 |
| staging | kiểm thử trước khi phát hành, dựng tạm trên runner CI rồi hủy | 50% | giả lập | team | C-001 |
| production | chạy thật | 100% | thật | nhân viên vận hành | D-004 |

Chi phí: dev và staging không phát sinh phí hạ tầng (máy lập trình viên và runner CI trong gói miễn phí, xem [cost-licensing.md](../02-tech-stack/cost-licensing.md)); chi phí production ở [cost-model.md](../03-capacity/cost-model.md).

## Quy tắc dữ liệu giữa môi trường
<!-- required -->

- Dữ liệu thật ở môi trường ngoài production: không dùng
- Sao chép dữ liệu production về môi trường khác: cấm

## Cấu hình và bí mật theo môi trường
<!-- required -->

| Mục | Cách quản lý |
| --- | --- |
| Cấu hình khác nhau giữa môi trường | biến môi trường, một tệp cấu hình mỗi môi trường |
| Bí mật | tập bí mật riêng mỗi môi trường, theo [secrets-compliance.md](../08-security/secrets-compliance.md); khóa HMAC và khóa nhân viên của production không dùng ở môi trường khác |
| Khác biệt với production được phép | một máy ảo thay vì hai, không có standby; rủi ro là không kiểm được failover ở staging |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian dựng một môi trường staging mới | 10 phút | NFR-002 | nhật ký workflow CI |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| đồng bộ cấu hình staging với production | mỗi tháng | 1 giờ | C-002 |
