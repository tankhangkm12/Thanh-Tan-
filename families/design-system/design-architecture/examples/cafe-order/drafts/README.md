# CafeOrder: kiến trúc

## Phiên bản và mức áp dụng
<!-- required -->

- Phiên bản: v1 (khớp mục mới nhất của `CHANGELOG.md` khi `archive_release.py` ghi file đó lúc phát hành)
- Ngày phát hành: chưa phát hành; bộ mẫu không có phê duyệt thật
- Mức áp dụng: M, theo [project-profile.md](00-context/project-profile.md)
- Phát hành khi người dùng duyệt: chưa có; khi phát hành ghi nguyên văn câu duyệt G10 của người dùng

## Mục lục
<!-- required -->

| Phần | Nội dung | Áp dụng |
| --- | --- | --- |
| [00-context](00-context/project-profile.md) | hồ sơ dự án, truy vết yêu cầu, NFR, ràng buộc, giả định, thuật ngữ | có |
| [01-system](01-system/containers.md) | bối cảnh, containers, kiểu kiến trúc, hệ thống ngoài | có |
| [02-tech-stack](02-tech-stack/README.md) | stack đã chốt, tiêu chí, phiên bản, tương thích, chi phí, thoát | có |
| [03-capacity](03-capacity/workload-model.md) | mô hình tải, dung lượng dữ liệu, năng lực tính toán, chi phí | có |
| [04-flows](04-flows/flow-index.md) | các luồng nghiệp vụ | có |
| [05-frontend](05-frontend/overview.md) | kiến trúc kỹ thuật của app web | có |
| [06-backend](06-backend/overview.md) | service, giao tiếp, xuyên suốt, hợp đồng | có |
| [07-data](07-data/overview.md) | database, nhất quán, sao lưu | có; bỏ object storage, cache, messaging (lý do ở project-profile.md) |
| [08-security](08-security/threat-model.md) | phân quyền, bí mật, mối đe dọa | có |
| [09-infrastructure](09-infrastructure/topology.md) | topology, môi trường, CI/CD, quan sát, scale và HA | có |
| [10-process](10-process/operations.md) | phát hành, thay đổi dữ liệu, bảo trì, vận hành | có |
| [11-risks](11-risks/risk-register.md) | sổ rủi ro | có |
| [12-roadmap](12-roadmap/implementation-plan.md) | kế hoạch triển khai, giai đoạn scale, nâng cấp | có |

## Cách đọc
<!-- required -->

| Vai trò | Bắt đầu từ | Rồi đọc |
| --- | --- | --- |
| agent dev | [implementation-plan.md](12-roadmap/implementation-plan.md), gói của mình | tài liệu đầu vào ghi trong gói |
| designer | [routing-navigation.md](05-frontend/order-web/routing-navigation.md) | [authz-matrix.md](08-security/authz-matrix.md) |
| người vận hành | [topology.md](09-infrastructure/topology.md), [observability.md](09-infrastructure/observability.md) | [operations.md](10-process/operations.md), [backup-recovery.md](07-data/backup-recovery.md) |

## Quy ước ID
<!-- required -->

Mọi file liên kết hai chiều với nhau qua ID. Mỗi loại ID được định nghĩa ở đúng một nơi.

| Tiền tố | Nghĩa | Định nghĩa ở |
| --- | --- | --- |
| `FR`, `NFR` | yêu cầu chức năng, phi chức năng | `00-context/` |
| `C`, `A` | ràng buộc, giả định | `00-context/constraints.md`, `00-context/assumptions.md` |
| `TC` | tiêu chí chọn công nghệ | `02-tech-stack/selection-criteria.md` |
| `FL` | luồng | `04-flows/` |
| `SCR` | màn hình (của designer) | tài liệu của designer, không định nghĩa ở đây |
| `SVC`, `API` | service, API | `06-backend/` |
| `EVT`, `TBL`, `BKT` | event, bảng, bucket | `07-data/` |
| `R` | rủi ro | `11-risks/risk-register.md` |
| `D`, `CH` | quyết định, câu hỏi | `decisions/` và `questions.md` của workspace, không nằm trong architecture/ |

## Còn mở
<!-- required -->

Không có.
