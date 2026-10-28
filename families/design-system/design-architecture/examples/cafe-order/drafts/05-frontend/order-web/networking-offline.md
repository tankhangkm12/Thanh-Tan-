# Mạng, offline và đồng bộ

## Gọi API
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Thời gian chờ mỗi request (ms) | 5000 | NFR-001 |
| Thử lại | 2 lần, chỉ với API-get-order và API-create-order (có khóa idempotency), chờ 1 giây rồi 2 giây | NFR-001 |
| Khóa idempotency khi thử lại | API-create-order dùng khóa do client sinh một lần mỗi lần bấm đặt, theo [api.md](../../06-backend/services/order-service/api.md) | |
| Hủy request khi rời màn hình | có | |
| Xử lý lỗi | theo error model của [cross-cutting.md](../../06-backend/cross-cutting.md) | |

## Offline và đồng bộ
<!-- required -->

Không hỗ trợ offline: không NFR nào đòi (NFR-001, NFR-002, NFR-003), và đặt đơn cần máy chủ xác nhận mới có mã đơn.

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| dữ liệu API truyền mỗi phiên trên mạng 4G chậm | 20 KB | NFR-001 | log truy cập của order-service |
