# Nhất quán dữ liệu

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mức nhất quán chọn theo nghiệp vụ, không theo công nghệ; mỗi mức truy về FR, NFR hoặc C. File này chỉ nhắc ID, không đặt `FR-`, `TBL-`… ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Mức nhất quán theo nghiệp vụ
<!-- required -->

| Nghiệp vụ hoặc dữ liệu | Mức | Cơ chế | Cửa sổ bất nhất tối đa (giây) | Cơ sở |
| --- | --- | --- | --- | --- |
| <tên, kèm FR-xx> | <mạnh, cuối cùng> | <giao dịch cơ sở dữ liệu, bản sao đọc, event> | <số, hoặc 0 nếu mạnh> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Giao dịch xuyên service hoặc xuyên kho
<!-- required -->

Ghi "không có" nếu mọi thay đổi nằm gọn trong một database.

| Luồng | Cách bảo đảm | Khi một bước hỏng | Quyết định |
| --- | --- | --- | --- |
| <FL-xx> | <outbox, saga, hai pha> | <bù trừ, thử lại, báo vận hành> | <D-xxx> |

## Xung đột và thứ tự
<!-- required -->

| Tình huống | Cách xử lý |
| --- | --- |
| <hai bên cùng sửa một bản ghi> | <khóa lạc quan theo phiên bản, khóa bi quan> |
| <event đến sai thứ tự> | <bỏ qua bản cũ theo số thứ tự> |

## Đối soát
<!-- required -->

| Việc | Tần suất | So sánh giữa | Khi lệch |
| --- | --- | --- | --- |
| <đối soát định kỳ> | <giờ, ngày> | <hai kho> | <sửa tự động, báo vận hành> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <độ trễ nhân bản đọc (p95)> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |
| <số bản ghi lệch mỗi lần đối soát> | <số> | <NFR-xx> | <báo cáo đối soát> |

## Rủi ro
<!-- required -->

Rủi ro nhất quán (mất event, lệch dữ liệu) đã khai trong [sổ rủi ro](../11-risks/risk-register.md): <R-xx, …>.
