# Lớp <tên lớp>

> Template của design-architecture, một file mỗi lớp dùng trong stack (frontend, backend, data, messaging, infrastructure, tooling, third-party); lớp không dùng thì không có file. Tên file là tên lớp. Mục có `<!-- required -->` là bắt buộc. Nhắc `TC-xx` bằng ID, **không** đặt `TC-xx` ở ô đầu dòng bảng (chỉ [selection-criteria.md](../selection-criteria.md) định nghĩa TC). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Lựa chọn
<!-- required -->

| Công nghệ | Phiên bản | Vai trò trong dự án | Quyết định |
| --- | --- | --- | --- |
| <Tên — vai trò> | <major.minor> | <dùng cho thành phần nào> | <D-xxx> |

## Truy vết tiêu chí
<!-- required -->

Lớp này được chọn theo tiêu chí nào và đáp ứng ra sao (Q5). Mỗi dòng nhắc ít nhất một `TC-xx`.

| Điều lớp phải đáp ứng | TC | Cách công nghệ đáp ứng | Nguồn |
| --- | --- | --- | --- |
| <điều kiện> | <TC-xx> | <bằng chứng, kèm số nếu có> | <link tài liệu chính thức> |

## Tối ưu
<!-- required -->

Chỉ số mục tiêu của lớp này, bằng số và đơn vị, truy về NFR (Q2).

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <ví dụ: p95 truy vấn> | <ví dụ: < 50 ms> | <NFR-xx> | <công cụ, vị trí đo> |

## Scale, nâng cấp, bảo trì
<!-- required -->

Mỗi công nghệ của lớp một dòng (Q3). Phiên bản và ngày hết hỗ trợ lấy từ [versions-features.md](../versions-features.md), không chép lại.

| Công nghệ | Đơn vị scale | Giới hạn (số + đơn vị) | Ngưỡng lên giai đoạn sau | Đường nâng cấp | Bảo trì mỗi tháng (giờ) | Cơ sở ước tính |
| --- | --- | --- | --- | --- | --- | --- |
| <Tên> | <instance, shard, partition…> | <số> | <số kích hoạt, link scaling-stages nếu có> | <bản kế tiếp, khi nào, việc phải làm> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Rủi ro
<!-- required -->

Rủi ro của lớp này đã khai trong [sổ rủi ro](../../11-risks/risk-register.md): <R-xx, …>. Chưa có sổ ở gate hiện tại thì ghi rủi ro vào `risks/` của workspace và liệt kê ID ở đây.
