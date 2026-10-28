# Truy vết yêu cầu

## Yêu cầu chức năng
<!-- required -->

| ID | Mô tả | Nguồn BA | NFR | Ràng buộc | Luồng (FL) | Dịch vụ (SVC) | Bảng / bucket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-001 | Khách đặt đơn gồm nhiều món | inputs/ba/prd.md mục 3.1 | NFR-001 | C-001 | FL-001 | SVC-order-service | TBL-orders, TBL-order-items |
| FR-002 | Khách xem trạng thái đơn của mình | inputs/ba/prd.md mục 3.2 | NFR-001 | C-001 | FL-002 | SVC-order-service | TBL-orders |
| FR-003 | Nhân viên cập nhật trạng thái đơn | inputs/ba/prd.md mục 3.3 | NFR-001, NFR-002 | C-001 | FL-003 | SVC-order-service | TBL-orders |

## Phủ yêu cầu phi chức năng
<!-- required -->

- NFR-001: được đáp ứng bởi FR-001, FR-002, FR-003, SVC-order-service
- NFR-002: được đáp ứng bởi FR-003, SVC-order-service
- NFR-003: được đáp ứng bởi SVC-order-service

## Yêu cầu chưa phủ

Không có.
