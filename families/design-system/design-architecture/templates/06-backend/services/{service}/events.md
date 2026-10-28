# Event của service

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. `EVT-xx` được định nghĩa ở [`07-data/messaging.md`](../../../07-data/messaging.md), không ở đây: file này chỉ nhắc ID, nên cột đầu là tên sự kiện, không phải ID. Service không phát hay nhận event nào thì ghi "không có" ở mục tương ứng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Event phát ra
<!-- required -->

| Sự kiện | EVT | Khi nào phát | Đảm bảo giao | Kích thước payload (byte) | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| <tên> | <EVT-xx> | <điều kiện, bước của FL-xx> | <at-least-once, exactly-once…> | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Event nhận
<!-- required -->

| Sự kiện | EVT | Từ service | Xử lý | Thứ tự và trùng lặp | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| <tên> | <EVT-xx> | <SVC-xx> | <hành động> | <cách xử lý trùng, thứ tự, thử lại tối đa bao nhiêu lần> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
