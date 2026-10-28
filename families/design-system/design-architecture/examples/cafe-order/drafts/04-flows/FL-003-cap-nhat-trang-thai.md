# FL-003: Cập nhật trạng thái đơn

## Yêu cầu liên quan
<!-- required -->

- FR: FR-003
- NFR: NFR-001, NFR-002
- Ràng buộc: C-001

## Tác nhân và điều kiện
<!-- required -->

- Tác nhân: nhân viên
- Kích hoạt: nhân viên đổi trạng thái
- Điều kiện trước: đơn đã tồn tại
- Kết quả: trạng thái đơn đã đổi

## Sơ đồ tuần tự
<!-- required -->

```mermaid
sequenceDiagram
    participant N as Nhân viên
    participant S as SVC-order-service
    participant D as TBL-orders
    N->>S: API-update-status
    S->>D: cập nhật trạng thái
    S-->>N: xác nhận
```

## Lỗi và xử lý
<!-- required -->

| Bước | Lỗi | Hậu quả cho người dùng | Xử lý (thử lại, thời gian chờ, bù trừ) | Cơ sở |
| --- | --- | --- | --- | --- |
| 2 | chuyển trạng thái không hợp lệ | nhân viên thấy lỗi | từ chối, trả mã 409 | |

## Dữ liệu chạm tới
<!-- required -->

| Loại | ID | Thao tác | Bước |
| --- | --- | --- | --- |
| bảng | TBL-orders | ghi | 2 |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| p95 toàn luồng | dưới 300 ms | NFR-001, NFR-002 | log truy cập của order-service |

## Rủi ro
<!-- required -->

Không có rủi ro mới: luồng chỉ dùng một service và một database đã chốt ở D-001.
