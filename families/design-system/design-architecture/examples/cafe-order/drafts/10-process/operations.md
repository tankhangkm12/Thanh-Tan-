# Vận hành và xử lý sự cố

## Mức sự cố
<!-- required -->

| Mức | Định nghĩa | Thời gian phản hồi (phút) | Ai xử lý | Cơ sở |
| --- | --- | --- | --- | --- |
| nghiêm trọng | khách không đặt được đơn hoặc nhân viên không đổi được trạng thái, vi phạm SLO ở [observability.md](../09-infrastructure/observability.md) | 30 | nhân viên vận hành | NFR-002 |
| cao | một trong hai máy ảo hỏng, hệ thống vẫn chạy nhưng không còn dự phòng | 60 | nhân viên vận hành | NFR-002 |
| thấp | cảnh báo hiệu năng hoặc bảo mật chưa ảnh hưởng người dùng | 480 | thành viên được giao | C-002 |

## Trực và leo thang
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Hình thức trực | vòng phiên giữa 3 người; giờ hành chính cho mức cao và thấp, ngoài giờ chỉ cho mức nghiêm trọng | C-002 |
| Số người đủ trực | 3, bằng số người của team | C-002 |
| Khi người trực không phản hồi (phút) | 30, leo thang cho người kế tiếp trong vòng phiên | NFR-002 |

## Hướng dẫn xử lý (runbook)
<!-- required -->

Mỗi cảnh báo ở [observability.md](../09-infrastructure/observability.md) có một dòng.

| Cảnh báo hoặc sự cố | Cách chẩn đoán | Cách xử lý | Nơi đặt hướng dẫn chi tiết |
| --- | --- | --- | --- |
| CPU máy ảo cao | metric CPU từng máy ảo, log truy cập theo API | giảm tải bằng cách dừng backfill; nếu kéo dài thì tách PostgreSQL ra máy riêng theo [scaling-stages.md](../12-roadmap/scaling-stages.md) | wiki vận hành, mục CPU cao |
| lỗi máy chủ tăng | log truy cập theo mã 5xx và correlationId | rollback bản mới nhất theo [delivery.md](delivery.md) | wiki vận hành, mục lỗi 5xx |
| ngân sách hiệu năng bị vượt | báo cáo bước đo hiệu năng trong CI | tách gói mã hoặc bỏ thư viện nặng nhất khỏi gói tải ban đầu | wiki vận hành, mục hiệu năng |
| dò mã tra cứu | log theo IP và mã 404 | chặn IP ở mức tên miền; nếu lan rộng thì xoay khóa HMAC theo [secrets-compliance.md](../08-security/secrets-compliance.md) | wiki vận hành, mục dò mã |
| khôi phục thử vượt RTO | báo cáo diễn tập | tìm bước tốn thời gian nhất và sửa, diễn tập lại trong tháng | wiki vận hành, mục diễn tập |
| khóa quá hạn xoay | danh sách khóa và ngày xoay | xoay khóa theo [secrets-compliance.md](../08-security/secrets-compliance.md) | wiki vận hành, mục xoay khóa |

## Hậu kiểm
<!-- required -->

- Khi nào làm: sau mỗi sự cố mức nghiêm trọng, trong vòng 5 ngày (NFR-002)
- Nội dung: nguyên nhân gốc, việc phòng ngừa, rủi ro mới khai vào [sổ rủi ro](../11-risks/risk-register.md)

## Diễn tập
<!-- required -->

| Diễn tập | Tần suất | Tiêu chí đạt | Nơi ghi kết quả |
| --- | --- | --- | --- |
| khôi phục sao lưu | mỗi quý, khớp [backup-recovery.md](../07-data/backup-recovery.md) | thời gian khôi phục thực đo không vượt 240 phút (NFR-002) | báo cáo diễn tập trong wiki vận hành |
| failover sang standby | mỗi quý | khớp [scaling-ha.md](../09-infrastructure/scaling-ha.md) | báo cáo diễn tập trong wiki vận hành |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian khắc phục sự cố trung bình | 60 phút | NFR-002 | nhật ký sự cố |
| số sự cố lặp lại mỗi quý | 1 | NFR-002 | nhật ký sự cố |
