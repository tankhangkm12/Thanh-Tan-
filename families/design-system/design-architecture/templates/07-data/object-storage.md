# Object storage

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mỗi bucket một heading cấp 3 `### BKT-xxx: <tên>`: `BKT-xx` được định nghĩa ở heading đó, chỉ ở file này (tên ID trùng khóa trong `capacity/storage.yaml`). Số file, dung lượng và băng thông do `calc_capacity.py` tính ở [storage-sizing.md](../03-capacity/storage-sizing.md): **dẫn link, không chép lại**. Dự án không có object storage thì không có file này: hồ sơ dự án ghi `07-data/object-storage.md` là `bỏ` kèm lý do (Q8) và `capacity/storage.yaml` không có bucket. Không đặt `SVC-`, `FR-`… ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Danh sách bucket
<!-- required -->

| Bucket | Mục đích | Service sở hữu | Yêu cầu (FR) |
| --- | --- | --- | --- |
| BKT-xxx | <loại file lưu> | <SVC-xx> | <FR-xx> |

## Chi tiết từng bucket
<!-- required -->

### BKT-xxx: <tên>

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Loại object | <ảnh, tài liệu, báo cáo> | |
| Kích thước và số lượng | <link mục BKT-xx trong storage-sizing.md> | |
| Quyền truy cập | <riêng tư, công khai; ai ghi, ai đọc> | |
| Thời hạn URL tạm thời (giây) | <số, nếu dùng presigned URL> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Vòng đời và thời gian giữ (ngày) | <chuyển lớp lưu trữ, xóa sau bao lâu> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Phiên bản hóa | <bật, tắt; giữ bao nhiêu bản> | |
| Mã hóa | <khi lưu, khi truyền> | |
| Cách tham chiếu từ bảng | <cột nào trong `TBL-xx` giữ khóa object> | |

## Tối ưu
<!-- required -->

| Bucket | Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- | --- |
| <BKT-xx> | <p95 độ trễ tải lên và tải xuống> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Giới hạn của dịch vụ (số + đơn vị) | <ví dụ: request mỗi giây mỗi tiền tố> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Ngưỡng lên giai đoạn sau | <số kích hoạt, link scaling-stages.md nếu có> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Đường nâng cấp hoặc di chuyển nhà cung cấp | <việc phải làm, link exit-strategy.md> | |
| Việc định kỳ (giờ mỗi tháng) | <rà quyền, dọn object mồ côi: giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Được dùng bởi
<!-- required -->

Link tới mọi file nhắc một bucket của file này (luồng, service, capacity, requirements-trace…); thiếu link là lỗi `missing-backlink`.

- <[tên file](đường-dẫn-tương-đối.md)>
