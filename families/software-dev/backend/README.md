# dev-backend

Plugin phát triển phía server của nhóm **software-dev** (phiên bản 0.2.0). Phụ thuộc `dev-core` (quy trình, gitflow, gate dùng chung) và chỉ thêm phần nghiệp vụ backend. Không giả định ngôn ngữ hay framework: mọi thông tin kỹ thuật lấy từ cấu hình dự án.

## Có gì bên trong

| Thành phần | Vị trí | Việc làm |
|---|---|---|
| Hợp đồng extension | `extension.yaml` | Role, quy tắc đường dẫn, quy tắc plan, tool scan, gate; `agentflow ext add` đọc file này |
| Role `db-engineer` | nguồn `src/roles/db-engineer.md` | **Role duy nhất** được viết migration. Sinh agent cho cả Claude Code và Antigravity bằng `tools/build.py` |
| Model | `src/roles/db-engineer.md` | `db-engineer` là một agent duy nhất (Claude Code: `sonnet`, effort `high`; Antigravity: `pro`) bất kể `tier` của mục; muốn dùng Opus cho migration khó, đổi `settings:` của nguồn role rồi `uv run tools/build.py --plugin families/software-dev/backend` (Opus tốn giới hạn hơn Sonnet) |
| 6 skill | `skills/*/SKILL.md` | `api-implementation`, `business-logic`, `db-migration`, `query-review`, `backend-testing`, `contract-test` |

## Gate và tool

| Gate / tool | Khi nào | Cách hoạt động |
|---|---|---|
| Quy tắc đường dẫn | `plan check` và `agentflow commit --item` | Mục kế hoạch hay commit đụng thư mục migration phải thuộc role `db-engineer` |
| Migration lên **và** xuống | `plan check` | `done-when` của mục có migration phải chứa nguyên văn lệnh lên và lệnh xuống của dự án (chạy trên DB trong container) |
| Squawk | bước `test` | Lint migration đã đổi khi `backend.db.engine` là `postgresql`; DB khác thì bỏ qua và `summary.md`/kết quả scan ghi rõ lý do |
| Schemathesis | bước `test` | Contract test (container) khi có `backend.openapi.spec` và `backend.openapi.url`; container gọi vào máy chủ qua `host.docker.internal` |

## Dùng với một dự án

1. Cài `agentflow` và hai plugin (`dev-core`, `dev-backend`); xem [README gốc](../../../README.md).
2. Trong dự án đã `agentflow init`, **bạn** chạy (không phải agent):

   ```
   agentflow ext add "<repo>/families/software-dev/backend/extension.yaml"
   agentflow config set backend.db.engine postgresql
   agentflow config set backend.migrations_dir db/migrations
   agentflow config set backend.migrations_lint_glob "db/migrations/*.up.sql"
   agentflow config set backend.migrate_up_command "<lệnh chạy migration lên trên DB trong container>"
   agentflow config set backend.migrate_down_command "<lệnh chạy migration xuống>"
   agentflow config set backend.test_command "<lệnh chạy test>"
   agentflow config set backend.openapi.spec openapi.yaml
   agentflow config set backend.openapi.url http://localhost:8000
   agentflow config check
   ```

3. Dùng như dev-core: `/dev-core:start`, rồi `/dev-core:continue`. Mục kế hoạch migration gán `role: db-engineer`, mục còn lại gán `implementer`.

## Dùng cùng dev-core

Khuôn yêu cầu task chỉ có một, ở [USAGE.md](../USAGE.md#khuôn-yêu-cầu-task) của nhóm; dev-backend không thay khuôn đó, chỉ thêm dữ liệu và ví dụ done-when cho gate của nó.

**Bước `test-spec` và migration.** `db-engineer` không có bước `test-spec` riêng: tester viết khối `test-spec` cho mọi mục kế hoạch, kể cả mục migration. Mục migration không có test đơn vị thì khai `- tests: không có — chạy lên/xuống/lên` (đúng lệnh lên và xuống trong `done-when`); `db-engineer` vẫn chứng minh bằng cách chạy chúng ở bước `implement`. Gate Squawk và Schemathesis ở bước `test` không đổi; gate `tests-pass` chạy thêm lệnh test của dự án.

**Dữ liệu cần thêm khi tạo task backend**
- **Contract API:** điền link tới contract OpenAPI vào dòng `Tài liệu` của khuôn. Có contract thì Schemathesis kiểm được dịch vụ có đúng contract không.
- **Migration:** nói rõ task có đụng migration hay không (ở `Trong phạm vi`). Có thì mục migration thuộc role `db-engineer` và `done-when` của nó phải chứa nguyên văn lệnh migration lên và xuống của dự án.
- **Cài đặt `backend.*`:** phải đặt **trước** khi tạo task (`agentflow config set backend.*`, rồi `agentflow config check`); xem [Dùng với một dự án](#dùng-với-một-dự-án). Gate Squawk và Schemathesis đọc các cài đặt này.

**Ví dụ done-when cho gate của dev-backend** (dùng chỗ trống thay cho lệnh cụ thể của dự án)

```
Xong khi: `<lệnh migration lên của dự án>` rồi `<lệnh migration xuống của dự án>` rồi lại `<lệnh migration lên của dự án>` đều chạy được; migration mới qua lint Squawk ở bước test.
```

```
Xong khi: `<lệnh test của dự án>` xanh; contract test Schemathesis ở bước test qua với spec trong `backend.openapi.spec`, dịch vụ đang chạy tại `backend.openapi.url`.
```

Squawk chỉ chạy khi `backend.db.engine` là `postgresql`; Schemathesis chỉ chạy khi có cả `backend.openapi.spec` và `backend.openapi.url`. Thiếu một trong hai thì gate bị bỏ qua và kết quả scan ghi rõ lý do, nên đừng ghi tiêu chí này vào `Xong khi` nếu cài đặt tương ứng chưa đặt.
