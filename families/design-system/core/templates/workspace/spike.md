---
spike: S-<n>
layer: <data | messaging | backend | infrastructure | frontend | tooling | third-party>
image: <image:tag hoặc image@sha256:...>
network: none
timeout: 300
memory: 1g
cpus: 2
commands:
  - "<lệnh sh thứ nhất>"
  - "<lệnh sh thứ hai>"
expect:
  exit_code: 0
  output_contains: ["<chuỗi phải có trong đầu ra>"]
  output_not_contains: ["<chuỗi không được có>"]
---

# Spike S-<n>: <điều cần thử, một câu>

> Designer viết, đặt ở `.agent-workspace/stack/layers/<lớp>/spikes/S-<n>-<tên>.md` (`<lớp>` đúng bằng khóa `layer`). Phần giữa hai dấu `---` ở đầu file là dữ liệu cho `run_spike.py`; ba mục bên dưới là bản người đọc, phải khớp phần đó. Chỉ người dùng cho chạy: Orchestrator ghi dòng `S-<n>: chạy` của người dùng vào `state.md` (mục "Spike được duyệt chạy") kèm sha256 của file này; sửa file sau đó thì phải xin lại.
>
> **Khóa**
> - `spike`: ID, trùng phần đầu tên file. `layer`: lớp stack, trùng tên thư mục chứa file.
> - `image`: có tag hoặc digest cố định (không `latest`, không để trống tag). Container không được gắn thư mục nào của máy, không `--privileged`.
> - `network`: `none` (mặc định, không mạng) hoặc `bridge` (cần mạng thật, ví dụ tải gói); nói rõ lý do ở mục Lệnh.
> - `timeout` (giây, tối đa 1800), `memory` (ví dụ `512m`, `2g`), `cpus`: giới hạn tài nguyên; bỏ thì dùng mặc định trong `core/data/spike.yaml`.
> - `commands`: các lệnh `sh`, chạy lần lượt trong một container (`sh -ec`): lệnh nào lỗi thì dừng. Đầu ra gộp stdout và stderr. Không dùng lệnh cần tương tác.
> - `expect`: `exit_code` (mặc định 0), `output_contains` (mọi chuỗi phải có), `output_not_contains` (không chuỗi nào được có). Chỉ ghi thứ kiểm được bằng máy.
> - Kết quả (`đạt` / `không đạt` / `lỗi`) do `run_spike.py` ghi vào `S-<n>-<tên>.result.md`; không agent nào ghi file đó.

## Mục tiêu

<Giả thuyết cần kiểm và vì sao: truy về TC, NFR hoặc `R-xx`. Một đoạn ngắn.>

## Lệnh

<Mỗi lệnh làm gì. Nếu `network: bridge` thì ghi vì sao cần mạng.>

## Kết quả mong đợi

<Kết quả nào là đạt, bằng số hoặc chuỗi cụ thể, khớp `expect`.>
