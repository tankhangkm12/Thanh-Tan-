# SVC-order-service: dịch vụ đơn hàng

## Trách nhiệm
<!-- required -->

Sở hữu nghiệp vụ nhận đơn, theo dõi và cập nhật trạng thái đơn.

- Đơn vị triển khai: service riêng
- Làm: nhận đơn, trả trạng thái, đổi trạng thái, phục vụ file tĩnh của order-web
- Không làm: thanh toán (ngoài phạm vi sản phẩm)

## Yêu cầu liên quan
<!-- required -->

- FR: FR-001, FR-002, FR-003
- NFR: NFR-001, NFR-002, NFR-003
- Ràng buộc: C-001
- Luồng: FL-001, FL-002, FL-003

## Ranh giới
<!-- required -->

Một service vì một team 3 người (C-002) và một database duy nhất; quyết định D-001.

## Được dùng bởi
<!-- required -->

- [requirements-trace.md](../../../00-context/requirements-trace.md)
- [flow-index.md](../../../04-flows/flow-index.md)
- [FL-001](../../../04-flows/FL-001-dat-don.md)
- [FL-002](../../../04-flows/FL-002-xem-trang-thai.md)
- [FL-003](../../../04-flows/FL-003-cap-nhat-trang-thai.md)
- [compute-sizing.md](../../../03-capacity/compute-sizing.md)
- [api.md](api.md)
- [events.md](events.md)
- [data.md](data.md)
- [dependencies.md](dependencies.md)
- [scaling.md](scaling.md)
- [containers.md](../../../01-system/containers.md)
- [overview.md](../../../07-data/overview.md)
- [implementation-plan.md](../../../12-roadmap/implementation-plan.md)
- [tables.md](../../../07-data/databases/order-db/tables.md)
