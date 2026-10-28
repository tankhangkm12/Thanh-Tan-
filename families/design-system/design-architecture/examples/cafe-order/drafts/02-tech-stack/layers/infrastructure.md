# Lớp infrastructure

## Lựa chọn
<!-- required -->

| Công nghệ | Phiên bản | Vai trò trong dự án | Quyết định |
| --- | --- | --- | --- |
| Ubuntu Server LTS — hệ điều hành của máy ảo | 24.04 | chạy order-service và PostgreSQL trên hai máy ảo | D-004 |

## Truy vết tiêu chí
<!-- required -->

| Điều lớp phải đáp ứng | TC | Cách công nghệ đáp ứng | Nguồn |
| --- | --- | --- | --- |
| Còn hỗ trợ đến hết mốc 3y | TC-001 | xem [versions-features.md](../versions-features.md) | https://ubuntu.com/about/release-cycle |
| Team học được trước hạn | TC-002 | xem [team-readiness.md](../team-readiness.md) | https://ubuntu.com/server/docs |
| Chi phí nằm trong ngân sách | TC-003 | bản LTS miễn phí, giá máy ảo ở [cost-model.md](../../03-capacity/cost-model.md) | https://ubuntu.com/pricing |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| mức dùng CPU trung bình của máy ảo ở tải đỉnh | 70% | NFR-001 | giám sát máy ảo |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Công nghệ | Đơn vị scale | Giới hạn (số + đơn vị) | Ngưỡng lên giai đoạn sau | Đường nâng cấp | Bảo trì mỗi tháng (giờ) | Cơ sở ước tính |
| --- | --- | --- | --- | --- | --- | --- |
| Ubuntu Server | máy ảo | theo [compute-sizing.md](../../03-capacity/compute-sizing.md) | mức dùng CPU trên 70% | bản LTS kế tiếp trước 2029-05-31 | 2 giờ | C-002 |

## Rủi ro
<!-- required -->

Rủi ro hai thành phần dùng chung máy ảo đã khai trong [sổ rủi ro](../../11-risks/risk-register.md): R-003.
