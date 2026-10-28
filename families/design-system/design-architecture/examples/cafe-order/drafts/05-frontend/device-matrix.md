# Ma trận thiết bị

## Thiết bị hỗ trợ
<!-- required -->

| Lớp thiết bị | OS và phiên bản tối thiểu | Trình duyệt tối thiểu | RAM (GB) | Màn hình (px rộng) | Tỉ lệ người dùng | Cơ sở |
| --- | --- | --- | --- | --- | --- | --- |
| máy yếu nhất | Android 10 | Chrome 120 | 2 | 360 | 25% | [analytics](https://example.com/analytics/order-web-2026-10) |
| tầm trung | iOS 16 | Safari 16 | 4 | 390 | 45% | [analytics](https://example.com/analytics/order-web-2026-10) |
| máy tính bàn của nhân viên | Windows 10 | Edge 120 | 8 | 1366 | 30% | [analytics](https://example.com/analytics/order-web-2026-10) |

## Điều kiện mạng
<!-- required -->

| Lớp mạng | Băng thông tải xuống (Mbps) | Độ trễ khứ hồi (ms) | Tỉ lệ người dùng | Cơ sở |
| --- | --- | --- | --- | --- |
| 4G chậm | 5 | 150 | 25% | [analytics](https://example.com/analytics/order-web-2026-10) |
| 4G | 20 | 60 | 45% | [analytics](https://example.com/analytics/order-web-2026-10) |
| wifi quán | 50 | 20 | 30% | [analytics](https://example.com/analytics/order-web-2026-10) |

## Thiết bị chuẩn để đo
<!-- required -->

- Thiết bị: máy yếu nhất (Android 10, Chrome 120)
- Mạng: 4G chậm

## Không hỗ trợ
<!-- required -->

| Thiết bị hoặc trình duyệt | Hành vi khi gặp | Cơ sở |
| --- | --- | --- |
| trình duyệt cũ hơn bản tối thiểu ở bảng trên | hiện thông báo cần cập nhật trình duyệt, không tải ứng dụng | D-003 |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| tỉ lệ người dùng nằm trong ma trận | 95% | NFR-001 | log truy cập của order-service, theo chuỗi trình duyệt |

## Nâng cấp và bảo trì
<!-- required -->

| Việc | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| rà lại ma trận theo số liệu thật, bỏ hỗ trợ OS hoặc trình duyệt hết vòng đời | mỗi quý | 1 giờ | C-002 |
