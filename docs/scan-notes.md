# Notas de quét (scan)

Kết quả dò thật trên Docker Desktop (Windows) ngày 2026-10-10, dùng làm căn cứ cho `agentflow scan`. Fixture mẫu nằm ở `foundation/tests/fixtures/scans/`.

## Image đã ghim

| Tool | Image | Ghi chú |
|---|---|---|
| Semgrep | `semgrep/semgrep:1.180.0` | Chạy với `--network none`, rule nạp từ file cục bộ |
| Trivy | `aquasec/trivy:0.75.0` | Cần mạng lần đầu để tải DB; DB nằm trong volume `agentflow-trivy-cache` |
| Gitleaks | `zricethezav/gitleaks:v8.24.0` | Đã dùng cho `agentflow commit` từ trước |
| Squawk | `ghcr.io/sbdchd/squawk:2.68.0` | Tag không có chữ `v` (tag `v2.68.0` không tồn tại trên GHCR) |
| Schemathesis | `schemathesis/schemathesis:4.30.1` | |

## Giấy phép rule Semgrep

Rule của Semgrep Registry theo *Semgrep Rules License v1.0*: chỉ được dùng cho mục đích nội bộ, và "does not allow you to distribute the rules". Vì repo này công khai nên **không có rule nào của Registry nằm trong repo**. `agentflow scan` tải rule lúc chạy từ `https://semgrep.dev/c/<ruleset>` (ví dụ `p/default`, trả về YAML ~2,4 MB) vào thư mục cache của người dùng, ngoài repo:

- Windows: `%LOCALAPPDATA%\agentflow\cache\semgrep-rules\`
- Nơi khác: `$XDG_CACHE_HOME/agentflow/semgrep-rules/` hoặc `~/.cache/agentflow/semgrep-rules/`
- Ghi đè bằng biến môi trường `AGENTFLOW_CACHE_DIR`.

Cache được mount chỉ đọc vào container. Nếu không tải được và chưa có cache thì `agentflow scan` báo lỗi cứng.

## Hành vi đã quan sát

- **Semgrep** `scan --config /rules --json --metrics=off --disable-version-check --quiet <file...>`: JSON ra stdout, mã thoát 0 dù có phát hiện (không dùng `--error`). Mức độ ở `results[].extra.severity` (`ERROR`, `WARNING`, `INFO`); id rule ở `results[].check_id` (có tiền tố `rules.` theo tên thư mục mount). Không có file nào khớp ngôn ngữ thì `results` rỗng.
- **Trivy** `fs --scanners vuln --format json --quiet /repo`: mã thoát 0. `Results[].Vulnerabilities[]` có `VulnerabilityID`, `Severity`, `FixedVersion` (rỗng nếu chưa có bản vá), `PkgName`, `Status`.
- **Gitleaks** `git --log-opts=<base>..<nhánh> --redact --report-format json --report-path - --exit-code 99`: `--report-path -` in JSON ra stdout (`/dev/stdout` không in gì). Mã thoát 99 khi có rò rỉ. Mỗi mục có `RuleID`, `File`, `StartLine`, `Fingerprint`, `Secret`/`Match` đã thành `REDACTED`.
- **Squawk** `--reporter json <file...>`: mã thoát 1 khi có vi phạm. Danh sách phẳng, mỗi mục có `rule_name`, `level` (`Warning`/`Error`), `file`, `line`, `message`.
- **Schemathesis**: mã thoát 0 đạt, 1 có lỗi, 2 không chạy được; `--url` bắt buộc với file schema.
- Git Bash trên Windows làm hỏng đường dẫn mount (`/w` thành `W:/`); `agentflow` gọi Docker bằng subprocess với đường dẫn Windows nguyên dạng nên không bị.
