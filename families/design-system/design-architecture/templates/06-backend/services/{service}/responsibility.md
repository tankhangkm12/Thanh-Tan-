# SVC-xxx: <tên service>

> Template của design-architecture, một thư mục mỗi service (`06-backend/services/<service>/`). `SVC-xx` được định nghĩa ở heading trên, chỉ ở file này; tên ID trùng khóa `id` trong `capacity/compute.yaml`. Mục có `<!-- required -->` là bắt buộc. Không có thư mục `modules/`: modular monolith vẫn dùng `services/<service>/`, mỗi module một thư mục, và trường "Đơn vị triển khai" bên dưới nói nó là service riêng hay module trong monolith. Không đặt `FR-`, `TBL-`… ở ô đầu dòng bảng.

## Trách nhiệm
<!-- required -->

<một câu: service sở hữu nghiệp vụ nào>

- Đơn vị triển khai: <service riêng | module trong monolith>

- Làm: <việc 1>
- Không làm: <việc thuộc service khác, kèm SVC-xx của nơi làm>

## Yêu cầu liên quan
<!-- required -->

- FR: <FR-xx, …>
- NFR: <NFR-xx>
- Ràng buộc: <C-xx, hoặc "không có">
- Luồng: <FL-xx, …>

## Ranh giới
<!-- required -->

Vì sao ranh giới nằm ở đây (dữ liệu sở hữu, tốc độ thay đổi, team, scale riêng) và quyết định nào chốt nó: <D-xxx>.

## Được dùng bởi
<!-- required -->

Link tới mọi file nhắc `SVC-xxx` (luồng, service khác, capacity, requirements-trace…); thiếu link là lỗi `missing-backlink`.

- <[tên file](đường-dẫn-tương-đối.md)>
