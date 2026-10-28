# CI/CD

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Quy trình phát hành và rollback ở góc nhìn con người nằm ở [delivery.md](../10-process/delivery.md); file này nói pipeline tự động làm gì. Ngân sách hiệu năng frontend ở [performance-budget.md](../05-frontend/performance-budget.md). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Pipeline
<!-- required -->

| Giai đoạn | Việc làm | Công cụ | Thời gian tối đa (phút) | Cơ sở |
| --- | --- | --- | --- | --- |
| <build, kiểm thử, quét, đóng gói, triển khai> | <việc> | <công cụ, phiên bản chốt> | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Cổng chất lượng
<!-- required -->

Điều kiện chặn merge hoặc chặn triển khai.

| Cổng | Điều kiện đạt | Khi không đạt | Nguồn |
| --- | --- | --- | --- |
| <kiểm thử, độ phủ, quét lỗ hổng, kiểm hợp đồng, ngân sách hiệu năng> | <ngưỡng bằng số> | <chặn, cảnh báo> | <NFR-xx, C-xx hoặc link> |

## Triển khai
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Chiến lược | <rolling, blue-green, canary> | |
| Tỉ lệ lưu lượng cho bản canary (phần trăm) | <số, nếu dùng canary> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Rollback tự động khi | <điều kiện, ví dụ tỉ lệ lỗi vượt ngưỡng> | |
| Thời gian rollback tối đa (phút) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Thay đổi schema database | <thứ tự với triển khai mã, link migration-strategy.md> | |

## Artifact và bí mật
<!-- required -->

| Mục | Giá trị |
| --- | --- |
| Nơi lưu artifact và image | <registry, quy tắc đặt tag> |
| Quét bí mật và phụ thuộc | <công cụ, khi nào> |
| Bí mật dùng trong pipeline | <lấy từ đâu, theo secrets-compliance.md> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <thời gian pipeline đầy đủ (p95)> | <số + đơn vị> | <NFR-xx> | <CI> |
| <tỉ lệ build lỗi không do mã> | <phần trăm> | <NFR-xx> | <CI> |

## Nâng cấp và bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <cập nhật runner và công cụ, dọn artifact cũ> | <tuần, tháng> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
