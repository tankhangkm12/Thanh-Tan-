# Ràng buộc

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. File này là nơi **duy nhất** định nghĩa `C-xx` (ô đầu dòng bảng); file khác chỉ nhắc. Ràng buộc là điều đã cố định từ ngoài, không phải lựa chọn của thiết kế.

## Ràng buộc
<!-- required -->

| ID | Loại | Nội dung | Giá trị (số + đơn vị) | Nguồn | Ảnh hưởng tới thiết kế |
| --- | --- | --- | --- | --- | --- |
| C-xxx | <ngân sách, team, hạ tầng, pháp lý, thời hạn> | <điều bị ràng buộc> | <ví dụ: 500 USD/tháng, 3 người, hạn 2027-03-01> | <BA hoặc người dùng> | <TC, FR hoặc mục bị ảnh hưởng> |

## Ràng buộc có thể nới
<!-- required -->

Ràng buộc nào nới được nếu có lý do, và ai quyết. Không có thì ghi "không có ràng buộc nào nới được".

Không đặt `C-xx` ở ô đầu dòng (ô đầu dòng là chỗ định nghĩa ID).

| Điều kiện nới | Ai quyết | Ràng buộc |
| --- | --- | --- |
| <điều kiện> | <người> | <C-xx> |
