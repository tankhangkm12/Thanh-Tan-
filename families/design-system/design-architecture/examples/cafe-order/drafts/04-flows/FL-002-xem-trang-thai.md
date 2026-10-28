# FL-002: Xem trạng thái đơn

## Yêu cầu liên quan
<!-- required -->

- FR: FR-002
- NFR: NFR-001
- Ràng buộc: C-001

## Tác nhân và điều kiện
<!-- required -->

- Tác nhân: khách
- Kích hoạt: khách mở màn hình đơn
- Điều kiện trước: khách đã có mã đơn
- Kết quả: khách thấy trạng thái hiện tại

## Sơ đồ tuần tự
<!-- required -->

```mermaid
sequenceDiagram
    participant K as Khách
    participant S as SVC-order-service
    participant D as TBL-orders
    K->>S: API-get-order
    S->>D: đọc đơn
    S-->>K: trạng thái
```

## Lỗi và xử lý
<!-- required -->

| Bước | Lỗi | Hậu quả cho người dùng | Xử lý (thử lại, thời gian chờ, bù trừ) | Cơ sở |
| --- | --- | --- | --- | --- |
| 2 | không có đơn | khách thấy thông báo không tìm thấy | trả mã 404, không thử lại | |

## Dữ liệu chạm tới
<!-- required -->

| Loại | ID | Thao tác | Bước |
| --- | --- | --- | --- |
| bảng | TBL-orders | đọc | 2 |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| p95 toàn luồng | dưới 300 ms | NFR-001 | log truy cập của order-service |

## Rủi ro
<!-- required -->

Không có rủi ro mới: luồng chỉ dùng một service và một database đã chốt ở D-001.
