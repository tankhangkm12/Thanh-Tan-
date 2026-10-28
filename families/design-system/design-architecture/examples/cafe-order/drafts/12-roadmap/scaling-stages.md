# Các giai đoạn scale

## Giai đoạn
<!-- required -->

| Giai đoạn | Ngưỡng bắt đầu (số + đơn vị) | Nguồn của ngưỡng | Thay đổi kiến trúc | Chi phí thêm | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| ra mắt | từ ngày ra mắt | [workload-model.md](../03-capacity/workload-model.md) | hai máy ảo, mỗi máy chạy order-service và PostgreSQL | [cost-model.md](../03-capacity/cost-model.md) | NFR-003 |
| mở rộng | req/s đỉnh vượt công suất hai instance | [compute-sizing.md](../03-capacity/compute-sizing.md) | thêm máy ảo chạy order-service | [cost-model.md](../03-capacity/cost-model.md) | [compute-sizing.md](../03-capacity/compute-sizing.md) |
| tách PostgreSQL | CPU máy ảo trên 70% trong 15 phút | [observability.md](../09-infrastructure/observability.md) | chuyển PostgreSQL primary và standby sang hai máy ảo riêng | [cost-model.md](../03-capacity/cost-model.md) | NFR-001 |

## Dấu hiệu cần chuyển giai đoạn
<!-- required -->

| Giai đoạn kế tiếp | Dấu hiệu | Ngưỡng cảnh báo (số + đơn vị) | Thời gian đệm trước khi chạm ngưỡng thật | Cơ sở |
| --- | --- | --- | --- | --- |
| mở rộng | req/s đỉnh quan sát được trên log truy cập | 80% công suất hai instance | 4 tuần | [compute-sizing.md](../03-capacity/compute-sizing.md) |
| tách PostgreSQL | CPU máy ảo cao (cảnh báo ở observability.md) | 70% trong 15 phút | 1 ngày, vì dựng máy ảo từ cấu hình mất 30 phút (NFR-002) | NFR-001 |

## Thứ tự thay đổi
<!-- required -->

- mở rộng: thêm máy ảo từ cấu hình, thêm vào DNS kiểm tra sức khỏe, theo dõi tải; người phụ trách là nhân viên vận hành
- tách PostgreSQL: dựng hai máy ảo riêng, nhân bản từ primary hiện tại, chuyển kết nối của order-service, tắt PostgreSQL trên máy ứng dụng; người phụ trách là thành viên backend cùng nhân viên vận hành

## Rủi ro
<!-- required -->

Rủi ro order-service và PostgreSQL dùng chung máy ảo, dẫn tới giai đoạn tách PostgreSQL, đã khai trong [sổ rủi ro](../11-risks/risk-register.md): R-003.
