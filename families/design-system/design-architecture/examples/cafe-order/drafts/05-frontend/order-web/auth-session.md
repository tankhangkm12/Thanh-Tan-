# Đăng nhập và phiên

Khách không đăng nhập: khách đặt đơn ẩn danh và xem đơn bằng mã tra cứu. Chỉ nhân viên dùng khóa. Cơ chế phía máy chủ ở [cross-cutting.md](../../06-backend/cross-cutting.md).

## Phiên và token
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Cơ chế | khách: mã tra cứu có chữ ký trong URL; nhân viên: khóa nhân viên gửi trong header mỗi request, không có token truy cập hay token làm mới | |
| Nơi lưu trên client | mã tra cứu: URL; khóa nhân viên: bộ nhớ của tab, không ghi vào localStorage hay cookie | [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) |
| Thời hạn token truy cập (giây) | không áp dụng, vì không có token truy cập | |
| Thời hạn phiên không hoạt động (phút) | 30 phút thì xóa khóa khỏi bộ nhớ | [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) |
| Làm mới token | không áp dụng | |

## Phân quyền màn hình
<!-- required -->

| Màn hình (SCR) | Vai trò được vào | Hành vi khi thiếu quyền | Kiểm ở đâu |
| --- | --- | --- | --- |
| SCR-order-form | mọi người | không có | API-create-order giới hạn tần suất theo IP |
| SCR-order-status | khách giữ mã tra cứu | mã sai trả lỗi không tìm thấy theo error model | kiểm chữ ký ở API-get-order |
| SCR-staff-update | nhân viên | hỏi khóa nhân viên; khóa sai trả lỗi chưa xác thực theo error model | guard route phía client và kiểm lại ở API-update-status |

Kiểm ở client chỉ để điều hướng; quyền thật luôn kiểm lại ở máy chủ. Ma trận đầy đủ ở [authz-matrix.md](../../08-security/authz-matrix.md).

## Đăng xuất và thu hồi
<!-- required -->

- Thoát (nhân viên): xóa khóa khỏi bộ nhớ và cache truy vấn
- Thu hồi từ máy chủ: khóa bị thu hồi thì API trả lỗi chưa xác thực, client xóa khóa và hỏi lại
- Dữ liệu offline còn lại sau khi thoát: không có, vì không hỗ trợ offline

## Bảo vệ phía client
<!-- required -->

| Mối đe dọa | Biện pháp | Tham chiếu |
| --- | --- | --- |
| XSS | chính sách CSP chặn script ngoài, không chèn HTML thô | [threat-model.md](../../08-security/threat-model.md) |
| CSRF | khóa gửi bằng header tùy biến, không dùng cookie | [threat-model.md](../../08-security/threat-model.md) |
| lộ khóa hoặc mã tra cứu | không ghi khóa ra log, mã tra cứu không đưa vào tham chiếu gửi sang trang khác | [threat-model.md](../../08-security/threat-model.md) |
