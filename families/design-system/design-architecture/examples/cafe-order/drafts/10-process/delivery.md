# Quy trình phát hành

## Nhánh và review
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Mô hình nhánh | trunk-based: nhánh tính năng sống ngắn, merge vào nhánh chính sau review | |
| Quy tắc review | một người duyệt khác tác giả, theo phần sở hữu mã ở [repo-structure.md](../06-backend/repo-structure.md) | C-002 |
| Quy tắc đặt phiên bản | semver cho API, theo mã commit cho bản build | |

## Phát hành
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Tần suất phát hành | tối đa 2 lần mỗi tuần | C-002 |
| Ai quyết định phát hành | nhân viên vận hành | |
| Cửa sổ phát hành | 10:00 đến 16:00 ngày làm việc, khi có người trực | C-002 |
| Thay đổi khẩn cấp (hotfix) | lỗ hổng mức nghiêm trọng theo hạn ở [secrets-compliance.md](../08-security/secrets-compliance.md) hoặc sự cố mức nghiêm trọng; một người duyệt, chạy đủ cổng chất lượng ở [ci-cd.md](../09-infrastructure/ci-cd.md) | |

## Rollback
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Khi nào quyết định rollback | tỉ lệ lỗi 5xx trên 5% trong 2 phút sau khi triển khai một máy ảo | NFR-002 |
| Ai quyết định | nhân viên vận hành, tự động theo [ci-cd.md](../09-infrastructure/ci-cd.md) | |
| Thời gian rollback tối đa (phút) | 10, khớp [ci-cd.md](../09-infrastructure/ci-cd.md) | NFR-002 |
| Khi thay đổi đã chạm dữ liệu | xem [data-change.md](data-change.md) | |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian từ khi merge đến khi chạy trên production (p95) | 30 phút | NFR-002 | lịch sử chạy workflow |
| tỉ lệ phát hành phải rollback | 5% | NFR-002 | nhật ký phát hành |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| rà quy trình, dọn nhánh cũ, cập nhật hướng dẫn phát hành | mỗi tháng | 1 giờ | C-002 |
