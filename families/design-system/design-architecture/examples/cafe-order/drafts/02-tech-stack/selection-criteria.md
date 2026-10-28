# Tiêu chí lựa chọn (TC)

## Tiêu chí loại trừ
<!-- required -->

| ID | Tiêu chí | Truy về (FR / NFR / C) | Ngưỡng (số + đơn vị) | Cách kiểm |
| --- | --- | --- | --- | --- |
| TC-001 | Phiên bản còn hỗ trợ ít nhất đến hết mốc 3y | NFR-002 | có / không | versions-features.md |
| TC-002 | Team 3 người đã có kỹ năng hoặc học được trước hạn | C-002, C-003 | có / không | team-readiness.md |

## Tiêu chí có trọng số
<!-- required -->

| ID | Tiêu chí | Truy về (FR / NFR / C) | Trọng số | Cách chấm 0–5 |
| --- | --- | --- | --- | --- |
| TC-003 | Chi phí vận hành nằm trong ngân sách | C-001 | 3 | 0 là vượt ngân sách, 5 là dưới một nửa |
| TC-004 | Đáp ứng thời gian phản hồi | NFR-001 | 2 | 0 là không đạt, 5 là đạt với biên dư |

## Áp dụng cho
<!-- required -->

Không đặt `TC-xx` ở ô đầu dòng (chỉ hai bảng trên định nghĩa TC).

| Áp dụng cho | Tiêu chí |
| --- | --- |
| lớp backend, lớp data, lớp frontend, lớp infrastructure, lớp third-party | TC-001, TC-002, TC-003, TC-004 |
