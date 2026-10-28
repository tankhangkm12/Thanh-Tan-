# Chiến lược thoát

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Đường thay thế cho từng công nghệ trong stack, để việc đổi công nghệ sau này có chi phí và điều kiện kích hoạt biết trước (Q3). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Đường thay thế
<!-- required -->

| Công nghệ | Mức khóa chặt | Phương án thay thế | Chi phí chuyển (người-ngày) | Dữ liệu cần chuyển |
| --- | --- | --- | --- | --- |
| <Tên> | <thấp / vừa / cao, vì sao> | <công nghệ khác hoặc cách tự vận hành> | <số> | <loại dữ liệu, dung lượng nếu biết (link data-sizing)> |

## Điều kiện kích hoạt
<!-- required -->

Ngưỡng bằng số khiến phải bắt đầu chuyển.

| Công nghệ | Điều kiện (số + đơn vị) | Cách phát hiện | Rủi ro | Cơ sở |
| --- | --- | --- | --- | --- |
| <Tên> | <ví dụ: chi phí > 800 USD/tháng, hoặc hết hỗ trợ trong 6 tháng> | <chỉ số, cảnh báo> | <R-xx> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
