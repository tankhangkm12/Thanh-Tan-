# Tech stack

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. `check_versions.py` đọc bảng có cột "Công nghệ": **chỉ giữ một bảng như vậy trong file này**, mỗi công nghệ một dòng, mỗi dòng phải có dòng cùng tên và cùng phiên bản ở [versions-features.md](versions-features.md). Cột "Lớp" ghi tên lớp (frontend, backend, data, messaging, infrastructure, tooling, third-party); lớp third-party là lớp duy nhất được ghi phiên bản `YYYY-MM-DD` hoặc "SaaS, không phiên bản".

## Stack đã chốt
<!-- required -->

Tên công nghệ viết trước vai trò, cách nhau bằng " — " hoặc đặt vai trò trong ngoặc, để khớp với versions-features.md.

| Lớp | Công nghệ | Phiên bản | TC đáp ứng | Chi tiết |
| --- | --- | --- | --- | --- |
| <lớp> | <Tên — vai trò> | <major.minor> | <TC-xx, …> | [<lớp>](layers/<lớp>.md) |

## Quyết định
<!-- required -->

Mỗi lớp chốt bởi quyết định nào (hội đồng + người dùng duyệt) và rủi ro sinh ra.

| Lớp | Quyết định | Duyệt ngày | Rủi ro |
| --- | --- | --- | --- |
| <lớp> | <D-xxx> | <YYYY-MM-DD> | <R-xx, hoặc "không có"> |

## Kiểm tra chéo toàn stack
<!-- required -->

Kết quả kiểm tra chéo sau khi chốt mọi lớp: xem [compatibility.md](compatibility.md) (tương thích), [cost-licensing.md](cost-licensing.md) (chi phí so với ngân sách), [team-readiness.md](team-readiness.md) (kỹ năng). Ghi tóm tắt: <còn xung đột nào không, kèm số>.
