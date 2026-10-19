# Kế hoạch design-architecture

Oct 12, 2026

**Trạng thái:** Giai đoạn 6 xong và đã gộp vào `develop`; đã chạy thử trên một dự án mẫu ở G0–G2, các gate sau G2 chưa chạy thử trên dự án thật. Chi tiết dựng ở mục "Trạng thái dựng" bên dưới.

## Mục tiêu và nguyên tắc nền

Plugin `design-architecture` (family Design) biến tài liệu BA thành một bộ tài liệu kiến trúc giải pháp đầy đủ, có số liệu thật, mà agent dev nhận vào là code được, không phải tự quyết thêm.

- **Đầu ra chỉ là tài liệu**, nằm trong `architecture/`, chỉ chứa nội dung đã chốt.
- **Bạn quyết mọi lựa chọn.** Phương án, so sánh, phiếu bầu và trạng thái duyệt chỉ nằm trong `.agent-workspace/`.
- **Phù hợp nhất với dự án, không phải tốt nhất.** Mọi đánh giá chấm theo hồ sơ dự án; làm quá tay bị trừ điểm.
- **Số liệu thật, không nói mồm.** Mọi con số có công thức, giả định và nguồn; phép tính do script chạy.
- **Chốt từ đầu.** Kiểu dữ liệu, kiến trúc, stack, phiên bản và rủi ro của từng phiên bản được thống nhất trước khi thiết kế chi tiết.
- **Hai chế độ:** thiết kế mới từ BA, hoặc nâng cấp từ bộ thiết kế cũ (agent đọc bản cũ trước).
- **Plugin stack-agnostic.** Kiến thức riêng từng stack lấy từ `~/knowledge/stacks/<stack>/`.

## 8 tiêu chí chất lượng

Mọi file đầu ra phải qua 8 tiêu chí này; chúng là nội dung checklist của Reviewer ở mọi gate.

| ID | Tiêu chí | Kiểm bằng cách nào |
| --- | --- | --- |
| Q1 | Đúng FR / NFR / ràng buộc | Mọi thành phần truy về ít nhất một FR, NFR hoặc ràng buộc; script truy vết báo thiếu |
| Q2 | Tối ưu theo từng tầng: frontend, backend, lưu trữ, hạ tầng, quy trình | Mỗi phần có mục "Tối ưu" với chỉ số mục tiêu bằng số |
| Q3 | Sẵn sàng mở rộng, nâng cấp, bảo trì | Mỗi thành phần có đường scale, đường nâng cấp và gánh nặng bảo trì ước tính |
| Q4 | Số liệu thật | Mọi con số có công thức, giả định (link `assumptions.md`) và nguồn chính thức; script tính lại khớp |
| Q5 | Kiểu dữ liệu, kiến trúc, stack, phiên bản rõ từ đầu | Ma trận phiên bản và tính năng đã được bạn duyệt ở gate stack |
| Q6 | Quản lý rủi ro | Mỗi quyết định sinh rủi ro vào sổ rủi ro; rủi ro điểm cao cần bạn chấp nhận rõ ràng |
| Q7 | Frontend sâu về kiến trúc, tối ưu cho thiết bị thật; không đụng GUI | Có ma trận thiết bị và ngân sách hiệu năng; không có quyết định visual nào |
| Q8 | Phù hợp với dự án | Độ sâu tài liệu khớp hồ sơ dự án đã duyệt; không có phần thừa so với hồ sơ |

## Hồ sơ dự án và mức độ áp dụng

Bước đầu tiên của mọi dự án là lập hồ sơ dự án và chọn mức áp dụng; bạn duyệt mức này trước khi làm bất cứ thứ gì khác (tiêu chí Q8).

Hồ sơ ghi: quy mô người dùng và dữ liệu dự kiến, mức độ quan trọng (mất dịch vụ thì thiệt hại gì), số người trong team, ngân sách, thời hạn, yêu cầu tuân thủ. Từ hồ sơ, agent đề xuất một mức:

| Mức | Ví dụ dự án | Phần bắt buộc | Hội đồng | Mốc tính số liệu |
| --- | --- | --- | --- | --- |
| S | Công cụ nội bộ, MVP | context (`00-context`), system tối thiểu (`architecture-style.md`, `containers.md`; thêm `integrations.md` khi dự án có hệ thống ngoài), stack, capacity rút gọn, luồng chính, backend, data, rủi ro rút gọn (chỉ rủi ro ≥ 8 điểm), `implementation-plan.md` | 3 phiếu, chỉ cho stack và kiểu kiến trúc | Lúc ra mắt, 1 năm |
| M | Sản phẩm thật, một team | Như S + system đầy đủ, frontend đầy đủ, security, infra, process, rủi ro đầy đủ, `scaling-stages.md`, `upgrade-roadmap.md` | 3 phiếu | Ra mắt, 1 năm, 3 năm |
| L | Nhiều team, nhiều client | Toàn bộ 13 phần, chi tiết từng service | 3 phiếu, 5 cho quyết định khó đảo ngược | Ra mắt, 1, 3, 5 năm |
| XL | Phân tán, tải lớn, yêu cầu tuân thủ cao | Toàn bộ + spike bắt buộc cho stack, DR chi tiết | 5 phiếu | Ra mắt, 1, 3, 5 năm + đỉnh tải |

Kết quả lưu ở `architecture/00-context/project-profile.md`: mức đã chốt và danh sách phần nào áp dụng, phần nào bỏ. Script kiểm tra và Reviewer đọc file này để biết phần nào được phép vắng.

## Cấu trúc đầu ra architecture/

Đầu ra gồm 13 phần đánh số `00` đến `12`; mỗi phần link hai chiều với các phần liên quan qua ID (`FR`, `NFR`, `TC`, `FL`, `SCR`, `SVC`, `API`, `EVT`, `TBL`, `BKT`, `R`).

```
architecture/
├── README.md                      # mục lục, phiên bản, mức áp dụng
├── CHANGELOG.md                   # chế độ nâng cấp: khác gì bản trước
│
├── 00-context/
│   ├── project-profile.md         # mức S/M/L/XL, phần nào áp dụng
│   ├── requirements-trace.md      # FR/NFR → FL → SVC → TBL/BKT
│   ├── quality-attributes.md      # NFR có số: tải, latency, uptime, RPO/RTO
│   ├── constraints.md             # ngân sách, team, hạ tầng, pháp lý, thời hạn
│   ├── assumptions.md             # mọi giả định dùng để tính số (DAU, tăng trưởng…);
│   │                              #   sinh từ capacity/assumptions.yaml bằng script, không sửa tay
│   └── glossary.md
│
├── 01-system/
│   ├── system-context.md          # C4 mức 1
│   ├── containers.md              # C4 mức 2
│   ├── architecture-style.md      # kiểu kiến trúc + giai đoạn scale
│   └── integrations.md            # hệ thống ngoài: cách gọi, lỗi, fallback
│
├── 02-tech-stack/
│   ├── README.md                  # lớp → công nghệ → phiên bản → TC đáp ứng
│   ├── selection-criteria.md      # TC-xx truy về FR/NFR/ràng buộc
│   ├── layers/                    # frontend, backend, data, messaging,
│   │                              #   infrastructure, tooling, third-party
│   ├── versions-features.md       # phiên bản, EOL, tính năng dùng, lỗi đã biết
│   ├── compatibility.md           # ma trận tương thích giữa các lớp
│   ├── cost-licensing.md
│   ├── team-readiness.md
│   └── exit-strategy.md           # đường thay thế từng công nghệ
│
├── 03-capacity/
│   ├── workload-model.md          # người dùng, req/s đỉnh, tỉ lệ đọc/ghi
│   ├── data-sizing.md             # byte/dòng, số dòng, dung lượng theo mốc
│   ├── storage-sizing.md          # object store: số file, dung lượng, băng thông
│   ├── compute-sizing.md          # năng lực mỗi instance, số instance cần
│   └── cost-model.md              # chi phí tháng theo từng mốc
│
├── 04-flows/
│   ├── flow-index.md
│   └── FL-xxx-<tên>.md            # sơ đồ tuần tự, lỗi, dữ liệu chạm tới
│
├── 05-frontend/
│   ├── overview.md                # client nào, chiến lược render
│   ├── device-matrix.md           # thiết bị, trình duyệt, OS, mạng hỗ trợ
│   ├── performance-budget.md      # bundle KB, LCP/INP/CLS, bộ nhớ
│   └── <app>/                     # web/, admin/, mobile/
│       ├── architecture.md        # lớp, ranh giới module, luồng dữ liệu
│       ├── routing-navigation.md  # SCR (của designer) ↔ route ↔ API
│       ├── state-data.md
│       ├── networking-offline.md
│       ├── auth-session.md
│       ├── build-delivery.md      # code splitting, CDN, cache asset
│       └── folder-structure.md
│
├── 06-backend/
│   ├── overview.md                # bản đồ service, ranh giới, mức tổ chức code A/B của từng service (định nghĩa dưới sơ đồ)
│   ├── communication.md           # sync/async, gateway, timeout, retry
│   ├── cross-cutting.md           # authN/Z, error model, logging, idempotency
│   ├── repo-structure.md
│   ├── contracts/
│   └── services/<service>/        # mỗi service hoặc module (modular monolith) một thư mục; xem "Đơn vị triển khai" ở responsibility.md
│       ├── responsibility.md
│       ├── api.md
│       ├── events.md
│       ├── domain-model.md
│       ├── data.md
│       ├── dependencies.md
│       ├── scaling.md             # đơn vị scale, giới hạn, số instance
│       └── folder-structure.md
│
├── 07-data/
│   ├── overview.md
│   ├── databases/<db>/
│   │   ├── erd.md
│   │   ├── tables.md              # kiểu dữ liệu + số byte từng cột
│   │   ├── access-patterns.md
│   │   ├── indexing.md
│   │   ├── partitioning-retention.md
│   │   └── migration-strategy.md
│   ├── object-storage.md
│   ├── cache.md
│   ├── messaging.md
│   ├── consistency.md
│   └── backup-recovery.md         # RPO/RTO, lịch backup, diễn tập khôi phục
│
├── 08-security/
│   ├── authz-matrix.md
│   ├── threat-model.md
│   └── secrets-compliance.md
│
├── 09-infrastructure/
│   ├── topology.md
│   ├── environments.md
│   ├── scaling-ha.md              # autoscale, HA, DR có số
│   ├── observability.md           # SLO, metric, cảnh báo
│   └── ci-cd.md
│
├── 10-process/
│   ├── delivery.md                # nhánh, release, rollback
│   ├── data-change.md             # migration, backfill
│   ├── maintenance.md             # lịch nâng cấp phiên bản, vá lỗi
│   └── operations.md              # xử lý sự cố, diễn tập backup
│
├── 11-risks/
│   └── risk-register.md
│
└── 12-roadmap/
    ├── scaling-stages.md          # ngưỡng số để lên giai đoạn sau
    ├── upgrade-roadmap.md         # nâng cấp theo ngày EOL
    └── implementation-plan.md     # gói docs giao cho từng agent dev
```

