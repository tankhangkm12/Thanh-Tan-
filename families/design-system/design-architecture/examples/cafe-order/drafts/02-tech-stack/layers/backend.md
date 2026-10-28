# Lớp backend

## Lựa chọn
<!-- required -->

| Công nghệ | Phiên bản | Vai trò trong dự án | Quyết định |
| --- | --- | --- | --- |
| Node.js — runtime cho order-service | 24.0 | chạy order-service | D-002 |

## Truy vết tiêu chí
<!-- required -->

| Điều lớp phải đáp ứng | TC | Cách công nghệ đáp ứng | Nguồn |
| --- | --- | --- | --- |
| Còn hỗ trợ đến hết mốc 3y | TC-001 | xem [versions-features.md](../versions-features.md) | https://example.com/lifecycle/backend |
| Team học được trước hạn | TC-002 | xem [team-readiness.md](../team-readiness.md) | https://example.com/docs/backend |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| p95 xử lý một request | dưới 300 ms | NFR-001 | log truy cập, tại order-service |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Công nghệ | Đơn vị scale | Giới hạn (số + đơn vị) | Ngưỡng lên giai đoạn sau | Đường nâng cấp | Bảo trì mỗi tháng (giờ) | Cơ sở ước tính |
| --- | --- | --- | --- | --- | --- | --- |
| Node.js | instance | năng lực mỗi instance ở [compute-sizing.md](../../03-capacity/compute-sizing.md) | mức dùng CPU trên 70% | bản LTS kế tiếp trước ngày hết hỗ trợ | 2 giờ | [lịch phát hành](https://github.com/nodejs/Release#release-schedule) |

## Rủi ro
<!-- required -->

Không có rủi ro mới ở lớp này: phiên bản chốt còn hỗ trợ xa hơn mốc 3y.
