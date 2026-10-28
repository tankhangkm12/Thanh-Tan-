# Messaging

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mỗi event một heading cấp 3 `### EVT-xxx: <tên>`: `EVT-xx` được định nghĩa ở heading đó, chỉ ở file này; `events.md` của service và các luồng chỉ nhắc ID. Schema đầy đủ có thể nằm ở `06-backend/contracts/` và được link tới. Dự án không có kênh bất đồng bộ thì hồ sơ dự án ghi `07-data/messaging.md` là `bỏ` kèm lý do (Q8), và `events.md` của service ghi "không có". Không đặt `SVC-`, `FR-`… ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Kênh
<!-- required -->

| Kênh | Loại | Công nghệ | Thứ tự | Thời gian giữ (giờ) | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| <tên> | <hàng đợi, topic> | <[tên](../02-tech-stack/layers/messaging.md)> | <bảo đảm theo khóa, không bảo đảm> | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Danh sách event
<!-- required -->

| Event | Kênh | Bên phát | Bên nhận |
| --- | --- | --- | --- |
| EVT-xxx | <kênh> | <SVC-xx> | <SVC-xx, …> |

## Chi tiết từng event
<!-- required -->

### EVT-xxx: <tên>

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Khi nào phát | <điều kiện, bước của FL-xx> | |
| Nội dung (payload) | <trường chính, link schema trong contracts/> | |
| Kích thước payload tối đa (byte) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Khóa phân vùng và thứ tự | <trường nào, bảo đảm gì> | |
| Đảm bảo giao | <at-least-once, exactly-once> | |
| Xử lý trùng lặp | <khóa khử trùng, thời gian nhớ (giây)> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Thử lại và hàng đợi lỗi | <số lần, backoff, nơi giữ event lỗi, ai xử lý> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Cách đổi schema | <tương thích ngược, phiên bản> | |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <độ trễ từ lúc phát đến lúc xử lý xong (p95)> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |
| <số event tồn đọng tối đa> | <số> | <NFR-xx> | <metric của kênh> |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Đơn vị scale | <partition, consumer> | |
| Giới hạn (số + đơn vị) | <event mỗi giây mỗi kênh, từ workload-model.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Ngưỡng lên giai đoạn sau | <số kích hoạt> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Đường nâng cấp | <phiên bản, ngày hết hỗ trợ lấy từ versions-features.md> | |
| Bảo trì mỗi tháng (giờ) | <rà hàng đợi lỗi, dọn: giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Được dùng bởi
<!-- required -->

Link tới mọi file nhắc một event của file này (`events.md` của service, luồng, requirements-trace…); thiếu link là lỗi `missing-backlink`.

- <[tên file](đường-dẫn-tương-đối.md)>