**Mức tổ chức code A/B (`06-backend/overview.md`, mỗi service một mức).** Là cách tổ chức code bên trong service, không liên quan số file tài liệu.

| Mức | Cách tổ chức | Dùng khi |
| --- | --- | --- |
| A (đơn giản) | Thư mục chia theo loại thành phần của framework (controller, service, repository, dto, entity…) | Service chủ yếu CRUD, logic mỏng |
| B (phân lớp) | domain / application / infrastructure / presentation; phụ thuộc hướng vào domain, domain không phụ thuộc framework hay ORM; interface ở domain hoặc application, hiện thực ở infrastructure | Có quy tắc nghiệp vụ, trạng thái, tính toán; có tích hợp dịch vụ ngoài; hoặc sắp tách thành microservice |

Nâng từ A lên B làm riêng từng service khi nó phình ra. `overview.md` ghi mức và cơ sở chọn (ID FR, NFR, D…); `folder-structure.md` của service phải khớp mức đã ghi. Không có script kiểm; Reviewer soát theo checklist 06-backend.

## Quy tắc số liệu và sizing

Mọi con số trong đầu ra phải tính lại được: nó có giá trị, đơn vị, công thức, giả định đầu vào và nguồn; phép tính do script chạy, không để model tính nhẩm (tiêu chí Q4).

**Năm thành phần bắt buộc của một con số**

| Thành phần | Ví dụ |
| --- | --- |
| Giá trị + đơn vị | 292 MB/năm |
| Công thức | số dòng/năm × byte/dòng |
| Giả định | 10.000 đơn/ngày (link `assumptions.md`) |
| Hằng số có nguồn | `bigint` = 8 byte (link tài liệu chính thức của DB và phiên bản đã chọn) |
| Mốc thời gian | ra mắt, 1, 3, 5 năm theo mức áp dụng |

Các từ như "nhanh", "lớn", "đủ dùng", "scale tốt" không có số đi kèm là lỗi chặn khi review.

**Kiểu dữ liệu chọn theo số, không theo thói quen.** Mỗi cột trong `tables.md` ghi kiểu, số byte và lý do. Quy tắc: chọn kiểu nhỏ nhất vẫn đủ cho mốc xa nhất cộng biên an toàn. Ví dụ với PostgreSQL: `integer` (4 byte) có giá trị lớn nhất 2.147.483.647. Bảng thêm 10.000 dòng/ngày thì dùng được hàng trăm năm, nên giữ `integer`. Bảng thêm 1 triệu dòng/ngày (365 triệu/năm) thì hết sau khoảng 5,9 năm, nên phải dùng `bigint` (8 byte) ngay từ đầu.

**Dung lượng dữ liệu** = (phần đầu dòng + con trỏ dòng + tổng byte các cột + padding căn lề) × số dòng, cộng index. Các hằng số phần đầu dòng và căn lề kiểu lấy từ tài liệu chính thức của DB đã chọn; MAXALIGN phụ thuộc nền tảng nên là giả định (x86_64 hoặc arm64, có nguồn), không phải hằng số. Ví dụ: 10.000 đơn/ngày là 3,65 triệu dòng/năm; với khoảng 80 byte/dòng thì cỡ 292 MB/năm, chưa tính index.

**Hai con số cho dữ liệu của mỗi database.** *Dung lượng logic* là số tính từ dòng, trang và index như trên. *Dung lượng cần cấp* là số thật phải mua: `(heap × hệ số phình heap + index × hệ số phình index + WAL) × (1 + số bản sao) + số backup × dữ liệu sau phình`, và chi phí lưu trữ database tính trên số này. Các thứ script không mô hình được nên bắt buộc khai thành giả định cho **mỗi database** (`database_assumptions` trong `assumptions.yaml`): hệ số phình heap và index, dung lượng WAL giữ lại, số bản sao, số backup giữ lại, tỉ lệ cột vượt ngưỡng TOAST (TOAST chưa được mô hình; `data-sizing.md` nói rõ và ghi tỉ lệ đã khai) và MAXALIGN. Mỗi giả định có giá trị và nguồn hoặc lý do; giá trị 0 (hoặc hệ số phình 1) được phép nhưng phải có `reason`; thiếu là lỗi.

**Tải tính toán** đi từ giả định người dùng:

```
req/s đỉnh = (DAU × request/người/ngày) / 86 400 × hệ số đỉnh
```

Hệ số đỉnh và biên an toàn cũng là giả định, nằm trong `assumptions.md` và được bạn duyệt.

**Object storage** = số file/ngày × kích thước trung bình × thời gian lưu; băng thông ra = lượt xem × kích thước. **Chi phí** lấy từ trang giá chính thức, ghi ngày tra cứu.

**Cách làm:** Designer ghi giả định và tham số vào `capacity/*.yaml` trong workspace; script `calc_capacity.py` sinh bảng số vào bản nháp; Reviewer chạy lại script và đối chiếu. Mỗi khi kiểu dữ liệu hay giả định đổi, toàn bộ số được tính lại. `capacity/assumptions.yaml` là nguồn duy nhất của giả định; `00-context/assumptions.md` sinh từ nó, và `check_numbers.py` báo lỗi nếu hai file lệch.

**Hằng số của DB không viết cứng trong script.** Phần đầu dòng, căn lề, kích thước kiểu, kích thước trang, fillfactor nằm trong `capacity/db-constants/<db>-<major>.yaml` (mỗi hằng số có `value` và `source` là link tài liệu chính thức; link vào mã nguồn phải trỏ **tag phát hành cố định** như `REL_16_4`, không trỏ nhánh như `REL_16_STABLE`; file có `looked_up`), và `calc_capacity.py` chỉ đọc từ đó (hoặc từ `--constants-dir`). Nguồn dùng lại giữa các dự án là `~/knowledge/stacks/<db>/constants-<major>.yaml`; ở G4, sau khi chốt DB, Researcher xác minh lại từng link rồi chép vào workspace. Hằng số hay đơn giá thiếu nguồn thì script báo lỗi và không tính. Schema các file `capacity/*.yaml`: [core/workflow/capacity-schema.md](core/workflow/capacity-schema.md).

## Phiên bản và ma trận tính năng

Mỗi công nghệ trong stack được chốt đến phiên bản cụ thể ở gate stack, kèm những tính năng dự án dựa vào và rủi ro của chính phiên bản đó; sau gate này, đổi phiên bản phải đi qua chế độ nâng cấp và ghi vào `CHANGELOG.md` (tiêu chí Q5).

**Tiêu chí lựa chọn đi trước ứng viên.** Agent rút tiêu chí `TC-xx` từ FR, NFR và ràng buộc; bạn duyệt tiêu chí và trọng số trước khi bất kỳ ứng viên nào được nêu tên. Tiêu chí không có nguồn thì không được dùng. Tiêu chí loại trừ gạt ứng viên trước; tiêu chí có trọng số chỉ xếp hạng phần còn lại.

**Mỗi dòng trong `versions-features.md`**

