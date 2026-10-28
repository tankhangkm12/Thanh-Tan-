# Backend: tổng quan

## Bản đồ service
<!-- required -->

Mức A/B là cách tổ chức code bên trong service: A chia theo loại thành phần framework, B chia domain / application / infrastructure / presentation (định nghĩa đầy đủ ở template). `folder-structure.md` của service khớp mức ghi ở đây.

| Service | Đơn vị triển khai | Mức tổ chức code (A/B) | Cơ sở | Trách nhiệm | Database sở hữu | Chi tiết |
| --- | --- | --- | --- | --- | --- | --- |
| order-service | service riêng | B | FR-003: trạng thái chỉ đi tiến; FR-001: đơn có ít nhất một món (quy tắc bất biến ở [domain-model.md](services/order-service/domain-model.md)) | nhận đơn, trả và đổi trạng thái đơn, phục vụ file tĩnh của order-web | order-db | [responsibility.md](services/order-service/responsibility.md) |

## Ranh giới
<!-- required -->

| Quy tắc | Lý do | Quyết định |
| --- | --- | --- |
| chỉ order-service đọc và ghi order-db | một nguồn sự thật cho đơn, một team 3 người (C-002) | D-001 |
| client chỉ đi qua API đã khai ở api.md | giữ hợp đồng ở một chỗ | D-001 |

## Phụ thuộc giữa service
<!-- required -->

Không có: dự án chỉ có một service, không gọi service khác. Cách gọi và thời gian chờ ở [communication.md](communication.md).

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| p95 độ trễ API ở tải đỉnh | 300 ms | NFR-001 | log truy cập của order-service |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Service | Scale, nâng cấp, bảo trì |
| --- | --- |
| order-service | [scaling.md](services/order-service/scaling.md) |

## Rủi ro
<!-- required -->

Không có rủi ro mới từ cách chia service.
