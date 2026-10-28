# CI/CD

## Pipeline
<!-- required -->

| Giai đoạn | Việc làm | Công cụ | Thời gian tối đa (phút) | Cơ sở |
| --- | --- | --- | --- | --- |
| build | build order-service và order-web | GitHub Actions, Node.js 24.0, Vite 7.3 | 5 | [gói miễn phí](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions) |
| kiểm thử | kiểm thử đơn vị, kiểm thử hợp đồng, kiểm thử tải nhẹ | GitHub Actions | 5 | [gói miễn phí](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions) |
| quét | quét bí mật và lỗ hổng phụ thuộc, đo hiệu năng so với ngân sách | GitHub Actions | 3 | [gói miễn phí](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions) |
| đóng gói | tạo ảnh build gắn tag theo mã commit | GitHub Actions | 2 | [gói miễn phí](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions) |
| triển khai | triển khai lần lượt từng máy ảo | GitHub Actions | 5 | [gói miễn phí](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions) |

## Cổng chất lượng
<!-- required -->

| Cổng | Điều kiện đạt | Khi không đạt | Nguồn |
| --- | --- | --- | --- |
| kiểm thử đơn vị | độ phủ domain từ 80% | chặn merge | NFR-002 |
| quét lỗ hổng | không có lỗ hổng nghiêm trọng hoặc cao chưa vá, theo hạn ở [secrets-compliance.md](../08-security/secrets-compliance.md) | chặn merge | NFR-002 |
| kiểm hợp đồng | order-web và order-service khớp [api.md](../06-backend/services/order-service/api.md) | chặn merge | NFR-001 |
| ngân sách hiệu năng | JS tải ban đầu tối đa 170 KB nén, LCP tối đa 2,5 s, theo [performance-budget.md](../05-frontend/performance-budget.md) | chặn merge | NFR-001 |

## Triển khai
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Chiến lược | rolling: lần lượt từng máy ảo, máy còn lại giữ phục vụ | |
| Tỉ lệ lưu lượng cho bản canary (phần trăm) | không dùng canary | |
| Rollback tự động khi | tỉ lệ lỗi 5xx trên 5% trong 2 phút sau khi triển khai một máy | NFR-002 |
| Thời gian rollback tối đa (phút) | 10, khớp [build-delivery.md](../05-frontend/order-web/build-delivery.md) | NFR-002 |
| Thay đổi schema database | migration chạy trước khi triển khai mã mới, tương thích ngược với mã cũ; xem [migration-strategy.md](../07-data/databases/order-db/migration-strategy.md) | |

## Artifact và bí mật
<!-- required -->

| Mục | Giá trị |
| --- | --- |
| Nơi lưu artifact và image | kho gói đi kèm GitHub, tag là mã commit |
| Quét bí mật và phụ thuộc | mỗi pull request |
| Bí mật dùng trong pipeline | bí mật của GitHub Actions theo từng môi trường, theo [secrets-compliance.md](../08-security/secrets-compliance.md) |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian pipeline đầy đủ (p95) | 20 phút | NFR-002 | lịch sử chạy workflow |
| tỉ lệ build lỗi không do mã | 2% | NFR-002 | lịch sử chạy workflow |

## Nâng cấp và bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| cập nhật phiên bản action, dọn ảnh build cũ | mỗi tháng | 1 giờ | C-002 |
