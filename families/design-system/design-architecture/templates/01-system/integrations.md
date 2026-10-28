# Hệ thống ngoài

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mức S: bắt buộc khi dự án có hệ thống ngoài (thanh toán, mail, SMS…), chỉ bỏ khi không có hệ thống ngoài nào (`profiles.md`). Phiên bản và ngày hết hỗ trợ của dịch vụ bên thứ ba lấy từ [versions-features.md](../02-tech-stack/versions-features.md), không chép lại. File này chỉ nhắc ID, không đặt `FR-`, `SVC-`… ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Danh sách hệ thống ngoài
<!-- required -->

| Hệ thống | Mục đích | Cách gọi | Service gọi | Yêu cầu (FR) | Tài liệu chính thức |
| --- | --- | --- | --- | --- | --- |
| <tên> | <việc nó làm cho dự án> | <REST, webhook, SDK, file> | <SVC-xx> | <FR-xx> | <link> |

## Lỗi và fallback
<!-- required -->

| Hệ thống | Thời gian chờ (ms) | Số lần thử lại | Khi hỏng | Dữ liệu có thể mất | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| <tên> | <số> | <số> | <hành vi: hàng đợi, bỏ qua, báo người dùng, chuyển nhà cung cấp khác> | <có, không, mô tả> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Giới hạn và chi phí
<!-- required -->

Chi phí hạ tầng dẫn link [cost-model.md](../03-capacity/cost-model.md); khoản của nhà cung cấp ngoài ghi kèm link nguồn giá và ngày tra cứu.

| Hệ thống | Giới hạn của nhà cung cấp (số + đơn vị) | Mức dự án dùng ở đỉnh | Cơ sở |
| --- | --- | --- | --- |
| <tên> | <ví dụ: request mỗi giây, hạn mức tháng> | <số, từ workload-model.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

| Hệ thống | Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- | --- |
| <tên> | <tỉ lệ gọi thành công, p95 độ trễ> | <số> | <NFR-xx> | <công cụ, vị trí đo> |

## Nâng cấp và bảo trì
<!-- required -->

| Hệ thống | Cách nhà cung cấp báo thay đổi | Việc định kỳ | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- | --- |
| <tên> | <changelog, email, trang trạng thái> | <xoay khóa, đổi phiên bản API, đối soát> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Rủi ro
<!-- required -->

Rủi ro phụ thuộc (nhà cung cấp ngừng dịch vụ, đổi giá, đổi API) đã khai trong [sổ rủi ro](../11-risks/risk-register.md): <R-xx, …>.
