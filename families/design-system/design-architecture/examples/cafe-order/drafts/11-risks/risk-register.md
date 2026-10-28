# Sổ rủi ro

## Sổ rủi ro
<!-- required -->

| ID | Mô tả | Nhóm | Khả năng × Tác động | Thành phần liên quan | Dấu hiệu sớm | Cơ sở dấu hiệu sớm | Giảm thiểu | Phương án dự phòng | Trạng thái |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-001 | Trang tải chậm trên máy yếu và mạng 4G chậm, khách bỏ đặt đơn | capacity | 3 × 3 = 9 | [frontend](../02-tech-stack/layers/frontend.md) | LCP trên 2,5 s trong 7 ngày liên tiếp | NFR-001 | bước đo hiệu năng trong CI chặn merge khi vượt ngân sách ở [performance-budget.md](../05-frontend/performance-budget.md) | tách gói mã theo route sâu hơn, bỏ thư viện nặng nhất khỏi gói tải ban đầu | đang theo dõi |
| R-002 | Chưa từng khôi phục thử bản sao lưu, đến lúc cần thì khôi phục lâu hơn RTO và mất đơn trong khoảng RPO | dữ liệu | 2 × 4 = 8 | [data](../02-tech-stack/layers/data.md) | thời gian khôi phục thử vượt 240 phút | NFR-002 | diễn tập khôi phục mỗi quý, bắt đầu trước ngày ra mắt (xem [backup-recovery.md](../07-data/backup-recovery.md)) | dựng lại từ bản sao standby, nhận mất tối đa 15 phút dữ liệu | đang theo dõi |
| R-003 | order-service và PostgreSQL dùng chung hai máy ảo: tải đỉnh làm hai bên tranh CPU, và mất một máy là mất cả một instance lẫn primary hoặc standby | capacity | 3 × 3 = 9 | [infrastructure](../02-tech-stack/layers/infrastructure.md), [data](../02-tech-stack/layers/data.md) | CPU máy ảo trên 70% trong 15 phút | NFR-001 | theo dõi CPU từng máy ảo (xem [observability.md](../09-infrastructure/observability.md)), tách PostgreSQL ra máy riêng khi vượt ngưỡng (xem [scaling-ha.md](../09-infrastructure/scaling-ha.md)) | dựng máy ảo riêng cho PostgreSQL từ cấu hình trong 30 phút | đang theo dõi |
| R-004 | Kẻ tấn công dò mã tra cứu từ nhiều IP để xem đơn của người khác hoặc gửi đơn rác | bảo mật | 3 × 3 = 9 | [backend](../02-tech-stack/layers/backend.md) | một IP nhận trên 20 lỗi không tìm thấy trong 5 phút | NFR-003 | chữ ký HMAC 128 bit, giới hạn 5 request/giây mỗi IP ở [cross-cutting.md](../06-backend/cross-cutting.md) | chặn IP ở mức tên miền, xoay khóa HMAC | đang theo dõi |
| R-005 | Lộ hoặc quên thu hồi khóa nhân viên, người ngoài đổi được trạng thái mọi đơn | bảo mật | 2 × 4 = 8 | [backend](../02-tech-stack/layers/backend.md) | một khóa nhân viên quá 90 ngày chưa xoay | C-002 | xoay khóa mỗi 90 ngày, gỡ khóa người nghỉ trong cùng ngày, xem [secrets-compliance.md](../08-security/secrets-compliance.md) | thu hồi toàn bộ khóa nhân viên và cấp lại | đang theo dõi |

## Ngưỡng xử lý
<!-- required -->

- 15–25 điểm: bắt buộc có giảm thiểu; nếu vẫn giữ, người dùng chấp nhận rõ ràng và trạng thái ghi "đã chấp nhận".
- 8–14 điểm: bắt buộc có giảm thiểu và dấu hiệu sớm.
- 1–7 điểm: theo dõi, có dấu hiệu sớm.

## Cảnh báo tương ứng
<!-- required -->

- R-001: kết quả bước đo hiệu năng trong CI mỗi lần build, xem [performance-budget.md](../05-frontend/performance-budget.md)
- R-002: báo cáo diễn tập khôi phục mỗi quý, xem [backup-recovery.md](../07-data/backup-recovery.md)
- R-003: cảnh báo CPU máy ảo cao ở [observability.md](../09-infrastructure/observability.md)
- R-004: cảnh báo dò mã tra cứu ở [observability.md](../09-infrastructure/observability.md)
- R-005: cảnh báo khóa quá hạn xoay ở [observability.md](../09-infrastructure/observability.md)

## Rà soát
<!-- required -->

- Lần rà gần nhất: G9, 2026-10-13
