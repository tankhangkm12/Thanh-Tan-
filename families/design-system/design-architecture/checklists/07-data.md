# Xong khi: 07-data (databases/{db})

Gate: G7 (quay lại G5 tính lại capacity khi kiểu dữ liệu thật lộ ra). Trọng tâm: Q1, Q2, Q3, Q6, Q8. Checklist này phủ `07-data/databases/<db>/` và các file chung của 07-data (`overview`, `object-storage`, `cache`, `messaging`, `consistency`, `backup-recovery`).

## Mỗi database (thư mục `databases/<db>/`)

- [ ] Có đủ 6 file: `tables.md`, `erd.md`, `access-patterns.md`, `indexing.md`, `partitioning-retention.md`, `migration-strategy.md` (`check_profile.py` báo `instance-file-missing`).
- [ ] Loại database và phiên bản khớp `02-tech-stack/` (có dòng trong `versions-features.md`); khóa của database trong `capacity/tables.yaml` trùng tên thư mục.
- [ ] Kiểu dữ liệu của bảng tăng nhanh nhất, khóa chính và khóa ngoại đã qua hội đồng (`D-xxx`) và người dùng quyết.

## tables.md

- [ ] Mỗi bảng có heading `### TBL-…` (định nghĩa chỉ ở đây), mục đích, FR/NFR, chủ sở hữu `SVC-…` (Q1).
- [ ] Mỗi bảng có **một** cặp `<!-- BEGIN:calc:<bảng> -->` / `<!-- END:calc:<bảng> -->` với `<bảng>` là khóa trong `tables.yaml`; giữa hai dấu chỉ có nội dung `calc_capacity.py` sinh (hoặc "chờ script" trước khi chạy), không sửa tay (`check_numbers.py` báo `calc-block-edited`).
- [ ] Sau khi chạy script: mỗi cột có kiểu, số byte và lý do (từ `reason` trong yaml); kiểu chọn theo số (nhỏ nhất đủ cho mốc xa nhất cộng biên an toàn); cột tăng dần không báo "KHÔNG ĐỦ" (Q4).
- [ ] "Tối ưu": chỉ số bằng số, đơn vị, NFR, cách đo (Q2); số liệu dẫn link `data-sizing.md`, không chép lại.
- [ ] "Được dùng bởi" link mọi file nhắc `TBL-…` (`check_links.py` báo `missing-backlink`).

## erd.md, access-patterns.md, indexing.md

- [ ] erd: mọi bảng trong `tables.md` xuất hiện; kiểu cột khóa ngoại trùng kiểu cột khóa chính (cùng số byte); mỗi khóa ngoại có hành vi khi xóa.
- [ ] access-patterns: mỗi mẫu truy về luồng `FL-xx` và bảng; tần suất trỏ giả định `A-xx` hoặc `workload-model.md`; độ trễ mục tiêu là số có đơn vị (Q1, Q2).
- [ ] indexing: mỗi index trùng tên trong `tables.yaml`, phục vụ ít nhất một mẫu truy cập, có lý do; kích thước dẫn link, không chép số.
- [ ] indexing "Tối ưu": chỉ số bằng số, đơn vị, NFR (Q2).

## partitioning-retention.md, migration-strategy.md

- [ ] Phân vùng: bảng lớn có khóa và ngưỡng bằng số, hoặc ghi "không phân vùng" kèm ngưỡng khi sẽ cần (Q3).
- [ ] Thời gian giữ dữ liệu khớp `retention_days` của yaml, truy về `C-xx` hoặc NFR.
- [ ] "Scale": đơn vị scale, giới hạn, ngưỡng lên giai đoạn sau bằng số (Q3).
- [ ] "Migration schema": công cụ, quy tắc an toàn, thời gian khóa tối đa (giây), rollback, backfill.
- [ ] "Nâng cấp": phiên bản và ngày hết hỗ trợ khớp `versions-features.md`, đường nâng cấp, gián đoạn tối đa (Q3).
- [ ] "Bảo trì": mỗi việc định kỳ có tần suất và giờ mỗi tháng kèm cơ sở ước tính (Q3).

## File chung (overview, object-storage, cache, messaging, consistency, backup-recovery)

- [ ] `object-storage.md`, `cache.md`, `messaging.md` chỉ vắng khi hồ sơ dự án ghi dòng cấp file `bỏ` kèm lý do (Q8); `overview.md` ghi "không có" ở dòng kho tương ứng. Không bỏ `messaging.md` mà `events.md` của service vẫn nhắc `EVT-`.
- [ ] `overview.md`: mỗi kho có một dòng; mỗi loại dữ liệu có đúng một nguồn sự thật; không định nghĩa `TBL-`, `BKT-`, `EVT-` ở đây.
- [ ] `object-storage.md`: mỗi bucket có heading `### BKT-…` (định nghĩa chỉ ở đây, khớp khóa trong `capacity/storage.yaml`), chủ sở hữu `SVC-…`, FR; số file, dung lượng, băng thông dẫn link `storage-sizing.md`, không chép số; vòng đời và thời hạn URL có cơ sở; có "Được dùng bởi" (`missing-backlink`).
- [ ] `messaging.md`: mỗi event có heading `### EVT-…` (định nghĩa chỉ ở đây), bên phát và bên nhận `SVC-…`, đảm bảo giao, cách xử lý trùng và thứ tự, thử lại và hàng đợi lỗi bằng số có cơ sở; mọi `EVT-…` mà `events.md` hoặc luồng nhắc đều có ở đây (`check_trace.py` báo `data-ref-missing`); có "Được dùng bởi".
- [ ] `cache.md`: mỗi mục cache có nguồn, thời gian sống (giây) kèm cơ sở, cách vô hiệu hóa; có hành vi khi cache trống và "Tối ưu" (tỉ lệ trúng cache) (Q2).
- [ ] `consistency.md`: mức nhất quán theo nghiệp vụ truy về FR, NFR hoặc C; cửa sổ bất nhất tối đa là số; giao dịch xuyên kho có quyết định `D-xxx`.
- [ ] `backup-recovery.md`: RPO và RTO bằng số truy về NFR và khớp `scaling-ha.md`; lịch sao lưu có thời gian giữ và nơi lưu khác vùng; diễn tập khôi phục có tiêu chí đạt bằng số; dung lượng sao lưu dẫn link `data-sizing.md` (Q4).
- [ ] Mỗi file chung có "Tối ưu" hoặc "Scale, nâng cấp, bảo trì" như template đòi, với chỉ số bằng số, đơn vị, NFR (Q2, Q3).

## Chung

- [ ] Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" với ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần không đạt (`check_numbers.py`).
- [ ] `calc_capacity.py` đầy đủ chạy sạch và `calc_capacity.py --check` khớp; `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_trace.py --gate G7` (mọi `TBL-`/`BKT-`/`EVT-` luồng nhắc có định nghĩa), `check_profile.py --gate G7 --templates …`, `check_workspace.py` sạch.
- [ ] Mỗi database có `capacity/db-constants/<db>-<major>.yaml` với mọi hằng số có link nguồn; mỗi database khai đủ giả định phình, WAL, bản sao, backup, TOAST, MAXALIGN.
- [ ] Quyết định và rủi ro mới (kiểu dữ liệu sắp tràn, dung lượng sát ngân sách) đã khai vào sổ rủi ro (Q6).
- [ ] Người dùng duyệt từng database.
