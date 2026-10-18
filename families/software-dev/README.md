# Nhóm software-dev

> **Bản nháp (MVP).** `dev-core` và `dev-backend` có nội dung dùng được; các plugin `dev-*` còn lại vẫn là khung.

Cách dùng nhóm (chọn plugin, chuẩn bị dự án, khuôn yêu cầu task, checklist duyệt): [USAGE.md](USAGE.md).

Nhóm plugin phục vụ phát triển phần mềm. `dev-core` giữ chuẩn chung của nhóm; các plugin con (`dev-design`, `dev-backend`, `dev-frontend`, `dev-infra`) phụ thuộc vào `dev-core` và chỉ thêm phần nghiệp vụ riêng.

| Plugin | Phạm vi |
|---|---|
| `dev-core` | Quy trình, gitflow, gate, hook an toàn, server MCP, quy ước, 5 skill và 7 role dùng chung |
| `dev-design` | Thiết kế giao diện (UI brief, design token, component spec) và thiết kế hệ thống (ADR, sơ đồ C4, contract API OpenAPI, data model) |
| `dev-backend` | Service, API, dữ liệu: role `db-engineer`, 6 skill, Squawk và Schemathesis qua extension (xem [README](backend/README.md)) |
| `dev-frontend` | Giao diện, state phía client |
| `dev-infra` | CI/CD, container, triển khai |

## Quy trình 7 bước

Định nghĩa trong [`core/workflow.yaml`](core/workflow.yaml), do `agentflow` thực thi.

| # | Bước | Role | Cần người duyệt | Fail thì |
|---|---|---|---|---|
| 1 | `confirm`: xác nhận task | orchestrator | có | blocked |
| 2 | `plan`: vào workspace, lập kế hoạch | planner | có | blocked |
| 3 | `test-spec`: viết test trước (gate `test-spec-valid`: agentflow tự chạy lại, phải đỏ) | tester | có, kể cả task small | quay về `plan` |
| 4 | `implement`: triển khai | implementer | không | blocked |
| 5 | `test`: kiểm thử (gate `tests-pass`: agentflow tự chạy, phải xanh) | tester | không | quay về `implement` |
| 6 | `security`: kiểm tra bảo mật | security | không | quay về `implement` |
| 7 | `review`: review | reviewer | có | quay về `implement` |

Không có bước "loop" riêng: fail ở `test`/`security`/`review` quay thẳng về `implement` và đếm vòng. Hết 3 vòng (`max_rounds`) task chuyển `blocked`, chỉ người mới cho làm tiếp (`agentflow task approve`, được ghi lại trong `.agentflow/decisions/`) hoặc hủy (`agentflow task cancel`).

Chỉ role `implementer` sửa code. `tester` chỉ ghi vào thư mục test; `orchestrator`, `planner`, `security`, `reviewer` không có tool sửa file và ghi báo cáo qua tool MCP `report_write` (dự phòng: `agentflow report`).

## Gitflow

- `main`: chỉ chứa bản đã phát hành.
- `develop`: nhánh tích hợp; nhánh `feature/...` và `bugfix/...` tách từ đây.
- `hotfix/...` tách từ `main`.
- Tên nhánh task: `<loại>/T-001-<slug>`, do `agentflow task new` tạo.
- Agent không tự `push`, không commit hay merge trên `main`/`develop`; hook của `dev-core` chặn các lệnh này.

## Gate bằng tool

Một bước chỉ được coi là xong khi tool xác nhận, không dựa vào nhận định của agent:

- Test: `uv run pytest` (hoặc test runner của dự án) phải xanh.
- Manifest plugin: `claude plugin validate` và `agy plugin validate` phải qua.
- Bí mật: `agentflow commit` quét Gitleaks (Docker/Podman) trên phần staged; engine không chạy là không commit.
- Bước `security` (gate `scans-clean`): `agentflow scan` chạy trong container Semgrep (rule từ Semgrep Registry, chặn mức `ERROR`), Trivy (chặn lỗ hổng `HIGH`/`CRITICAL` đã có bản vá) và Gitleaks (mọi phát hiện đều chặn); thêm Semgrep với rule do chính bạn viết khi có quy ước `check: semgrep`. Thiếu kết quả, kết quả cũ hoặc còn phát hiện chặn thì `task advance --result pass` bị từ chối.
- Bước `plan` (gate `plan-valid`): `agentflow plan check` kiểm mã mục, role, `done-when`, `docs`, luật `plan` của quy ước và mọi câu hỏi "Chưa có quy ước" đã được trả lời.
- Bước `review` (gate `conventions-reviewed`): báo cáo review phải có một dòng cho từng quy ước `check: review`.
- Bước `review` (gate `drift-reviewed`): báo cáo review phải có mục `## Đề xuất cập nhật hồ sơ` (`không có`, hoặc `- <tài liệu>: <đề xuất>`); gate chỉ kiểm hình thức, người kiểm tính đúng ở checklist Review.
- Plugin con thêm gate qua extension: `dev-backend` chạy Squawk (lint migration PostgreSQL) và Schemathesis (contract test) ở bước `test`, cùng gate `scans-clean`.
- Lint, type check và build của chính dự án vẫn do dự án khai báo trong `done-when` của kế hoạch; agentflow chưa có gate riêng cho chúng.
