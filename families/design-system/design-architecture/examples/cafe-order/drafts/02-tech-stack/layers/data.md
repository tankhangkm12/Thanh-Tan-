# Lớp data

## Lựa chọn
<!-- required -->

| Công nghệ | Phiên bản | Vai trò trong dự án | Quyết định |
| --- | --- | --- | --- |
| PostgreSQL — database quan hệ cho order-db | 16.4 | lưu đơn và món trong đơn | D-002 |

## Truy vết tiêu chí
<!-- required -->

| Điều lớp phải đáp ứng | TC | Cách công nghệ đáp ứng | Nguồn |
| --- | --- | --- | --- |
| Còn hỗ trợ đến hết mốc 3y | TC-001 | xem [versions-features.md](../versions-features.md) | https://example.com/lifecycle/data |
| Team học được trước hạn | TC-003 | xem [team-readiness.md](../team-readiness.md) | https://example.com/docs/data |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| p95 truy vấn theo khóa | dưới 20 ms | NFR-001 | pg_stat_statements |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Công nghệ | Đơn vị scale | Giới hạn (số + đơn vị) | Ngưỡng lên giai đoạn sau | Đường nâng cấp | Bảo trì mỗi tháng (giờ) | Cơ sở ước tính |
| --- | --- | --- | --- | --- | --- | --- |
| PostgreSQL | primary cộng bản sao đọc | dung lượng theo [data-sizing.md](../../03-capacity/data-sizing.md) | CPU primary trên 70% | bản 17 trước 2028-11-09 | 3 giờ | D-002 |

## Rủi ro
<!-- required -->

Không có rủi ro mới ở lớp này: phiên bản chốt còn hỗ trợ xa hơn mốc 3y.
