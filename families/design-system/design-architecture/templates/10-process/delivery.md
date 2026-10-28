# Quy trình phát hành

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mức S bỏ cả phần 10-process. Pipeline tự động ở [ci-cd.md](../09-infrastructure/ci-cd.md); file này nói quy trình cho con người. Số người và thời gian của team lấy từ ràng buộc `C-xx`. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Nhánh và review
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Mô hình nhánh | <trunk-based, nhánh tính năng, GitFlow> | |
| Quy tắc review | <số người duyệt, ai được duyệt phần nào theo sở hữu mã> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Quy tắc đặt phiên bản | <semver, theo ngày> | |

## Phát hành
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Tần suất phát hành | <số lần mỗi tuần hoặc tháng> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Ai quyết định phát hành | <vai trò> | |
| Cửa sổ phát hành | <giờ trong ngày, ngày trong tuần, tránh giờ cao điểm theo workload-model.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Thay đổi khẩn cấp (hotfix) | <điều kiện, ai duyệt, kiểm tra tối thiểu> | |

## Rollback
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Khi nào quyết định rollback | <ngưỡng tỉ lệ lỗi hoặc độ trễ, thời gian quan sát (phút)> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Ai quyết định | <vai trò> | |
| Thời gian rollback tối đa (phút) | <số, khớp ci-cd.md> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Khi thay đổi đã chạm dữ liệu | <link data-change.md> | |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <thời gian từ khi merge đến khi chạy trên production (p95)> | <số + đơn vị> | <NFR-xx> | <CI, nhật ký phát hành> |
| <tỉ lệ phát hành phải rollback> | <phần trăm> | <NFR-xx> | <nhật ký phát hành> |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <rà quy trình, dọn nhánh cũ, cập nhật hướng dẫn phát hành> | <tháng, quý> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
