# Kiểu kiến trúc và giai đoạn scale

## Kiểu đã chọn
<!-- required -->

- Kiểu: một service backend ([order-service](../06-backend/services/order-service/responsibility.md)) và một database (order-db)
- Quyết định: D-001

## Lý do
<!-- required -->

| Điều kiện | Nguồn | Vì sao kiểu này đáp ứng |
| --- | --- | --- |
| Một team 3 người vận hành | C-002 | một service là đủ để giữ gánh nặng vận hành thấp |
| Ngân sách hạ tầng 300 USD mỗi tháng | C-001 | số thành phần phải trả tiền giữ ở mức hai (service và database) |

## Phương án đã loại
<!-- required -->

| Phương án | Vì sao loại | Nguồn |
| --- | --- | --- |
| tách thành từng service theo nghiệp vụ | 3 người không đủ để giữ từng pipeline riêng | C-002 |

## Giai đoạn scale
<!-- required -->

| Giai đoạn | Kiểu ở giai đoạn này | Ngưỡng bắt đầu (số + đơn vị) | Việc phải làm khi chuyển | Cơ sở |
| --- | --- | --- | --- | --- |
| ra mắt | một service, một database | từ ngày ra mắt | không có | NFR-003 |
| mở rộng | thêm instance của order-service | req/s đỉnh vượt công suất 2 instance | thêm instance theo [compute-sizing.md](../03-capacity/compute-sizing.md) | [compute-sizing.md](../03-capacity/compute-sizing.md) |
| tách PostgreSQL | chuyển PostgreSQL sang máy ảo riêng | CPU máy ảo trên 70% trong 15 phút | dựng hai máy ảo riêng, xem [scaling-stages.md](../12-roadmap/scaling-stages.md) | NFR-001 |

## Gánh nặng vận hành
<!-- required -->

| Việc | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| vá bảo mật và cập nhật phụ thuộc | mỗi tháng | 2 giờ | C-002 |

## Rủi ro
<!-- required -->

Order-service và PostgreSQL dùng chung máy ảo đã khai trong [sổ rủi ro](../11-risks/risk-register.md): R-003.
