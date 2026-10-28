# Lớp third-party

## Lựa chọn
<!-- required -->

| Công nghệ | Phiên bản | Vai trò trong dự án | Quyết định |
| --- | --- | --- | --- |
| GitHub Actions — CI/CD | SaaS, không phiên bản | build, kiểm thử, đóng gói và triển khai | D-005 |

## Truy vết tiêu chí
<!-- required -->

| Điều lớp phải đáp ứng | TC | Cách công nghệ đáp ứng | Nguồn |
| --- | --- | --- | --- |
| Team học được trước hạn | TC-002 | xem [team-readiness.md](../team-readiness.md) | https://docs.github.com/en/actions |
| Chi phí nằm trong ngân sách | TC-003 | gói miễn phí 2.000 phút mỗi tháng, xem [cost-licensing.md](../cost-licensing.md) | https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian pipeline đầy đủ (p95) | 15 phút | NFR-002 | lịch sử chạy workflow |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Công nghệ | Đơn vị scale | Giới hạn (số + đơn vị) | Ngưỡng lên giai đoạn sau | Đường nâng cấp | Bảo trì mỗi tháng (giờ) | Cơ sở ước tính |
| --- | --- | --- | --- | --- | --- | --- |
| GitHub Actions | số phút chạy mỗi tháng | 2.000 phút ([giới hạn gói miễn phí](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions)) | dùng trên 1.500 phút mỗi tháng | đổi sang runner tự dựng hoặc gói trả phí | 1 giờ | C-002 |

## Rủi ro
<!-- required -->

Không có rủi ro mới ở lớp này: pipeline là tệp YAML, đổi sang công cụ khác tốn 5 người-ngày (xem [exit-strategy.md](../exit-strategy.md)).
