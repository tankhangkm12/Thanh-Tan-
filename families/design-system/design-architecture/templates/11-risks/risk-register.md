# Sổ rủi ro

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. **File chỉ có một bảng, là bảng rủi ro**: `check_workspace.py` đọc bảng đầu tiên với các cột ID, "Khả năng × Tác động", "Trạng thái", và `check_links.py` đòi mọi bảng trong file có cột "Thành phần liên quan" (bảng thứ hai, như bảng thang điểm, bị báo lỗi `risk-without-components-column`); nội dung khác viết dạng danh sách. `R-xx` được định nghĩa ở ô đầu dòng bảng này, chỉ ở đây; nơi khác chỉ nhắc ID. Mỗi quyết định, dòng phiên bản, bảng sizing và khoảng trống kỹ năng khai rủi ro vào đây ngay khi xuất hiện (Q6). Mức S rút gọn: chỉ ghi rủi ro từ 8 điểm trở lên. Rủi ro từ 15 điểm mà vẫn giữ phải được người dùng chấp nhận rõ ràng (`risks/acceptance.md` của workspace) và trạng thái ghi "đã chấp nhận". Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Sổ rủi ro
<!-- required -->

Điểm = khả năng × tác động, mỗi thang 1–5, tối đa 25; ghi dạng `4 × 3 = 12`. Trạng thái là một trong: đang theo dõi, đang giảm thiểu, đã chấp nhận, đã đóng. Cột "Thành phần liên quan" có ID `SVC-`, `TBL-`, `BKT-`, `EVT-`, `API-` hoặc link tới file trong `02-tech-stack/`. "Cơ sở dấu hiệu sớm" là ID hoặc link giải thích vì sao chọn ngưỡng đó.

| ID | Mô tả | Nhóm | Khả năng × Tác động | Thành phần liên quan | Dấu hiệu sớm | Cơ sở dấu hiệu sớm | Giảm thiểu | Phương án dự phòng | Trạng thái |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-xxx | <điều gì có thể xảy ra, hậu quả cụ thể> | <công nghệ, phiên bản, capacity, vendor, bảo mật, dữ liệu, team, tiến độ, vận hành> | <1–5> × <1–5> = <điểm> | <SVC-xx, TBL-xx hoặc [công nghệ](../02-tech-stack/layers/layer.md)> | <chỉ số có ngưỡng bằng số, ví dụ CPU database trên 70% trong 15 phút> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> | <làm gì trước để giảm khả năng hoặc tác động> | <làm gì khi rủi ro đã xảy ra> | <đang theo dõi> |

## Ngưỡng xử lý
<!-- required -->

- 15–25 điểm: bắt buộc có giảm thiểu; nếu vẫn giữ, người dùng chấp nhận rõ ràng (`R-xx: chấp nhận`) và trạng thái ghi "đã chấp nhận".
- 8–14 điểm: bắt buộc có giảm thiểu và dấu hiệu sớm.
- 1–7 điểm: theo dõi, có dấu hiệu sớm (mức S không ghi).

Phát hành chỉ khi mọi rủi ro từ 15 điểm trở lên đã được giảm thiểu, chấp nhận hoặc đóng.

## Cảnh báo tương ứng
<!-- required -->

Mỗi dấu hiệu sớm có cảnh báo ở [observability.md](../09-infrastructure/observability.md) (mức S không có file đó: ghi cách theo dõi thủ công).

- <R-xx: tên cảnh báo hoặc cách theo dõi>

## Rà soát
<!-- required -->

Ở mỗi gate, Reviewer soát lại: rủi ro mới từ giai đoạn vừa làm đã khai chưa, điểm có cần chấm lại không.

- Lần rà gần nhất: <gate, ngày>
