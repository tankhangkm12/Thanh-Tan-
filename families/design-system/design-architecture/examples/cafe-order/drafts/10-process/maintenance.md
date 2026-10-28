# Bảo trì và nâng cấp định kỳ

## Lịch nâng cấp phiên bản
<!-- required -->

| Thành phần | Nơi ghi phiên bản và ngày hết hỗ trợ | Bắt đầu nâng cấp trước ngày hết hỗ trợ (tháng) | Người phụ trách | Cơ sở |
| --- | --- | --- | --- | --- |
| Node.js | [versions-features.md](../02-tech-stack/versions-features.md) | 6 | thành viên backend | C-002 |
| PostgreSQL | [versions-features.md](../02-tech-stack/versions-features.md) | 6 | nhân viên vận hành | C-002 |
| Ubuntu Server | [versions-features.md](../02-tech-stack/versions-features.md) | 6 | nhân viên vận hành | C-002 |

Lộ trình theo ngày ở [upgrade-roadmap.md](../12-roadmap/upgrade-roadmap.md). React, Vite và GitHub Actions chưa công bố ngày hết hỗ trợ nên theo dõi qua chính sách bản vá bên dưới. Đổi phiên bản sau khi stack đã chốt đi qua chế độ nâng cấp và ghi vào `CHANGELOG.md`.

## Vá lỗi định kỳ
<!-- required -->

| Loại vá | Tần suất | Quy trình | Hạn tối đa (ngày) | Cơ sở |
| --- | --- | --- | --- | --- |
| bản vá bảo mật và phụ thuộc | mỗi tháng | thành viên vận hành kiểm bản tin, thử ở staging, triển khai theo [delivery.md](delivery.md) | 30, khớp [secrets-compliance.md](../08-security/secrets-compliance.md) | C-002 |

## Tổng gánh nặng bảo trì
<!-- required -->

| Việc | Nơi ghi chi tiết | Giờ mỗi tháng |
| --- | --- | --- |
| vá và cập nhật phụ thuộc của order-service | [scaling.md](../06-backend/services/order-service/scaling.md) | 2 |
| bảo trì order-db | [migration-strategy.md](../07-data/databases/order-db/migration-strategy.md) | 3 |
| build và phân phối order-web | [build-delivery.md](../05-frontend/order-web/build-delivery.md) | 2 |
| hạ tầng máy ảo | [topology.md](../09-infrastructure/topology.md) | 2 |
| bí mật và vá lỗi bảo mật | [secrets-compliance.md](../08-security/secrets-compliance.md) | 2 |
| sao lưu và diễn tập khôi phục | [backup-recovery.md](../07-data/backup-recovery.md) | 1 |
| CI/CD | [ci-cd.md](../09-infrastructure/ci-cd.md) | 1 |
| quan sát | [observability.md](../09-infrastructure/observability.md) | 1 |
| môi trường | [environments.md](../09-infrastructure/environments.md) | 1 |
| failover và ngưỡng scale | [scaling-ha.md](../09-infrastructure/scaling-ha.md) | 1 |
| quy trình phát hành | [delivery.md](delivery.md) | 1 |
| khóa nhân viên và phân quyền | [authz-matrix.md](../08-security/authz-matrix.md) | 1 |
| xuyên suốt (khóa, giới hạn tần suất) | [cross-cutting.md](../06-backend/cross-cutting.md) | 1 |
| mô hình mối đe dọa | [threat-model.md](../08-security/threat-model.md) | 1 |
| ma trận thiết bị | [device-matrix.md](../05-frontend/device-matrix.md) | 1 |

Tổng giờ mỗi tháng: 21; so với năng lực team ở C-002: đủ, vì 21 giờ chia cho 3 người là 7 giờ mỗi người mỗi tháng.

## Dọn dẹp
<!-- required -->

| Đối tượng | Quy tắc dọn | Tần suất | Cơ sở |
| --- | --- | --- | --- |
| log truy cập | giữ 30 ngày, hệ thống tự xóa | hằng ngày | C-001 |
| ảnh build cũ | giữ 10 bản gần nhất, nhân viên vận hành xóa | mỗi tháng | C-001 |
| môi trường staging tạm | hủy ngay sau khi kiểm thử xong | mỗi lần phát hành | C-001 |
| đơn hết thời gian giữ | xóa theo lô sau 1095 ngày, xem [partitioning-retention.md](../07-data/databases/order-db/partitioning-retention.md) | hằng đêm | C-001 |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| số thành phần đã hết hỗ trợ | 0 | NFR-002 | `check_versions.py`, versions-features.md |
| thời gian vá lỗ hổng nghiêm trọng (p95) | 7 ngày | NFR-002 | nhật ký vá |
