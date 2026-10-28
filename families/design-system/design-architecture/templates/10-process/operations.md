# Vận hành và xử lý sự cố

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Cảnh báo ở [observability.md](../09-infrastructure/observability.md), kế hoạch DR ở [scaling-ha.md](../09-infrastructure/scaling-ha.md), lịch và tiêu chí diễn tập sao lưu ở [backup-recovery.md](../07-data/backup-recovery.md). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Mức sự cố
<!-- required -->

| Mức | Định nghĩa | Thời gian phản hồi (phút) | Ai xử lý | Cơ sở |
| --- | --- | --- | --- | --- |
| <nghiêm trọng, cao, thấp> | <ảnh hưởng người dùng tới đâu, gắn SLO nào> | <số> | <vai trò> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Trực và leo thang
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Hình thức trực | <vòng phiên, giờ hành chính, không trực> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Số người đủ trực | <số, so với số người của team ở constraints.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Khi người trực không phản hồi (phút) | <leo thang cho ai> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Hướng dẫn xử lý (runbook)
<!-- required -->

Mỗi cảnh báo mức nghiêm trọng ở `observability.md` có một dòng.

| Cảnh báo hoặc sự cố | Cách chẩn đoán | Cách xử lý | Nơi đặt hướng dẫn chi tiết |
| --- | --- | --- | --- |
| <tên> | <xem metric, log nào> | <bước đầu tiên, khi nào rollback hoặc chuyển DR> | <đường dẫn> |

## Hậu kiểm
<!-- required -->

- Khi nào làm: <sau sự cố mức nào, trong bao nhiêu ngày>
- Nội dung: <nguyên nhân gốc, việc phòng ngừa, rủi ro mới khai vào sổ rủi ro (R-xx)>

## Diễn tập
<!-- required -->

| Diễn tập | Tần suất | Tiêu chí đạt | Nơi ghi kết quả |
| --- | --- | --- | --- |
| <khôi phục sao lưu> | <tháng, quý; khớp backup-recovery.md> | <thời gian khôi phục thực đo (phút) không vượt RTO> | <đường dẫn> |
| <chuyển DR hoặc failover> | <quý, năm> | <khớp scaling-ha.md> | <đường dẫn> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <thời gian khắc phục sự cố trung bình> | <số + đơn vị> | <NFR-xx> | <nhật ký sự cố> |
| <số sự cố lặp lại mỗi quý> | <số> | <NFR-xx> | <nhật ký sự cố> |