| Cột | Nội dung |
| --- | --- |
| Công nghệ | Tên + vai trò (ví dụ: database quan hệ cho `order-db`) |
| Phiên bản chốt | major.minor, chính sách nhận bản vá. Riêng lớp third-party được thêm hai dạng: phiên bản theo ngày (YYYY-MM-DD) và "SaaS, không phiên bản" (khi đó ô vòng đời phải link changelog hoặc chính sách ngừng hỗ trợ của dịch vụ) |
| Ngày phát hành, ngày hết hỗ trợ | Link trang vòng đời chính thức. Phiên bản đã hết hỗ trợ tại ngày chạy kiểm tra là lỗi chặn; hết hỗ trợ trong 12 tháng thì cột Rủi ro phải link `R-xx` |
| Tính năng dự án dựa vào | Mỗi tính năng ghi phiên bản tối thiểu cần có |
| Giới hạn và lỗi đã biết | Của đúng phiên bản này, có link issue hoặc release note |
| Thay đổi phá vỡ ở bản lớn kế tiếp | Ảnh hưởng gì khi nâng cấp sau này |
| Tương thích | Phiên bản tối thiểu của driver, SDK, lớp khác |
| Rủi ro | Link sang `R-xx` trong sổ rủi ro |

**Ai thu thập dữ kiện:** agent Researcher, bắt buộc kèm link nguồn chính thức. Dữ kiện không có nguồn là lỗi chặn; hội đồng chỉ chấm trên dữ kiện đã có nguồn.

**Kiểm tra chéo toàn stack** sau khi chốt từng lớp: tương thích giữa các phiên bản, tổng chi phí so với ngân sách, kỹ năng team. Từng lớp phù hợp riêng lẻ chưa đủ; ghép lại cũng phải khớp.

## Quản lý rủi ro

Rủi ro được ghi ngay khi nó xuất hiện, không đợi đến cuối: mỗi brief quyết định, mỗi dòng phiên bản, mỗi bảng sizing và mỗi khoảng trống kỹ năng đều phải khai rủi ro vào sổ (tiêu chí Q6). Sổ được mở ở G1 với rủi ro sớm sinh ra từ NFR và ràng buộc, bổ sung ở mỗi gate sau đó và hoàn thiện ở G9.

**Mỗi dòng trong `11-risks/risk-register.md`**

| Cột | Nội dung |
| --- | --- |
| ID | `R-xx` |
| Mô tả | Điều gì có thể xảy ra, hậu quả cụ thể |
| Nhóm | Công nghệ, phiên bản, capacity, vendor, bảo mật, dữ liệu, team, tiến độ, vận hành |
| Khả năng × Tác động | Mỗi thang 1–5, điểm = tích, tối đa 25 |
| Thành phần liên quan | Link `SVC`, `TBL`, `BKT`, công nghệ trong stack |
| Dấu hiệu sớm | Chỉ số có ngưỡng bằng số, ví dụ CPU DB > 70% trong 15 phút |
| Giảm thiểu | Làm gì trước để giảm khả năng hoặc tác động |
| Phương án dự phòng | Làm gì khi rủi ro đã xảy ra |
| Trạng thái | Đang theo dõi, đang giảm thiểu, đã chấp nhận, đã đóng |

**Ngưỡng xử lý**

| Điểm | Xử lý |
| --- | --- |
| 15–25 | Bắt buộc có giảm thiểu; nếu vẫn giữ, bạn phải chấp nhận rõ ràng (ghi trong workspace) |
| 8–14 | Bắt buộc có giảm thiểu và dấu hiệu sớm |
| 1–7 | Theo dõi, có dấu hiệu sớm |

Ở mỗi gate, Reviewer soát lại sổ: rủi ro mới từ giai đoạn vừa làm đã được khai chưa, điểm có cần chấm lại không. Phát hành snapshot chỉ khi mọi rủi ro từ 15 điểm trở lên đã được giảm thiểu hoặc được bạn chấp nhận.

Sổ rủi ro có ở mọi mức áp dụng và nằm trong `architecture/` (workspace không được commit). Mức S dùng bản rút gọn: chỉ ghi rủi ro từ 8 điểm trở lên.

## Phạm vi kiến trúc frontend

Frontend được thiết kế sâu ở phần kỹ thuật và tối ưu cho thiết bị thật của người dùng; mọi thứ thuộc về giao diện nhìn thấy được để cho designer (tiêu chí Q7).

| Thuộc kiến trúc (làm) | Thuộc designer (không đụng) |
| --- | --- |
| Chiến lược render từng app (CSR, SSR, SSG, kết hợp) và lý do từ NFR | Màu, font, bố cục, khoảng cách |
| Ma trận thiết bị: OS, trình duyệt, lớp màn hình, RAM máy yếu, điều kiện mạng | Hình dáng component, icon, minh họa |
| Ngân sách hiệu năng: KB JS tải ban đầu, LCP, INP, CLS, bộ nhớ, dung lượng app mobile | Hiệu ứng chuyển động, micro-interaction |
| Lớp và ranh giới module, luồng dữ liệu, quản lý state | Nội dung chữ trên giao diện |
| Lấy dữ liệu, cache, offline và đồng bộ, retry | Thứ tự và cách sắp xếp màn hình |
| Phiên đăng nhập, nơi lưu token, phân quyền màn hình | |
| Build và phân phối: code splitting, CDN, pipeline ảnh theo kích thước thiết bị | |
| Đo thực tế người dùng (RUM), báo lỗi client | |

**Ngân sách hiệu năng phải là số.** Ví dụ dùng ngưỡng "tốt" của Core Web Vitals làm mức sàn (LCP ≤ 2,5 s, INP ≤ 200 ms, CLS ≤ 0,1), rồi siết thêm theo hồ sơ dự án và máy yếu nhất trong ma trận thiết bị.

**Nối với designer qua ID màn hình.** `routing-navigation.md` dùng `SCR-xx` lấy từ tài liệu của designer và chỉ ghi route, dữ liệu cần, API gọi. Khi kiến trúc cần designer làm thêm điều gì (ví dụ trạng thái khi mất mạng), agent ghi câu hỏi vào `questions.md`, không tự quyết phần nhìn.

## Các agent và quyền ghi

Mỗi việc giao cho một agent độc lập, chạy trong context riêng, chỉ được đọc đúng file mình cần và chỉ được ghi vào đúng vùng của mình; không agent nào được ghi trạng thái "Đã duyệt".

| Agent | Việc | Được ghi vào | Model / effort |
| --- | --- | --- | --- |
| Orchestrator (phiên chính) | Chạy workflow, dò model, gọi agent, cập nhật trạng thái; không tự thiết kế | `state.md`, `models.md`; ngoài ra chỉ dòng "Trạng thái" trong `plan/tasks/*.md` | Model của phiên bạn mở / medium |
| Planner | Đọc input, lập hồ sơ dự án, chia task, viết checklist, gom câu hỏi | `plan/`, `questions.md`, nháp `project-profile` | Theo `models.md` / high |
| Researcher | Longlist công nghệ, dữ kiện phiên bản, EOL, giấy phép, giá, giới hạn, có link nguồn | `stack/` (trừ `*.result.md` của spike), `capacity/db-constants/<db>-<major>.yaml` (hằng số DB đã xác minh nguồn) | Model có tìm web trong `models.md` / medium |
| Designer | Viết brief phương án; sau khi bạn chốt thì viết bản nháp docs và tham số capacity | `decisions/*/brief.md`, `drafts/`, `capacity/` (trừ `capacity/db-constants/`), `questions.md` (thêm câu hỏi), `stack/layers/<lớp>/spikes/S-xx-<tên>.md` (đề bài spike) | Theo `models.md` / high |
| Hội đồng (3 hoặc 5) | Chấm và bỏ phiếu độc lập | `decisions/*/votes/` | Mỗi thành viên một model khác nhau trong `models.md` |
| Reviewer | Soát bản nháp theo 8 tiêu chí và checklist, chạy lại script; không sửa | `reviews/` | Khác model với Designer / high |
| Script | Đếm phiếu, tính capacity, sinh `assumptions.md`, kiểm link, truy vết, chuyển bản nháp đã duyệt | `tally.md`, `r1-summary.md`, `drafts/03-capacity/`, `drafts/00-context/assumptions.md`, khối bảng số trong `tables.md`, kết quả spike `S-xx-<tên>.result.md`, `checks/`, `architecture/` | Không phải agent |

Chỉ script `promote_drafts.py` được ghi vào `architecture/`, và chỉ chạy sau khi bạn duyệt gate. Nhờ vậy đầu ra luôn đúng nghĩa "chỉ nội dung đã chốt". Ngoại lệ duy nhất: `archive_release.py` thêm mục phát hành vào `architecture/CHANGELOG.md` sau khi bạn duyệt G10 (không chép nội dung thiết kế).

