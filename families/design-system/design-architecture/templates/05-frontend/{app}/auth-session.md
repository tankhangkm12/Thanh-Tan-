# Đăng nhập và phiên

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Cơ chế xác thực phía máy chủ nằm ở [cross-cutting.md](../../06-backend/cross-cutting.md); ma trận phân quyền đầy đủ ở [authz-matrix.md](../../08-security/authz-matrix.md) (có từ mức M). Màn hình nhắc bằng `SCR-xx`; cột đầu của bảng không phải ID. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Phiên và token
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Cơ chế | <cookie phiên, token truy cập kèm làm mới> | |
| Nơi lưu token trên client | <cookie HttpOnly, bộ nhớ, kho an toàn của hệ điều hành> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Thời hạn token truy cập (giây) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Thời hạn phiên không hoạt động (phút) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Làm mới token | <khi nào, xử lý khi nhiều tab cùng làm mới> | |

## Phân quyền màn hình
<!-- required -->

| Màn hình (SCR) | Vai trò được vào | Hành vi khi thiếu quyền | Kiểm ở đâu |
| --- | --- | --- | --- |
| <SCR-xx> | <vai trò> | <chuyển hướng, trả lỗi theo error model> | <guard route phía client và kiểm lại ở API> |

Kiểm ở client chỉ để điều hướng; quyền thật luôn kiểm lại ở máy chủ.

## Đăng xuất và thu hồi
<!-- required -->

- Đăng xuất: <xóa gì trên client, gọi API nào>
- Thu hồi phiên từ máy chủ: <client biết bằng cách nào, hành vi>
- Dữ liệu offline còn lại sau đăng xuất: <xóa, giữ>

## Bảo vệ phía client
<!-- required -->

| Mối đe dọa | Biện pháp | Tham chiếu |
| --- | --- | --- |
| <XSS, CSRF, lộ token> | <CSP, SameSite, không ghi token ra log> | <mục trong threat-model.md hoặc R-xx> |
