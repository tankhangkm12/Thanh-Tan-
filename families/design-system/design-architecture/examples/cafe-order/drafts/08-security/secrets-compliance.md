# Bí mật, mã hóa và tuân thủ

## Quản lý bí mật
<!-- required -->

| Loại bí mật | Nơi lưu | Ai và gì được đọc | Chu kỳ xoay (ngày) | Cơ sở |
| --- | --- | --- | --- | --- |
| khóa HMAC ký mã tra cứu | tệp cấu hình bí mật trên máy ảo, quyền chỉ chủ tiến trình đọc | chỉ tiến trình order-service | 365 | [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) |
| khóa nhân viên | mỗi nhân viên một khóa; order-service chỉ giữ bản băm, nhân viên giữ khóa gốc | order-service đọc bản băm; người vận hành thêm hoặc gỡ | 90 | [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) |
| mật khẩu database | tệp cấu hình bí mật trên máy ảo | order-service, người vận hành | 365 | [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) |

Khi xoay khóa HMAC, order-service chấp nhận cả khóa cũ và khóa mới trong 30 ngày (cửa sổ hai khóa, C-002), sau đó bỏ khóa cũ; mã tra cứu cũ ký bằng khóa đã bỏ trả lỗi không tìm thấy. Khi nhân viên nghỉ, người vận hành gỡ bản băm khóa của người đó trong cùng ngày; khóa không dùng chung giữa các người. Cửa sổ này khớp chu kỳ rà khóa mỗi tháng của team 3 người (C-002).

Bí mật không nằm trong mã nguồn, log hay ảnh build: công cụ quét bí mật chạy ở mỗi pull request (xem [ci-cd.md](../09-infrastructure/ci-cd.md)).

## Mã hóa
<!-- required -->

| Phạm vi | Cách mã hóa | Quản lý khóa | Cơ sở |
| --- | --- | --- | --- |
| khi truyền | TLS 1.2 trở lên giữa client và order-service, và giữa order-service với order-db | chứng chỉ gia hạn tự động mỗi 60 ngày | [Mozilla TLS](https://wiki.mozilla.org/Security/Server_Side_TLS) |
| khi lưu: database và sao lưu | mã hóa ổ đĩa của máy ảo và ổ sao lưu | khóa do nhà cung cấp hạ tầng giữ | C-001 |

## Dữ liệu cá nhân
<!-- required -->

Không lưu dữ liệu cá nhân của khách: khách ẩn danh, đơn chỉ có món, tổng tiền và ghi chú, và không lưu dữ liệu thanh toán ([project-profile.md](../00-context/project-profile.md)). Ghi chú đơn là chữ tự do nên có thể chứa dữ liệu cá nhân do khách tự gõ.

| Loại dữ liệu | Nơi lưu | Thời gian giữ (ngày) | Cách xóa hoặc ẩn danh | Cơ sở |
| --- | --- | --- | --- | --- |
| ghi chú đơn | order-db | 1095 | xóa theo lô cùng đơn, xem [partitioning-retention.md](../07-data/databases/order-db/partitioning-retention.md) | C-001 |

## Tuân thủ
<!-- required -->

Không có quy định riêng ([project-profile.md](../00-context/project-profile.md), mục Tuân thủ).

## Vá lỗi và nâng cấp bảo mật
<!-- required -->

| Mức nghiêm trọng của lỗ hổng | Hạn vá (ngày) | Cách phát hiện | Cơ sở |
| --- | --- | --- | --- |
| nghiêm trọng | 7 | quét phụ thuộc ở mỗi pull request, bản tin bảo mật của Ubuntu | C-002 |
| cao | 30 | quét phụ thuộc, bản tin bảo mật của Ubuntu | C-002 |
| trung bình | 90 | quét phụ thuộc mỗi tháng | C-002 |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| tỉ lệ bí mật xoay đúng hạn | 100% | NFR-002 | danh sách bí mật và ngày xoay trong wiki vận hành |
| thời gian từ lúc có bản vá đến lúc triển khai (p95) | 7 ngày | NFR-002 | lịch sử CI và ghi nhận lỗ hổng |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| xoay bí mật đến hạn, vá phụ thuộc, rà chứng chỉ | mỗi tháng | 2 giờ | C-002 |