**Danh mục model tự dò.** Ở G0, Orchestrator kiểm tra model nào gọi được trong môi trường hiện tại: các model của Claude Code, và CLI khác như Antigravity nếu đã cài và chạy được ở chế độ không tương tác. Kết quả ghi vào `.agent-workspace/models.md`: tên, cách gọi, có tìm web không, điểm mạnh, giới hạn. Mỗi lần gọi agent, Orchestrator chọn model từ danh mục này; model gọi lỗi thì bị đánh dấu không dùng được và được thay bằng model khác. Bạn xem danh mục ở gate G0.

**Hai cách gọi model.** Mỗi dòng trong `models.md` ghi rõ loại:

- *Subagent Claude*: model Claude Code gọi được (`sonnet`, `opus`, `haiku`, `fable`, ID đầy đủ). Mọi file agent đặt `model: inherit`; Orchestrator **luôn truyền model lúc gọi** subagent, lấy từ `models.md` (tham số lúc gọi thắng frontmatter). Theo tài liệu Claude Code ([sub-agents](https://code.claude.com/docs/en/sub-agents#choose-a-model)): `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` ép mọi subagent chạy một model; `CLAUDE_CODE_SUBAGENT_MODEL` chỉ ghi đè cả tham số lúc gọi ở Claude Code trước v2.1.251. `detect_models.py` cảnh báo nếu một trong hai đang đặt. Dò tĩnh liệt kê model nhưng mọi model ở trạng thái "chưa thử" và chưa được dùng; `--probe <danh sách>` chỉ thử gọi đúng các model trong danh sách (không kèm danh sách là lỗi tham số). Ở G0 Orchestrator chọn trước các model dự định dùng (phiên chính, Reviewer, đủ thành viên hội đồng theo mức) rồi `--probe` đúng các model đó, một lần. Cột "Tìm web" của model Claude ghi theo tool (WebSearch, WebFetch), của CLI ngoài là "chưa rõ" trừ khi khai qua `--web-models`.
- *Qua CLI ngoài*: model của CLI khác (ví dụ Antigravity, Gemini) không thể là subagent trong Claude Code. Chỉ làm được thành viên hội đồng: script gọi CLI ở chế độ không tương tác, đưa nguyên phần thân file góc nhìn kèm `brief.md` qua stdin (cách đưa theo từng CLI nằm ở `core/data/cli.yaml`; đối số `-p` chỉ là dự phòng), rồi ghi phiếu đúng định dạng `vote.md`. Vì vậy phần thân mỗi file góc nhìn của hội đồng tự đứng được, không dựa vào tool hay cú pháp riêng của Claude Code.

Quy tắc gán model:

- Hội đồng: mỗi thành viên một model khác nhau. Không đủ model thì dùng chung model với góc nhìn khác nhau, và `decision.md` ghi rõ độ đa dạng bị giảm.
- Reviewer luôn khác model với Designer của phần đang soát.
- Ưu tiên Sonnet cho phiên chính và các bước dài để giữ giới hạn gói Pro.

**Ngữ cảnh độc lập.** Mỗi agent chạy trong ngữ cảnh riêng, không mang lịch sử trò chuyện hay suy luận của agent khác, để phản biện thật sự độc lập.

- Mỗi agent chỉ nhận đúng danh sách file Orchestrator truyền cho task đó.
- Thành viên hội đồng chỉ đọc `brief.md` và phần context được trích; vòng 1 không thấy phiếu nào khác, vòng 2 chỉ thấy bản tóm tắt ẩn danh.
- Designer không thấy phiếu từng người, chỉ thấy quyết định cuối của bạn.
- Reviewer chỉ đọc bản nháp, template, checklist và nguồn gốc (BA, `assumptions`) và bản ghi quyết định, chấp nhận rủi ro của người dùng (`decision-log.md`, `acceptance.md`); không đọc brief hay lý luận của Designer, để soát như người ngoài.
- Agent trao đổi với nhau chỉ qua file trong workspace, không truyền tin trực tiếp.

## Hội đồng bỏ phiếu quá bán

Trước khi một quyết định lớn đến tay bạn, một hội đồng gồm các model khác nhau, mỗi thành viên một góc nhìn, bỏ phiếu độc lập; phương án nào được hơn 50% số phiếu mới thành đề xuất, còn bạn vẫn là người quyết cuối cùng.

**Thành phần, mỗi góc nhìn gắn với tiêu chí chất lượng**

| Góc nhìn | Hỏi gì | Tiêu chí | Model | Khi nào có |
| --- | --- | --- | --- | --- |
| Phù hợp và vừa sức | Đúng hồ sơ dự án không, team và thời hạn làm nổi không | Q8, Q1 | Gán từ models.md | Luôn có |
| Chi phí và vận hành | Tốn bao nhiêu mỗi tháng, ai vận hành, lỗi thì sao | Q2 | Gán từ models.md | Luôn có |
| Số liệu và NFR | Có đạt ngưỡng trong `quality-attributes` theo số đã tính không | Q4, Q1 | Gán từ models.md | Luôn có |
| Tiến hóa | Mở rộng, nâng cấp phiên bản, bảo trì có dễ không | Q3, Q5 | Gán từ models.md | Hội đồng 5 |
| Rủi ro và dữ liệu | Toàn vẹn, mất mát, bảo mật, khóa vendor | Q6 | Gán từ models.md | Hội đồng 5 |

**Quy tắc chấm "phù hợp nhất"**

- Brief do Designer viết trình bày các phương án trung lập, không kèm khuyến nghị.
- Mỗi thành viên chấm từng phương án theo các `TC` và chỉ thấy brief, không thấy phiếu của người khác. Thành viên chỉ ghi điểm thô 0–5 theo từng TC (TC loại trừ ghi đạt hoặc không đạt) và điểm trừ làm quá tay kèm lý do; `tally_votes.py` tính tổng có trọng số từ brief, loại phương án vi phạm TC loại trừ khỏi phiếu đó, và báo lỗi phiếu nếu lựa chọn lệch phương án có tổng cao nhất.
- **Công thức tổng** (do `tally_votes.py` tính, thành viên không ghi tổng): `tổng = Σ(điểm × trọng số) / (5 × Σ trọng số) × 100 − điểm trừ làm quá tay`, tính trên các TC có trọng số trong brief. Phương án vi phạm TC loại trừ bị loại khỏi phiếu đó. Script so sánh bằng giá trị chưa làm tròn, chỉ làm tròn 1 chữ số thập phân khi hiển thị. Hai phương án chênh nhau dưới 0,01 điểm coi là hòa: thành viên phải ghi `tie_reason`.
- Mỗi lý do phải trích một `TC`, `NFR`, ràng buộc, con số trong `03-capacity` hoặc `R-xx`. Lý do kiểu "chuẩn ngành", "đang phổ biến" không được tính. Mọi con số trong một lý do phải xuất hiện nguyên văn trong `brief.md` (hội đồng chỉ đọc brief, brief trích số từ `03-capacity`); số không có trong brief thì `tally_votes.py` từ chối phiếu.
- Phương án vượt xa nhu cầu mà tốn thêm chi phí hoặc độ phức tạp bị trừ điểm.
- Điểm trừ làm quá tay tối đa 20 mỗi phương án mỗi phiếu (`core/data/council.yaml`); vượt thì `tally_votes.py` từ chối phiếu.
- Luôn có lựa chọn "không phương án nào phù hợp".

**Đếm phiếu** (script `tally_votes.py`): quá bán nghĩa là 2/3 hoặc 3/5 phiếu.

1. Vòng 1 bỏ phiếu kín. Có phương án quá bán thì thành đề xuất.
2. Không quá bán thì sang vòng 2: mỗi thành viên đọc `r1-summary.md`, rồi bỏ phiếu lại. File này do `tally_votes.py` sinh, không do model tóm tắt: gom nguyên văn phần "Lý do" của từng phiếu vòng 1, xóa member, model và góc nhìn, xáo thứ tự ngẫu nhiên.
3. Vẫn không quá bán thì trình bạn hai phương án dẫn đầu, ghi rõ "chưa đạt đồng thuận".
4. "Không phương án nào phù hợp" thắng thì Designer làm lại brief.

`decision.md` trình cho bạn: phương án đề xuất, tỉ lệ phiếu, ý kiến thiểu số (luôn hiển thị), rủi ro mới sinh ra.

**Việc nào đưa ra hội đồng:** kiểu kiến trúc, stack từng lớp, phiên bản chốt, ranh giới service, loại database, chiến lược nhất quán dữ liệu, kiểu dữ liệu của các bảng tăng nhanh nhất, đặc biệt khóa chính và khóa ngoại. Chi tiết nhỏ hơn do Designer viết thẳng, Reviewer soát. Điều này giữ lượt dùng trong giới hạn gói Pro.

**Quyết định khó đảo ngược** (hội đồng 5 phiếu ở mức L): đổi sau khi có dữ liệu production thì phải migrate dữ liệu hoặc tách/gộp service. Danh sách mặc định: kiểu kiến trúc, loại database, ranh giới service, chiến lược nhất quán dữ liệu, kiểu dữ liệu của các bảng tăng nhanh nhất, đặc biệt khóa chính và khóa ngoại. Planner được đề xuất thêm ở G0; bạn duyệt.

## Các giai đoạn và gate

Quy trình có 11 gate theo thứ tự cố định; mỗi gate chỉ qua khi đủ điều kiện và bạn duyệt.

| Gate | Giai đoạn | Bạn duyệt gì |
| --- | --- | --- |
| G0 | Khởi tạo và hồ sơ dự án | Mức áp dụng, các phần áp dụng và danh mục model |
| G1 | Context | FR, NFR có số, ràng buộc, giả định |
| G2 | Tiêu chí lựa chọn TC | Tiêu chí và trọng số, trước mọi ứng viên |
| G3 | Kiểu kiến trúc | Kiểu kiến trúc và giai đoạn scale (hội đồng) |
| G4 | Stack và phiên bản | Từng lớp, ma trận phiên bản, kiểm tra chéo |
| G5 | Capacity sơ bộ | Tải, dung lượng, chi phí theo từng mốc |
| G6 | Luồng chính | Luồng, trước khi thiết kế chi tiết |
| G7 | Thiết kế chi tiết | Từng service, từng database, từng app frontend (có thể quay lại G5 để tính lại capacity theo kiểu dữ liệu thật) |
| G8 | Bảo mật, hạ tầng, quy trình | Từng phần |
| G9 | Rủi ro và roadmap | Sổ rủi ro (mở từ G1, hoàn thiện ở đây); rủi ro từ 15 điểm đã được xử lý |
| G10 | Kiểm tra chéo và phát hành | Tính lại toàn bộ số, mọi script sạch, phát hành vN |

G5 tính capacity sơ bộ, G7 tính lại theo kiểu dữ liệu thật, G10 tính lại lần cuối trước khi phát hành.

**Vòng làm việc trong mỗi giai đoạn**

1. Planner lập task và checklist "xong khi".
2. Gom câu hỏi, bạn trả lời.
3. Quyết định lớn: Designer viết brief, hội đồng bỏ phiếu, bạn quyết.
4. Designer viết bản nháp theo template, script tính số.
5. Reviewer soát theo 8 tiêu chí và chạy lại script.
6. Gate: mọi task đã đóng, không còn quyết định chờ, không còn lỗi chặn, script sạch, bạn duyệt; script chuyển bản nháp sang `architecture/`.

Ở chế độ nâng cấp, G0 đọc `previous-design/` trước, và mỗi gate chỉ làm lại phần có thay đổi.

## Mở session mới và tiếp tục

Mở session mới vẫn dùng bình thường, không cần làm gì thêm: mọi trạng thái nằm trong file, nên agent tự đọc và làm tiếp đúng chỗ đã dừng.

- `state.md` là điểm vào duy nhất: giai đoạn hiện tại, gate đã qua, task đang mở, câu hỏi đang chờ, việc tiếp theo.
- `init_workspace.py` tạo file hướng dẫn dự án mà CLI tự đọc khi mở session (ví dụ `CLAUDE.md` với Claude Code), ghi một quy tắc: đọc `.agent-workspace/state.md` trước khi làm gì khác. File này cũng nằm trong `.gitignore`, vì là thứ của agent.
- Mỗi task và mỗi gate kết thúc bằng việc cập nhật `state.md`. Session có đứt giữa chừng thì chỉ mất phần đang làm dở của task hiện tại.
- Không dựa vào lịch sử chat: quyết định bạn nói trong chat được Orchestrator ghi ngay vào `decision.md` rồi mới làm tiếp.
- Workspace chỉ ở local, nên tiếp tục phải trên cùng máy, hoặc bạn tự chép `.agent-workspace/` sang máy khác.

Nên mỗi session làm trọn một giai đoạn để ngữ cảnh phiên chính gọn.

## Cấu trúc .agent-workspace/

`.agent-workspace/` nằm cạnh `architecture/` trong repo thiết kế, chỉ ở máy local và có trong `.gitignore`; mọi thứ agent làm dở, mọi phương án và phiếu bầu nằm ở đây.

```
.agent-workspace/
├── state.md                       # ĐIỂM VÀO: giai đoạn, gate đã qua, task mở,
│                                  #   câu hỏi chờ, việc tiếp theo
├── models.md                      # model gọi được, cách gọi, tìm web, giới hạn
│
├── inputs/                        # chỉ đọc
│   ├── ba/                        # tài liệu BA bạn đưa trong prompt, Orchestrator lưu lại
│   ├── ui-design/                 # danh sách SCR-xx từ designer (nếu có)
│   └── previous-design/           # chế độ nâng cấp: bản architecture/ cũ
│
├── plan/
│   ├── plan.md                    # giai đoạn, task, phụ thuộc
│   └── tasks/T-xxx-<tên>.md       # mô tả, checklist "xong khi", trạng thái
│
├── questions.md                   # câu hỏi chờ bạn (mở / đã trả lời)
│
├── stack/
│   ├── layers/<lớp>/
│   │   ├── longlist.md            # ứng viên + dữ kiện có nguồn
│   │   ├── knockout.md            # ai bị loại, vì TC nào
│   │   ├── shortlist.md
│   │   ├── scoring.md             # bảng chấm theo trọng số
│   │   └── spikes/S-xx-<tên>.md   # đề bài (Designer) thử nhỏ trong container; kết quả S-xx-<tên>.result.md
│   │                              #   do run_spike.py sinh (XL: bắt buộc cho data, messaging, backend, infrastructure)
│   └── cross-check.md             # kiểm tra chéo toàn stack
│
├── capacity/
│   ├── assumptions.yaml           # DAU, tăng trưởng, hệ số đỉnh, biên an toàn
│   ├── tables.yaml                # bảng, cột, kiểu, số dòng/ngày
│   ├── storage.yaml               # file/ngày, kích thước, thời gian lưu
│   ├── compute.yaml               # năng lực mỗi instance
│   ├── pricing.yaml               # đơn giá + link + ngày tra cứu
│   └── db-constants/<db>-<major>.yaml   # hằng số DB (đầu dòng, căn lề, kích thước kiểu), từng hằng số kèm link nguồn
│
├── decisions/
│   ├── decision-log.md            # ID, câu hỏi, trạng thái, ngày
│   └── D-xxx-<tên>/
│       ├── brief.md               # câu hỏi, bối cảnh, phương án trung lập
│       ├── votes/
│       │   ├── r1-<góc-nhìn>-<model>.md
│       │   ├── r1-summary.md      # tóm tắt ẩn danh (khi cần vòng 2)
│       │   └── r2-<góc-nhìn>-<model>.md
│       ├── tally.md               # do script tạo
│       └── decision.md            # đề xuất, tỉ lệ, thiểu số, rủi ro,
│                                  #   quyết định của bạn, trạng thái
│
├── risks/
│   └── acceptance.md              # rủi ro ≥ 15 điểm bạn đã chấp nhận
│
├── drafts/                        # bản nháp, cùng cấu trúc architecture/
│
├── reviews/R-xxx-<phần>.md        # lỗi chặn / góp ý, link file và dòng
│
├── checks/
│   ├── links-<ngày>.md
│   ├── trace-<ngày>.md
│   ├── numbers-<ngày>.md
│   └── workspace-<ngày>.md
│
└── archive/vN/                    # chụp state, plan, stack, capacity,
                                   #   decisions, reviews khi phát hành vN
```

Thư mục `archive/` giữ phần "vì sao" cho chế độ nâng cấp sau này, trong khi đầu ra vẫn sạch.

## Các script kiểm tra

Việc gì máy kiểm được thì giao cho script Python chạy qua uv, không để agent tự đọc rồi tự khen; Reviewer chạy lại các script này trước khi viết báo cáo.

| Script | Làm gì | Chặn gate khi |
| --- | --- | --- |
| `init_workspace.py` | Tạo `.agent-workspace/`, thêm vào `.gitignore`, chép template, tạo file hướng dẫn CLI | — |
| `detect_models.py [--probe NAME,NAME] [--web-models ...]` | Dò model Claude và CLI ngoài gọi được, ghi `models.md` (mỗi dòng ghi loại: subagent Claude hay qua CLI ngoài). Mọi model ở trạng thái "chưa thử" (chưa dùng được) cho tới khi `--probe <danh sách>` thử gọi đúng các model đó; `--probe` không kèm danh sách là lỗi; cảnh báo nếu `CLAUDE_CODE_SUBAGENT_MODEL` hoặc `…_FORCE` đang đặt | Không có model nào gọi được sau khi thử |
| `call_council_cli.py --decision D-xxx-<tên> --round 1\|2 --perspective <góc-nhìn> --model <tên trong models.md> [--mode auto\|stdin\|argv]` | Gọi một thành viên hội đồng qua CLI ngoài (không tương tác): đưa phần thân file góc nhìn (cắt tại `<!-- body-end -->`) + `brief.md` (vòng 2 thêm `r1-summary.md`) qua **stdin** (mặc định; cách đưa theo từng CLI ở `core/data/cli.yaml`, agy: `--input-format stream-json`), dòng `cli` trong `models.md` làm cách dự phòng (prompt qua đối số, quá giới hạn dòng lệnh thì báo lỗi, không cắt); chỉ model `cli` ở trạng thái "gọi được"; luôn chạy bằng **agent khóa công cụ** (không công cụ, không MCP; khai ở `core/data/cli.yaml`) trong thư mục tạm rỗng, kiểm khóa bằng mã xác nhận trước khi đưa brief, bước công cụ trong câu trả lời làm phiếu vô hiệu; ghi phiếu nguyên văn vào `votes/r<vòng>-<góc-nhìn>-<member>.md` (không ghi đè nếu không có `--overwrite`) | Phiếu sai định dạng (do `tally_votes.py` bắt) |
| `guard_write.py` (hook `PreToolUse` của plugin, matcher `Write\|Edit\|Bash\|PowerShell`) | Đọc `agent_type` và đường dẫn từ dữ liệu hook, chặn (exit 2) khi agent ghi ngoài vùng của mình theo `permissions.md`. Với shell (agent chỉ có Bash; PowerShell vẫn nằm trong matcher và có cùng luật làm lớp dự phòng): Reviewer chỉ được `uv run` các script kiểm tra của design-core (`calc_capacity.py` chỉ kèm `--check`, không ghi bản nháp) và lệnh chỉ đọc; Orchestrator chỉ được `uv run` script của design-core (kể cả `promote_drafts.py`, `archive_release.py`, `tally_votes.py`), lấy ngày, lệnh chỉ đọc, và chép file vào `.agent-workspace/inputs/`; mọi lệnh khác bị chặn; Planner, Researcher, Designer, hội đồng không có shell. Thêm: Orchestrator chỉ sửa dòng "Trạng thái" của file task và khối `BEGIN:user` của `decision.md`; Designer không sửa khối `BEGIN:calc` của `tables.md` và `drafts/03-capacity/`, `assumptions.md`; Reviewer chỉ tạo file mới trong `reviews/` | Chặn từng lần ghi; không phải kiểm gate |
| `calc_capacity.py [--check] [--assumptions-only] [--constants-dir DIR]` | Đọc `capacity/*.yaml` và `capacity/db-constants/`, sinh `drafts/03-capacity/*`, `drafts/00-context/assumptions.md` và bảng số trong `tables.md` chỉ giữa `<!-- BEGIN:calc:<bảng> -->` và `<!-- END:calc:<bảng> -->`; `--check` chỉ tính lại và so sánh (Reviewer chạy); `--assumptions-only` chỉ sinh `assumptions.md` (G1); mốc tính theo mức dự án (S: ra mắt, 1 năm; M: thêm 3 năm; L: thêm 5 năm; XL: thêm đỉnh tải); kiểu khóa tăng dần không đủ cho mốc xa nhất cũng là lỗi; `storage.yaml` tùy chọn: không có file hoặc `buckets: {}` nghĩa là không có object storage (`storage-sizing.md` ghi rõ, chi phí object storage và băng thông ra bằng 0) | YAML thiếu nguồn cho hằng số hoặc giá |
| `tally_votes.py` | Đếm phiếu từng vòng, ghi `tally.md`, xác định quá bán; sinh `votes/r1-summary.md` ẩn danh khi cần vòng 2 | Thiếu phiếu, phiếu sai định dạng |
| `run_spike.py --spike S-xx [--show]` | Chạy spike S-xx trong container (Docker, hoặc Podman) theo đề bài Designer viết (`image`, `commands`, `expect`) và ghi `S-xx-<tên>.result.md` (`đạt` / `không đạt` / `lỗi`, kèm sha256 của đề bài). Chỉ chạy khi `state.md` (mục "Spike được duyệt chạy") có dòng người dùng đồng ý đúng `S-xx: chạy` kèm sha256 của đề bài hiện tại; `--show` in điều sẽ chạy và hash cần ghi. Container không gắn thư mục máy, không đặc quyền, mặc định không mạng, có giới hạn bộ nhớ, CPU, tiến trình, thời gian; image phải ghim tag; giới hạn ở `core/data/spike.yaml` | Mức XL: lớp bắt buộc không có spike `đạt` (do `check_workspace.py` kiểm) |
| `check_links.py` | Link gãy (file và `#mục`), ID trùng (ID được định nghĩa bởi heading; ô đầu dòng bảng chỉ định nghĩa khi không có heading nào, nên bảng chỉ mục ở file overview không trùng với file chi tiết), thiếu liên kết ngược (file có ID `SVC`/`TBL`/`BKT`/`EVT`/`API` phải có mục "Được dùng bởi" link tới mọi file nhắc ID đó; không áp cho `FR`/`NFR`/`C`/`A`/`TC`/`R`); `C-xx` chỉ được định nghĩa ở `00-context/constraints.md`, `A-xx` chỉ ở `00-context/assumptions.md` (định nghĩa ở file khác là lỗi chặn), mỗi lớp stack truy về `TC` đã định nghĩa (Q5), mỗi `R-xx` có trong cột "Thành phần liên quan" ID `SVC`/`TBL`/`BKT`/`EVT`/`API` hoặc link tới file trong `02-tech-stack/` (Q6; tên công nghệ trần không link là lỗi; luật này chỉ áp khi `02-tech-stack/layers/` có ít nhất một file `.md`, tức từ G4; trước đó sổ rủi ro chỉ cần có cột "Thành phần liên quan"); cảnh báo ID mồ côi (định nghĩa mà không file nào khác nhắc) | Có lỗi chặn (ID mồ côi chỉ cảnh báo, không chặn) |
| `check_trace.py --gate Gn [--root DIR] [--config FILE]` | Truy vết giữa các phần của bản nháp. **Từ G6:** FR không có luồng (mỗi FR được định nghĩa trong bản nháp phải được ít nhất một file đơn luồng `04-flows/FL-*.md` nhắc tới; `flow-index.md` không tính). **Từ G7:** `API-xx` mà frontend gọi (nhắc trong `05-frontend/`) nhưng `06-backend/` không định nghĩa (không có thư mục `05-frontend/` thì bỏ kiểm API); `TBL-`, `BKT-`, `EVT-` mà luồng nhắc nhưng `07-data/` không định nghĩa (ở G6 luồng được duyệt trước khi backend và data thiết kế nên chưa kiểm). **ID được nhắc mà chưa định nghĩa ở đâu** (việc dồn từ `check_links.py`; SVC, API, EVT, TBL, BKT chỉ từ G7; ngoài bản nháp thì `decisions/decision-log.md` định nghĩa D, `questions.md` định nghĩa CH, `inputs/ui-design/` định nghĩa SCR). Mỗi ID một lỗi (lỗi cụ thể hơn thay lỗi chưa định nghĩa); tên giữ chỗ như `FR-xx` không phải ID; nhắc trong khối mã tính (sơ đồ tuần tự), đích link và tên file không tính. Đường dẫn, tiền tố và gate nằm ở `core/data/trace.yaml`, tiền tố ID ở `core/data/ids.yaml` | Có lỗi bất kỳ |
| `check_numbers.py [--config FILE]` | Mọi số có đơn vị ("292 MB", "300 ms", "70%") phải có trong cùng câu (đoạn văn), mục (danh sách, heading) hoặc dòng bảng một công thức, một giả định `A-xx` đã khai trong `assumptions.yaml`, hoặc một nguồn (link, URL, `inputs/`); một ID `NFR-xx` hoặc `C-xx` đã được định nghĩa trong bản nháp cũng là bằng chứng (chỗ định nghĩa của chúng có cột nguồn); dòng bảng cũng đạt khi cột "Nguồn" / "Giả định" / "Công thức" của dòng đó đã điền, hoặc cột "Cơ sở" / "Cơ sở ước tính" có link hay ID (NFR, C, A, D, R, TC; chữ thuần như "kinh nghiệm team" không đạt); số trong file do `calc_capacity.py` sinh và trong khối `BEGIN:calc`/`END:calc` chỉ được miễn khi **chứng minh được**: file nằm đúng một trong sáu đường dẫn script sinh và nội dung khớp bản `calc_capacity.py` tính lại từ `capacity/*.yaml` (khối thì đúng file `tables.md` của database và đúng nội dung tính lại, hoặc chỉ có chữ "chờ script"); dòng "Sinh bởi calc_capacity.py" tự nó không miễn gì, file sinh bị sửa tay bị báo và kiểm như file thường. Từ mơ hồ ("nhanh", "lớn", "đủ dùng", "scale tốt"...) không kèm số trong cùng câu / mục / dòng bảng là lỗi (cụm chính xác như "ít nhất", "nhỏ nhất", "lớn nhất", "nhiều nhất" không tính). `assumptions.md` lệch `assumptions.yaml` (sinh lại từ yaml rồi so) là lỗi. Danh sách từ mơ hồ, đơn vị, tên cột bằng chứng nằm ở `core/data/numbers.yaml`, không viết cứng trong script (độ nhạy đã chỉnh ở Giai đoạn 4 trên bản nháp mẫu: cụm miễn, ID làm bằng chứng, cột cơ sở) | Có lỗi bất kỳ |
| `check_profile.py --gate Gn (--templates DIR \| --no-templates)` | `project-profile.md` hợp lệ (dòng `Mức:`, bảng `\| Phần \| Áp dụng \|` đủ 13 phần, giá trị có / rút gọn / bỏ; dòng cấp file được phép, dòng dài nhất thắng); phần đã bỏ lại xuất hiện; phần gate đã tới mà còn thiếu (file hoặc phần, file theo template; mỗi thư mục đối tượng đang có, như `services/<service>/`, `databases/<db>/`, `<app>/`, phải có đủ file mà template có placeholder tương ứng định nghĩa); và, gộp ở đây, **mục bắt buộc theo template**: mỗi file đầu ra có đủ, không để trống, không còn nguyên nội dung mẫu ở các mục template đánh dấu `<!-- required -->` (ngay sau heading hoặc cuối dòng heading), ví dụ "Tối ưu" (Q2), scale / nâng cấp / bảo trì (Q3) | Có lỗi bất kỳ; không tìm thấy template mà không truyền `--no-templates` cũng là lỗi (`--no-templates` ghi "Chưa kiểm mục bắt buộc" ở đầu báo cáo) |
| Kiểm mục bắt buộc theo template | Gộp vào `check_profile.py` (xem hàng trên) | Thiếu mục bắt buộc |
| `check_versions.py [--config FILE]` | Mọi công nghệ trong bảng của `02-tech-stack/README.md` (một công nghệ mỗi dòng, cột "Công nghệ") có dòng cùng tên trong `versions-features.md` (tên là phần trước vai trò: "PostgreSQL — database cho order-db"); phiên bản hai file trùng nhau; phiên bản major.minor ở mọi lớp, riêng lớp third-party (cột "Lớp" của README) được thêm YYYY-MM-DD hoặc "SaaS, không phiên bản" (cần link changelog hoặc chính sách ngừng hỗ trợ, không cần ngày EOL); ô "Ngày phát hành, ngày hết hỗ trợ" có ngày hết hỗ trợ sau ngày phát hành (hoặc "chưa công bố") và link http/https (Q5). Vòng đời: đã hết hỗ trợ tại ngày chạy là lỗi chặn; hết hỗ trợ trong 12 tháng là cảnh báo và cột Rủi ro của dòng đó phải có link `R-xx`, thiếu thì lỗi chặn (Q5, Q6); dòng trùng (cùng công nghệ và phiên bản) là lỗi chặn; dòng ma trận mà README không liệt kê chỉ là cảnh báo. Tên cột, nhãn ngày hết hỗ trợ, phiên bản trôi nổi, lớp third-party, ngưỡng 12 tháng nằm ở `core/data/versions.yaml` | Thiếu dòng, lệch hoặc không chốt phiên bản, thiếu ngày EOL hoặc link nguồn, đã hết hỗ trợ, sắp hết hỗ trợ mà thiếu link rủi ro, dòng trùng |
| `check_workspace.py [--gate Gn]` | Trạng thái workspace ở gate Gn (mặc định: "Giai đoạn hiện tại" của `state.md`). **Task** có Gate ≤ Gn chưa `đóng`. **Quyết định** có gate ≤ Gn chưa có quyết định của bạn: phải `đã quyết` với nguyên văn `D-xxx: chọn <phương án>` và ngày, khớp khối `user` của `decision.md` (`làm lại` vẫn là chưa quyết; thư mục `D-*` thiếu trong nhật ký là lỗi). **Rủi ro ≥ 15 điểm** chưa `đã chấp nhận` hay `đã đóng`: cảnh báo trước G9, lỗi chặn từ G9. **Kiểm hai chiều** sổ rủi ro ↔ `risks/acceptance.md`: rủi ro ≥ 15 điểm ghi `đã chấp nhận` phải có dòng ở acceptance.md, mỗi dòng ở đó phải có rủi ro cùng điểm, trạng thái `đã chấp nhận`, nguyên văn `R-xx: chấp nhận` và ngày. **Model** trong bảng "Gán model" của `models.md` mà danh mục ghi "chưa thử" hoặc "không dùng được": chỉ kiểm dòng gán của task chưa đóng (bảng là nhật ký, dòng của task đã đóng giữ làm lịch sử); model không có trong danh mục chỉ cảnh báo. **Spike** (mức XL, từ G4): mỗi lớp bắt buộc (`data`, `messaging`, `backend`, `infrastructure`, cộng lớp Planner đánh dấu ở mục "Lớp cần spike" của `plan/plan.md`; `tooling`, `third-party` không) có thư mục trong `stack/layers/` phải có ít nhất một spike `đạt` trên đề bài hiện tại. Từ ngữ và ngưỡng ở `core/data/workspace.yaml` | Có lỗi bất kỳ |
| `promote_drafts.py --gate Gn [--architecture DIR] [--dry-run]` | Chép bản nháp của gate Gn sang `architecture/` (điều kiện ở đoạn "Báo cáo có hash" dưới bảng) | Gate chưa được bạn duyệt đúng quy tắc 2; báo cáo của một script thiếu, có lỗi, sai gate hoặc cũ (hash lệch) |
| `archive_release.py [--version N] [--architecture DIR] [--dry-run]` | Chụp `state.md`, `plan/`, `stack/`, `capacity/`, `decisions/`, `reviews/`, `risks/`, `models.md` vào `archive/vN/` (dựng ở thư mục tạm, đọc lại từng file, rồi mới đổi tên) và thêm mục vN lên ĐẦU `architecture/CHANGELOG.md`: mức, quyết định đã chốt, rủi ro đã chấp nhận, và ở chế độ nâng cấp là file thêm/đổi/xóa so với `inputs/previous-design/` (sha256, chuẩn hóa CRLF). vN tự tăng từ `archive/vN` cao nhất (hoặc `--version`). Dữ liệu ở `core/data/archive.yaml`; dùng `approvals.py` | G0 đến G10 chưa được bạn duyệt đúng quy tắc 2; chưa có `architecture/`; không có báo cáo `checks/promote-<ngày>.md` ghi một lần chép G10 thành công (báo cáo mới nhất theo ngày trong tên), hoặc `architecture/` (trừ `CHANGELOG.md`) lệch hash các file lần chép đó ghi (file sửa tay, bị xóa, hoặc thừa; nêu rõ từng file); `archive/vN` hoặc mục vN của changelog đã có (không ghi đè); liên kết tượng trưng ở nơi nó đọc |

**Báo cáo có hash và `promote_drafts.py`.** Mọi script phán xét workspace (`calc_capacity.py`, `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py`, `check_trace.py`, `check_workspace.py`, `tally_votes.py`) kết thúc báo cáo trong `checks/` bằng một khối "Đã kiểm" (`core/scripts/checkreport.py`): tên script, kết quả (`sạch` / `có lỗi`), gate và chế độ nếu có, và danh sách file đã kiểm kèm sha256 nội dung (CRLF chuẩn hóa thành LF; hash lấy trước khi chạy, riêng file do chính `calc_capacity.py` và `tally_votes.py` ghi thì lấy sau khi ghi). `promote_drafts.py --gate Gn [--architecture DIR] [--dry-run]` chỉ chép khi: (1) `state.md` ghi gate đã duyệt đúng quy tắc 2 (trạng thái `đã duyệt`, nguyên văn `Gn: duyệt`, có ngày) và mọi gate trước đó cũng vậy (`core/scripts/approvals.py`); (2) báo cáo mới nhất (theo ngày trong tên file, không theo mtime) của mọi script của gate, theo `core/data/gates.yaml` (khớp dòng "Script" của `stages.md`, có test), đều sạch, đúng gate, đúng chế độ (`check_profile.py --no-templates` không đủ; `calc_capacity.py --assumptions-only` đủ cho G1, không đủ từ G5) và không cũ: hash mọi file báo cáo liệt kê phải bằng hash hiện tại, và không có file mới trong phạm vi của script (`scope` trong `gates.yaml`) từ lúc kiểm. Thiếu điều kiện nào thì từ chối và nêu rõ thiếu gì. Chép đúng các mục `GATE_ENTRIES` của `check_profile.py` (một phần chép nguyên, một file chép riêng; mục hồ sơ đã bỏ thì không có gì để chép); G10 chép lại mọi phần cùng `drafts/README.md`, phần nào đã đổi sau gate của nó thì được cập nhật và nêu rõ. Không bao giờ xóa file ở `architecture/` (file chỉ còn ở đó thì báo cảnh báo). `architecture/` mặc định cạnh workspace. Mỗi lần chạy ghi nối vào `checks/promote-<ngày>.md`; lần chạy có chép kết thúc bằng khối `BEGIN:promoted` ghi sha256 từng file `architecture/` giữ cho gate đó (đường dẫn tương đối `architecture/`), để `archive_release.py` so với `architecture/` trước khi phát hành.

**Danh sách tiền tố ID dùng chung.** `core/data/ids.yaml` là nguồn duy nhất: `FR`, `NFR`, `C` (ràng buộc), `A` (giả định), `TC`, `FL`, `SCR`, `SVC`, `API`, `EVT`, `TBL`, `BKT`, `R`, `D`, `CH`, cùng nhóm cần liên kết ngược và file định nghĩa của `C`, `A`. `check_links.py`, `check_numbers.py`, `tally_votes.py` và `check_trace.py` đọc danh sách này qua `scripts/idlist.py`, không script nào lặp lại; `test_idlist.py` giữ các script và tài liệu khớp với nó.

**Trạng thái dựng (Giai đoạn 6 xong, đã gộp vào `develop`).** Phần script dưới đây dựng ở Giai đoạn 3 (3A và 3B); các giai đoạn sau thêm template, bộ mẫu, USAGE và bản Antigravity. Script đã làm, có test và đã thử phá: `init_workspace.py`, `detect_models.py`, `guard_write.py` (và `hooks/hooks.json`), `calc_capacity.py` (kèm schema [capacity-schema.md](core/workflow/capacity-schema.md)), `check_links.py`, `check_profile.py` (gộp kiểm mục bắt buộc theo template), `check_numbers.py`, `check_versions.py`, `tally_votes.py` (dữ liệu hội đồng ở `core/data/council.yaml`), `call_council_cli.py` (cách gọi từng CLI ở `core/data/cli.yaml`), `run_spike.py` (giới hạn ở `core/data/spike.yaml`), `check_trace.py` (đường dẫn và gate ở `core/data/trace.yaml`), `check_workspace.py` (từ ngữ và ngưỡng ở `core/data/workspace.yaml`), `promote_drafts.py` (dữ liệu ở `core/data/gates.yaml`; dùng chung `checkreport.py` và `approvals.py`, không phải script chạy riêng), `archive_release.py` (dữ liệu ở `core/data/archive.yaml`). Dữ liệu cấu hình của các script nằm ở `core/data/` (`numbers.yaml`, `versions.yaml`, `council.yaml`, `ids.yaml`, `cli.yaml`, `spike.yaml`, `trace.yaml`, `workspace.yaml`, `gates.yaml`, `archive.yaml`); module dùng chung, không phải script chạy riêng: `idlist.py`, `checkreport.py`, `approvals.py`. Quy ước chung: chạy `uv run <script>.py [--workspace DIR]`; lỗi chặn trả mã 1, in báo cáo ngắn và ghi `checks/<tên>-<ngày>.md`; dùng sai tham số trả mã 2.

## Vị trí trong repo Thanh-Tan-

Workflow, agent, hội đồng và script nằm ở core của family Design để các plugin Design khác (UI sau này) dùng lại; plugin `design-architecture` chỉ chứa template, checklist và phần "dùng với core".

```
families/design-system/
├── README.md
├── PLAN.md                        # tài liệu này
├── core/
│   ├── USAGE.md                   # template prompt chính của family
│   ├── workflow/
│   │   ├── stages.md              # giai đoạn, gate, điều kiện qua gate
│   │   ├── permissions.md         # agent nào được ghi vào đâu
│   │   └── quality-criteria.md    # 8 tiêu chí Q1–Q8
│   ├── claude/agents/             # định dạng Claude Code (viết tay, manifest liệt kê rõ)
│   │   ├── orchestrator.md
│   │   ├── planner.md
│   │   ├── researcher.md
│   │   ├── designer.md
│   │   ├── reviewer.md
│   │   └── council/               # một file mỗi góc nhìn
│   ├── agents/                    # bản Antigravity: tạo ở Giai đoạn 6, trước đó để trống
│   ├── templates/workspace/       # task, brief, phiếu bầu, decision, review
│   └── scripts/                   # các script ở phần trên, môi trường uv
│
└── design-architecture/
    ├── README.md                  # phần "dùng với core": dữ liệu cần thêm, ví dụ done-when
    ├── templates/                 # form cố định cho từng file trong architecture/
    ├── checklists/                # "xong khi" cho từng phần 00–12
    └── profiles.md                # bảng mức S/M/L/XL và phần áp dụng
```

Kiến thức riêng của từng stack (cấu trúc thư mục NestJS, hằng số byte của từng DB) không nằm trong plugin mà ở `~/knowledge/stacks/<stack>/`, được chép vào dự án lúc khởi tạo.

## Prompt mẫu

Bốn prompt dưới đây là nội dung chính của `core/USAGE.md`. Tài liệu BA đưa thẳng trong prompt; Orchestrator lưu vào `inputs/ba/` để các agent sau đọc từ một chỗ cố định. Với Antigravity CLI, prompt giữ nguyên, chỉ đổi dòng "Chạy với".

**1. Thiết kế mới**

```text
Chạy với: Claude Code · model Sonnet · effort high

Dùng plugin design-architecture, chế độ THIẾT KẾ MỚI.

Dự án: <tên> — <1–2 câu mô tả>
Repo thiết kế: <đường dẫn>
Stack bắt buộc (nếu có): <ví dụ: backend phải là NestJS> | không có
Ràng buộc đã biết: ngân sách <…>/tháng · team <n> người (<kỹ năng>) · hạn <ngày> · hạ tầng <…> · tuân thủ <…>
Thiết bị người dùng chính (nếu biết): <…>
Tài liệu UI của designer (nếu có): <đường dẫn danh sách SCR>

Tài liệu BA đã duyệt:
<dán nội dung, hoặc liệt kê đường dẫn từng file>

Yêu cầu:
- Lưu tài liệu BA vào .agent-workspace/inputs/ba/ và chỉ đọc từ đó.
- Dò các model gọi được, ghi .agent-workspace/models.md.
- Làm hết G0 rồi dừng: trình hồ sơ dự án, mức áp dụng và danh mục model để tôi duyệt.
- Chỗ nào chưa rõ thì ghi vào questions.md và hỏi tôi, không tự giả định.
```

**2. Nâng cấp từ thiết kế cũ**

```text
Chạy với: Claude Code · model Sonnet · effort high

Dùng plugin design-architecture, chế độ NÂNG CẤP.

Repo thiết kế: <đường dẫn> · phiên bản hiện có: v<N>
Bản thiết kế cũ: <đường dẫn architecture/ cũ>
Lý do nâng cấp: <…>
Giữ nguyên, không xét lại: <…> | không có

Tài liệu BA mới hoặc phần thay đổi:
<dán nội dung, hoặc liệt kê đường dẫn>

Yêu cầu:
- Đọc bản cũ và archive/ (nếu còn) trước khi đề xuất gì.
- Liệt kê phần giữ, phần đổi, phần thêm.
- Dừng ở G0 để tôi duyệt phạm vi nâng cấp.
```

**3. Tiếp tục ở session mới**

```text
Chạy với: Claude Code · model Sonnet · effort medium

Tiếp tục design-architecture ở repo này.
(Tuỳ chọn) Tôi đã trả lời trong questions.md các mục: CH-003, CH-005.
```

**4. Duyệt gate và quyết định**

```text
Chạy với: Claude Code · model Sonnet · effort medium

Gate G4: duyệt.            (hoặc: chưa duyệt — lý do: …)
D-007: chọn phương án B. Ghi chú: …
R-04: chấp nhận rủi ro.
CH-006: <câu trả lời>
```

Mẹo dùng hiệu quả:

- Mỗi session làm trọn một giai đoạn, kết thúc ở gate.
- Trả lời theo ID (`G`, `D`, `R`, `CH`) để Orchestrator ghi đúng chỗ.
- Tài liệu BA càng có số (người dùng, tăng trưởng, ngưỡng hiệu năng) thì G1 càng ít câu hỏi.

## Thứ tự dựng plugin

Dựng từ khung và cơ chế kiểm soát trước, template nội dung sau, để mỗi bước dựng xong là dùng thử được ngay.

1. Khung `families/design-system/` và `init_workspace.py`.
2. Workflow: `stages.md`, `permissions.md`, `quality-criteria.md`, template task có checklist.
3. Agent Planner, Designer, Reviewer cùng `check_links.py` và `check_profile.py`.
4. Agent Researcher và template vùng `stack/`.
5. Capacity: schema các file YAML, `calc_capacity.py`, `check_numbers.py`.
6. Hội đồng: các file góc nhìn, template phiếu bầu, `tally_votes.py`.
7. Template và checklist đầu ra, làm nhóm cốt lõi trước: context, tech-stack, capacity, flow, service, database; các phần còn lại sau.
8. `check_trace.py`, `check_workspace.py`, `promote_drafts.py`, `archive_release.py`.
9. Chạy thử toàn bộ trên một dự án thật, cùng đợt chạy thử app full-stack đã lên kế hoạch.

## Các điểm đã chốt

- [x] Bảng mức S/M/L/XL: giữ như đề xuất.
- [x] File hướng dẫn cho CLI (ví dụ `CLAUDE.md`) do `init_workspace.py` tạo và đưa vào `.gitignore`.
- [x] Model: agent tự dò, ghi `models.md` và gán khi gọi.
- [x] Tài liệu BA: đưa trong prompt, Orchestrator lưu vào `inputs/ba/`.
