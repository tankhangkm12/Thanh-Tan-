# Giao tiếp giữa các thành phần

## Khi nào đồng bộ, khi nào bất đồng bộ
<!-- required -->

| Tình huống | Kiểu | Lý do |
| --- | --- | --- |
| đặt đơn, xem và đổi trạng thái đơn: cần kết quả ngay để trả lời | đồng bộ | NFR-001 |
| việc người dùng không cần chờ kết quả | bất đồng bộ (dự án chưa có việc nào như vậy) | NFR-001 |

## Gateway và định tuyến
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Điểm vào từ client | client gọi thẳng các instance order-service qua tên miền của hệ thống | |
| Việc gateway làm | không có gateway riêng; xác thực và giới hạn tần suất do order-service làm, xem [cross-cutting.md](cross-cutting.md) | |
| Giới hạn kích thước request (KB) | 16 | [api.md](services/order-service/api.md) |

## Thời gian chờ và thử lại mặc định
<!-- required -->

Không có gọi đồng bộ giữa service. Bảng dưới nói về lần gọi từ order-service tới order-db.

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Thời gian chờ truy vấn tới order-db (ms) | 2000, nhỏ hơn thời gian chờ 5000 ms của client | NFR-001 |
| Số lần thử lại | 2, chỉ với thao tác đọc hoặc ghi có khóa idempotency | NFR-001 |
| Backoff | chờ 1 giây cố định, không jitter | NFR-001 |
| Ngắt mạch (circuit breaker) | không dùng: chỉ một database, không có bên được gọi để cách ly | |
| Hành vi khi bên được gọi hỏng | trả lỗi máy chủ theo mô hình lỗi | |

## Bất đồng bộ
<!-- required -->

Không có: không có kênh hay event; xem [events.md](services/order-service/events.md).

## Phiên bản và tương thích
<!-- required -->

Chi tiết hợp đồng ở [contracts/README.md](contracts/README.md).

- Quy tắc tương thích: thêm trường tùy chọn không đổi phiên bản; xóa trường hoặc đổi nghĩa phải tăng phiên bản chính trong đường dẫn
- Thời gian giữ phiên bản cũ: 90 ngày, vì team 3 người không giữ nhiều phiên bản song song (C-002)

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| tỉ lệ request phải thử lại | 1% | NFR-001 | log truy cập của order-service |
