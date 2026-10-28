# Giai đoạn và gate

Quy trình có 11 gate (G0–G10) theo thứ tự cố định. Một gate chỉ qua khi đủ điều kiện **và người dùng duyệt**; không agent nào được ghi trạng thái "Đã duyệt" (xem [permissions.md](permissions.md)). Tiêu chí chất lượng Q1–Q8 là checklist của Reviewer (xem [quality-criteria.md](quality-criteria.md)). Nguồn: [PLAN.md](../../PLAN.md).

Đường dẫn dạng `NN-<phần>/...` là tương đối với `architecture/`. Trước khi gate được duyệt, file nằm ở `.agent-workspace/drafts/NN-<phần>/...` (bản nháp); sau khi người dùng duyệt, chỉ `promote_drafts.py` chép sang `architecture/NN-<phần>/...` (riêng `CHANGELOG.md` do `archive_release.py` thêm mục ở G10). Đường dẫn bắt đầu bằng `.agent-workspace/` là file làm việc, không bao giờ vào `architecture/`.

## Vòng làm việc trong mỗi giai đoạn

1. Planner lập task và checklist "xong khi" (`plan/tasks/T-xxx-<tên>.md`).
2. Gom câu hỏi vào `questions.md`; người dùng trả lời.
3. Quyết định lớn: Designer viết `brief.md`, hội đồng bỏ phiếu, `tally_votes.py` đếm, người dùng quyết.
4. Designer viết bản nháp theo template; `calc_capacity.py` tính số khi có số liệu.
5. Reviewer soát theo Q1–Q8 và checklist, chạy lại các script kiểm tra; không sửa.
6. Gate: kiểm các điều kiện chung bên dưới, người dùng duyệt, `promote_drafts.py` chép bản nháp sang `architecture/`.

Kết thúc mỗi task và mỗi gate, Orchestrator cập nhật `state.md`.

## Điều kiện chung của mọi gate

- Mọi task của giai đoạn đã đóng.
- Không còn quyết định chờ, không còn lỗi chặn trong `reviews/`.
- Các script kiểm tra áp cho gate (dòng "Script" của từng gate) chạy sạch, kết quả ở `checks/`; `check_workspace.py` chạy ở mọi gate.
- Reviewer soát đủ Q1–Q8 ở mọi gate. Các Q ghi theo từng gate bên dưới chỉ là trọng tâm. Q6 và Q8 là trọng tâm ở mọi gate: rủi ro được khai ngay khi phát sinh, độ sâu tài liệu khớp hồ sơ dự án.
- Phần bị bỏ theo mức áp dụng (ghi ở `00-context/project-profile.md`) không phải làm và không được xuất hiện; `check_profile.py` kiểm.
- Người dùng duyệt rõ ràng; quyết định nói trong chat được ghi vào `decision.md` trước khi làm tiếp.

Chế độ nâng cấp: G0 đọc `inputs/previous-design/` trước, và mỗi gate chỉ làm lại phần có thay đổi.

## Quy tắc script và hội đồng

- `check_links.py`, `check_numbers.py`, `check_profile.py`: từ G1 trở đi (đến G1 đã có NFR và giả định phải có số). `check_profile.py` chạy với `--gate Gn` (n là gate đang soát) và với `--templates <thư mục template của plugin design-*>`; không truyền cả hai thì script lỗi, và `--no-templates` ghi "Chưa kiểm mục bắt buộc" ở đầu báo cáo nên không được coi là đạt gate.
- `check_versions.py`: từ G4 trở đi. Ma trận phiên bản có từ G4, nhưng ngày hết hỗ trợ trôi theo ngày chạy nên chạy lại ở mọi gate sau: phiên bản đã hết hỗ trợ là lỗi chặn, sắp hết hỗ trợ (12 tháng) phải link `R-xx` ở cột Rủi ro.
- `check_trace.py --gate Gn`: từ G6 trở đi, truyền `--gate` của gate đang soát. Từ G6 kiểm mỗi FR có ít nhất một file đơn luồng `04-flows/FL-*.md` nhắc tới; từ G7 (khi backend và data đã thiết kế, G6 luồng được duyệt trước nên chưa kiểm) kiểm API `API-xx` frontend gọi có ở `06-backend/` và `TBL-`/`BKT-`/`EVT-` luồng nhắc có ở `07-data/`; ID được nhắc mà chưa định nghĩa ở đâu là lỗi (SVC, API, EVT, TBL, BKT chỉ từ G7). Chi tiết: `core/data/trace.yaml`.
- `calc_capacity.py`: ở G1 với `--assumptions-only` (sinh `00-context/assumptions.md`), ở G5, G7 và G10 đầy đủ. Orchestrator chạy; Reviewer chỉ chạy `--check` (so sánh, không ghi).
- `detect_models.py`: ở G0, lập danh mục model; `--probe <danh sách>` chỉ thử đúng các model đã chọn trước, một lần. `guard_write.py` là hook `PreToolUse` luôn chạy, không phải bước của gate.
- `run_spike.py`: ở G4 khi có spike (XL bắt buộc), chỉ Orchestrator chạy, chỉ khi `state.md` có dòng người dùng đồng ý đúng `S-xx: chạy` kèm sha256 của đề bài hiện tại; kết quả `.result.md` chỉ do script ghi.
- `call_council_cli.py`: ở mọi gate có hội đồng, cho từng thành viên chạy qua CLI ngoài (thành viên là subagent Claude thì Orchestrator gọi bằng Agent tool, không qua script); chỉ gọi model đã `--probe` đạt (`models.md` ghi "gọi được").
- `tally_votes.py`: ở mọi gate có hội đồng; `--gate Gn` đếm các quyết định của gate đó (ở G10 chạy không có `--gate`, đếm tất cả); báo cáo `checks/tally-<ngày>.md` ghi gate để `promote_drafts.py` kiểm.
- `promote_drafts.py --gate Gn`: chạy sau khi người dùng duyệt gate (`Gn: duyệt`, quy tắc 2). Chỉ chép khi mọi script của gate (danh sách trong `core/data/gates.yaml`, bằng dòng "Script" của gate trừ các script không để lại báo cáo) có báo cáo mới nhất sạch, đúng gate và không cũ (mỗi báo cáo ghi sha256 của các file đã kiểm; file đổi hoặc thêm sau lúc kiểm thì báo cáo cũ và phải chạy lại script). Thiếu gì thì từ chối và nêu rõ. G10 chép lại mọi phần cùng `README.md`.
- `check_workspace.py --gate Gn`: ở mọi gate (không truyền `--gate` thì lấy "Giai đoạn hiện tại" của `state.md`). Kiểm: task có Gate ≤ Gn chưa đóng; quyết định có gate ≤ Gn chưa có quyết định của người dùng; rủi ro ≥ 15 điểm chưa xử lý (cảnh báo trước G9, lỗi từ G9); sổ rủi ro và `risks/acceptance.md` khớp hai chiều; model chưa thử hoặc không dùng được ở các dòng "Gán model" của task chưa đóng (dòng của task đã đóng là lịch sử); ở mức XL từ G4, mỗi lớp bắt buộc có spike `đạt`. Từ ngữ và ngưỡng: `core/data/workspace.yaml`. G10 chạy toàn bộ script.
- **Hội đồng** chỉ dùng cho: kiểu kiến trúc (G3); stack từng lớp, phiên bản chốt, loại database (G4); ranh giới service, chiến lược nhất quán dữ liệu, kiểu dữ liệu của các bảng tăng nhanh nhất, đặc biệt khóa chính và khóa ngoại (G7). Chi tiết nhỏ hơn do Designer viết thẳng, Reviewer soát.
- **Số thành viên theo mức:** S 3 phiếu, chỉ cho kiểu kiến trúc (G3) và stack từng lớp (G4); M 3; L 3, và 5 cho quyết định khó đảo ngược (xem mục bên dưới); XL 5.

## Phần của `architecture/` theo mức áp dụng

Mức đã duyệt ở G0 quyết định phần nào bắt buộc (bảng "Hồ sơ dự án" trong PLAN); `project-profile.md` ghi phần áp dụng và phần bỏ.

| Phần | S | M | L | XL |
| --- | --- | --- | --- | --- |
| 00-context, 02-tech-stack, 04-flows, 06-backend, 07-data | có | có | có | có |
| 03-capacity | rút gọn | có | có | có |
| 01-system | tối thiểu: `architecture-style.md`, `containers.md`; thêm `integrations.md` khi có hệ thống ngoài (thanh toán, mail, SMS…) | có | có | có |
| 11-risks | rút gọn: chỉ rủi ro ≥ 8 điểm | có | có | có |
| 12-roadmap | chỉ `implementation-plan.md` | thêm `scaling-stages.md`, `upgrade-roadmap.md` | có | có |
| 05-frontend, 08-security, 09-infrastructure, 10-process | bỏ | có | có | có |

Mọi phần được giữ đều nằm trong `architecture/` và được commit; sổ rủi ro không được chỉ nằm trong workspace vì workspace không được commit. Mỗi gate dưới đây chỉ áp dụng cho các phần mà hồ sơ giữ lại.

## Giả định: một nguồn duy nhất

`.agent-workspace/capacity/assumptions.yaml` là nguồn duy nhất của giả định. `00-context/assumptions.md` được sinh từ yaml bằng script, không sửa tay; `check_numbers.py` báo lỗi nếu hai file lệch nhau. (`calc_capacity.py --assumptions-only` sinh; xem [capacity-schema.md](capacity-schema.md).)

## Quyết định khó đảo ngược (hội đồng 5 phiếu ở mức L)

Tiêu chí chung: đổi sau khi có dữ liệu production thì phải migrate dữ liệu hoặc tách/gộp service. Danh sách mặc định: kiểu kiến trúc, loại database, ranh giới service, chiến lược nhất quán dữ liệu, kiểu dữ liệu của các bảng tăng nhanh nhất, đặc biệt khóa chính và khóa ngoại. Planner được đề xuất thêm vào danh sách (ghi ở `plan/plan.md`); người dùng duyệt ở G0.

## Bảng tóm tắt

| Gate | Giai đoạn | Người dùng duyệt |
| --- | --- | --- |
| G0 | Khởi tạo và hồ sơ dự án | Mức áp dụng, các phần áp dụng, danh mục model |
| G1 | Context | FR, NFR có số, ràng buộc, giả định |
| G2 | Tiêu chí lựa chọn TC | Tiêu chí và trọng số, trước mọi ứng viên |
| G3 | Kiểu kiến trúc | Kiểu kiến trúc và giai đoạn scale (hội đồng) |
| G4 | Stack và phiên bản | Từng lớp, ma trận phiên bản, kiểm tra chéo |
| G5 | Capacity sơ bộ | Tải, dung lượng, chi phí theo từng mốc |
| G6 | Luồng chính | Luồng, trước khi thiết kế chi tiết |
| G7 | Thiết kế chi tiết | Từng service, database, app frontend |
| G8 | Bảo mật, hạ tầng, quy trình | Từng phần |
| G9 | Rủi ro và roadmap | Sổ rủi ro (mở từ G1, hoàn thiện ở đây); rủi ro từ 15 điểm đã được xử lý |
| G10 | Kiểm tra chéo và phát hành | Tính lại toàn bộ số, mọi script sạch, phát hành vN |

## G0. Khởi tạo và hồ sơ dự án

- **Đầu vào:** tài liệu BA trong prompt; chế độ nâng cấp thì thêm bản `architecture/` cũ.
- **Việc:** Orchestrator chạy `init_workspace.py`, lưu input vào `inputs/` (`ba/`, `ui-design/`, `previous-design/`), chạy `detect_models.py` để lập danh mục model, rồi sau khi có mức dự án đề xuất, chạy `detect_models.py --probe <các model đã chọn trước>` một lần (model chưa thử chưa được dùng). Planner lập hồ sơ dự án (quy mô người dùng và dữ liệu, mức độ quan trọng, số người, ngân sách, thời hạn, tuân thủ), đề xuất mức S/M/L/XL và danh sách phần áp dụng/bỏ; lập `plan/plan.md` và task đầu; đề xuất bổ sung (nếu có) vào danh sách quyết định khó đảo ngược.
- **Điều kiện qua gate:** người dùng duyệt mức, danh sách phần áp dụng và danh mục model (Q8). Đây là bước đầu tiên: chưa duyệt thì không làm gì khác.
- **File tạo ra:** `00-context/project-profile.md`; `.agent-workspace/state.md`, `models.md`, `inputs/*`, `plan/plan.md`, `plan/tasks/*`, `questions.md`.
- **Script:** `init_workspace.py`, `detect_models.py`, `check_workspace.py`, `promote_drafts.py` (sau khi bạn duyệt gate).

## G1. Context

- **Đầu vào:** `inputs/ba/`, hồ sơ dự án đã duyệt.
- **Việc:** Designer viết phần còn lại của `00-context` (đối chiếu BA, hỏi lại qua `questions.md` khi mơ hồ). Designer cũng mở sổ rủi ro `drafts/11-risks/risk-register.md` (chưa tính vào danh sách file của gate; `check_profile.py` chỉ đòi phần này từ G9) với các rủi ro sớm sinh ra từ NFR và ràng buộc (điểm, dấu hiệu sớm, giảm thiểu, dự phòng theo cột trong PLAN); cột "Thành phần liên quan" để trống đến khi có stack (script chưa đòi, xem `check_links.py`). Giả định ghi vào `capacity/assumptions.yaml`; `assumptions.md` do `calc_capacity.py --assumptions-only` sinh từ yaml (Orchestrator chạy), không sửa tay.
- **Điều kiện qua gate:** FR, NFR có chỉ số bằng số, ràng buộc (`C-xx`, định nghĩa ở `00-context/constraints.md`) và giả định (`A-xx`, ở `00-context/assumptions.md`) đều có ID; không có từ mơ hồ thiếu số (Q1, Q4); người dùng duyệt. Trọng tâm: Q1, Q4, Q6, Q8.
- **File tạo ra:** `00-context/requirements-trace.md`, `quality-attributes.md`, `constraints.md`, `assumptions.md` (sinh từ yaml), `glossary.md`; `.agent-workspace/capacity/assumptions.yaml` (nguồn duy nhất của giả định).
- **Script:** `calc_capacity.py --assumptions-only`, `check_links.py`, `check_numbers.py` (gồm kiểm yaml và `assumptions.md` không lệch), `check_profile.py`, `check_workspace.py`, `promote_drafts.py` (sau khi bạn duyệt gate).

## G2. Tiêu chí lựa chọn (TC)

- **Đầu vào:** context đã duyệt ở G1, hồ sơ dự án.
- **Việc:** Designer đề xuất tiêu chí TC-xx (ghi thẳng `drafts/02-tech-stack/selection-criteria.md`, không nêu tên công nghệ hay ứng viên nào) và trọng số cho stack và kiểu kiến trúc, mỗi TC truy về FR/NFR/ràng buộc; chấm theo hồ sơ dự án (làm quá tay bị trừ điểm). Phải xong **trước khi** có bất kỳ ứng viên nào.
- **Điều kiện qua gate:** người dùng duyệt tiêu chí và trọng số; chưa có ứng viên nào trong `.agent-workspace/stack/`. Trọng tâm: Q1, Q5, Q6, Q8.
- **File tạo ra:** `02-tech-stack/selection-criteria.md`; bản nháp trước duyệt: `.agent-workspace/drafts/02-tech-stack/selection-criteria.md` (nguồn duy nhất, không có bản nháp thứ hai trong `stack/`).
- **Script:** `check_links.py`, `check_numbers.py`, `check_profile.py`, `check_workspace.py`, `promote_drafts.py` (sau khi bạn duyệt gate).

## G3. Kiểu kiến trúc

- **Đầu vào:** context, TC đã duyệt.
- **Việc:** Designer viết `brief.md` với phương án trung lập (kiểu kiến trúc và giai đoạn scale); hội đồng bỏ phiếu độc lập (3 hoặc 5 phiếu theo mức); `tally_votes.py` đếm; người dùng quyết; sau đó Designer viết `01-system`.
- **Điều kiện qua gate:** quyết định có đủ phiếu đúng định dạng; `decision.md` ghi đề xuất, tỉ lệ, thiểu số, rủi ro và quyết định của người dùng; mỗi quyết định sinh rủi ro vào sổ rủi ro (Q6); người dùng duyệt. Trọng tâm: Q3, Q5, Q6, Q8.
- **File tạo ra:** `01-system/system-context.md`, `containers.md`, `architecture-style.md`, `integrations.md` (mức S: tối thiểu `architecture-style.md` và `containers.md`; `integrations.md` bắt buộc khi dự án có hệ thống ngoài, chỉ được bỏ khi không có hệ thống ngoài nào, lý do ở cột "Lý do (Q8)" của `project-profile.md`); `.agent-workspace/decisions/D-xxx-<tên>/` (`brief.md`, `votes/`, `tally.md`, `decision.md`), `decisions/decision-log.md`.
- **Script:** `call_council_cli.py`, `tally_votes.py`, `check_links.py`, `check_numbers.py`, `check_profile.py`, `check_workspace.py`, `promote_drafts.py` (sau khi bạn duyệt gate).

## G4. Stack và phiên bản

- **Đầu vào:** TC đã duyệt, kiểu kiến trúc đã chốt, kiến thức stack ở `~/knowledge/stacks/<stack>/`.
- **Việc:** với từng lớp, Researcher lập longlist có nguồn → loại theo TC (knockout) → shortlist → chấm theo trọng số. Hội đồng quyết stack từng lớp, phiên bản chốt và loại database (mức S: chỉ stack từng lớp; phiên bản chốt không qua hội đồng nhưng vẫn phải có trong `versions-features.md` và được người dùng duyệt ở G4, Q5). Spike trong container khi mức dự án yêu cầu (XL bắt buộc, xem điều kiện bên dưới): Designer viết đề bài `stack/layers/<lớp>/spikes/S-xx-<tên>.md` (template `spike.md`: image ghim, lệnh, kết quả mong đợi kiểm được bằng máy); Orchestrator chạy `run_spike.py --spike S-xx --show`, trình người dùng, và chỉ khi người dùng nói đúng `S-xx: chạy` mới ghi dòng vào mục "Spike được duyệt chạy" của `state.md` (kèm sha256 đề bài) rồi chạy `run_spike.py --spike S-xx`, script ghi `S-xx-<tên>.result.md` (`đạt` / `không đạt` / `lỗi`); sửa đề bài thì phải xin lại. Sau khi chốt database, Researcher xác minh từng link nguồn của hằng số DB trong `~/knowledge/stacks/<db>/constants-<major>.yaml` (đúng phiên bản chốt) rồi chép vào `capacity/db-constants/<db>-<major>.yaml`. Cuối cùng kiểm tra chéo toàn stack và lập ma trận phiên bản và tính năng.
- **Điều kiện qua gate:** từng lớp được người dùng duyệt; ma trận phiên bản đã duyệt (Q5); kiểm tra chéo không còn xung đột; mọi dữ kiện có link nguồn chính thức (Q4); mỗi database đã chốt có file hằng số `capacity/db-constants/<db>-<major>.yaml` với mọi hằng số có link nguồn. **Mức XL:** mỗi lớp trong `stack/layers/` thuộc danh sách bắt buộc có ít nhất một spike có kết quả `đạt` chạy trên đề bài hiện tại (`check_workspace.py` kiểm ở G4). Danh sách bắt buộc là `data`, `messaging`, `backend` (runtime, framework) và `infrastructure` (`core/data/spike.yaml`), cộng các lớp Planner đánh dấu thêm ở mục "Lớp cần spike" của `plan/plan.md` (mỗi lớp một dòng gạch đầu dòng, người dùng duyệt ở G0); `tooling` và `third-party` không bắt buộc. Trọng tâm: Q4, Q5, Q6, Q8.
- **File tạo ra:** phần còn lại của `02-tech-stack/`: `README.md`, `layers/`, `versions-features.md`, `compatibility.md`, `cost-licensing.md`, `team-readiness.md`, `exit-strategy.md`; `.agent-workspace/stack/layers/<lớp>/` (`longlist.md`, `knockout.md`, `shortlist.md`, `scoring.md`, `spikes/S-xx-<tên>.md` và `spikes/S-xx-<tên>.result.md`), `stack/cross-check.md`, `capacity/db-constants/<db>-<major>.yaml`, `decisions/D-xxx-*`.
- **Script:** `run_spike.py`, `call_council_cli.py`, `tally_votes.py`, `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py`, `check_workspace.py`, `promote_drafts.py` (sau khi bạn duyệt gate).

## G5. Capacity sơ bộ

- **Đầu vào:** NFR, giả định, stack đã chốt.
- **Việc:** Designer điền tham số capacity (`assumptions.yaml`, `tables.yaml`, `storage.yaml`, `compute.yaml`, `pricing.yaml`, schema ở [capacity-schema.md](capacity-schema.md)) và đặt trong `tables.md` mỗi bảng một cặp dấu `<!-- BEGIN:calc:<bảng> -->` / `chờ script` / `<!-- END:calc:<bảng> -->`; Orchestrator chạy `calc_capacity.py` (Designer không có Bash), `calc_capacity.py` tính tải, dung lượng, chi phí theo từng mốc của mức dự án (S: ra mắt, 1 năm; M: thêm 3 năm; L: thêm 5 năm; XL: thêm đỉnh tải).
- **Điều kiện qua gate:** mọi hằng số và đơn giá có nguồn và ngày tra cứu; mỗi database khai đủ giả định phình, WAL, bản sao, backup, TOAST và MAXALIGN; script tính lại khớp bản nháp (Q4); người dùng duyệt tải, dung lượng, chi phí từng mốc. Trọng tâm: Q2, Q4, Q6, Q8.
- **File tạo ra:** `03-capacity/workload-model.md`, `data-sizing.md`, `storage-sizing.md`, `compute-sizing.md`, `cost-model.md`; `.agent-workspace/capacity/` (`assumptions.yaml`, `tables.yaml`, `storage.yaml`, `compute.yaml`, `pricing.yaml`), `checks/numbers-<ngày>.md`.
- **Script:** `calc_capacity.py`, `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py`, `check_workspace.py`, `promote_drafts.py` (sau khi bạn duyệt gate).

## G6. Luồng chính

- **Đầu vào:** context, kiểu kiến trúc, stack, capacity sơ bộ.
- **Việc:** Designer viết các luồng chính (sơ đồ tuần tự, lỗi, dữ liệu chạm tới); chưa thiết kế chi tiết trước khi luồng được duyệt.
- **Điều kiện qua gate:** mọi FR có ít nhất một luồng (Q1), `check_trace.py` sạch; người dùng duyệt luồng. Trọng tâm: Q1, Q6, Q8.
- **File tạo ra:** `04-flows/flow-index.md`, `04-flows/FL-xxx-<tên>.md`; `.agent-workspace/checks/trace-<ngày>.md`.
- **Script:** `check_trace.py`, `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py`, `check_workspace.py`, `promote_drafts.py` (sau khi bạn duyệt gate).

## G7. Thiết kế chi tiết

- **Đầu vào:** luồng chính đã duyệt, stack, capacity sơ bộ.
- **Việc:** Designer thiết kế chi tiết từng app frontend (kiến trúc và tối ưu cho thiết bị thật, không quyết định visual; Q7), từng service, từng database. Hội đồng quyết ranh giới service, chiến lược nhất quán dữ liệu, kiểu dữ liệu của các bảng tăng nhanh nhất, đặc biệt khóa chính và khóa ngoại. Khi kiểu dữ liệu thật lộ ra, **quay lại G5** tính lại capacity rồi mới đi tiếp.
- **Điều kiện qua gate:** mỗi thành phần truy về FR/NFR/ràng buộc (Q1), có mục "Tối ưu" với chỉ số bằng số (Q2), có đường scale, nâng cấp và gánh nặng bảo trì (Q3); frontend có ma trận thiết bị và ngân sách hiệu năng (Q7); bảng, bucket, event nhắc trong luồng đều có ở phần data; từng service, database, app được người dùng duyệt. Trọng tâm: Q1, Q2, Q3, Q7 (frontend), Q6, Q8.
- **File tạo ra:** `05-frontend/` (`overview.md`, `device-matrix.md`, `performance-budget.md`, `<app>/*`), `06-backend/` (`overview.md`, `communication.md`, `cross-cutting.md`, `repo-structure.md`, `contracts/`, `services/<service>/*`), `07-data/` (`overview.md`, `databases/<db>/*`, `object-storage.md`, `cache.md`, `messaging.md`, `consistency.md`, `backup-recovery.md`), theo phần hồ sơ giữ lại; `.agent-workspace/capacity/tables.yaml` cập nhật, `reviews/R-xxx-<phần>.md`.
- **Script:** `calc_capacity.py`, `call_council_cli.py`, `tally_votes.py`, `check_trace.py`, `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py`, `check_workspace.py`, `promote_drafts.py` (sau khi bạn duyệt gate).

## G8. Bảo mật, hạ tầng, quy trình

- **Đầu vào:** thiết kế chi tiết đã duyệt, capacity.
- **Việc:** Designer viết từng phần bảo mật, hạ tầng, quy trình (chỉ phần mà hồ sơ dự án áp dụng).
- **Điều kiện qua gate:** mỗi phần đạt Q1–Q3; chỉ có phần được hồ sơ cho phép (`check_profile.py` sạch); người dùng duyệt từng phần. Trọng tâm: Q2, Q3, Q6, Q8.
- **File tạo ra:** `08-security/` (`authz-matrix.md`, `threat-model.md`, `secrets-compliance.md`), `09-infrastructure/` (`topology.md`, `environments.md`, `scaling-ha.md`, `observability.md`, `ci-cd.md`), `10-process/` (`delivery.md`, `data-change.md`, `maintenance.md`, `operations.md`); `.agent-workspace/reviews/*`.
- **Script:** `check_trace.py`, `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py`, `check_workspace.py`, `promote_drafts.py` (sau khi bạn duyệt gate).

## G9. Rủi ro và roadmap

- **Đầu vào:** sổ rủi ro mở từ G1, toàn bộ quyết định và rủi ro đã sinh ra từ G3 trở đi.
- **Việc:** Designer hoàn thiện sổ rủi ro (đã mở từ G1 và được bổ sung ở mỗi gate): hợp nhất, chấm lại điểm và viết roadmap (mức S: sổ rủi ro rút gọn chỉ ghi rủi ro ≥ 8 điểm, roadmap chỉ `implementation-plan.md`); rủi ro từ 15 điểm trở lên phải được xử lý hoặc được người dùng chấp nhận rõ ràng.
- **Điều kiện qua gate:** không còn rủi ro ≥ 15 điểm chưa xử lý; rủi ro ≥ 15 được chấp nhận thì ghi ở `risks/acceptance.md` (Q6); người dùng duyệt sổ rủi ro. Trọng tâm: Q3, Q6, Q8.
- **File tạo ra:** `11-risks/risk-register.md`, `12-roadmap/` (`implementation-plan.md` mọi mức; `scaling-stages.md`, `upgrade-roadmap.md` từ mức M); `.agent-workspace/risks/acceptance.md`.
- **Script:** `check_trace.py`, `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py`, `check_workspace.py`, `promote_drafts.py` (sau khi bạn duyệt gate).

## G10. Kiểm tra chéo và phát hành

- **Đầu vào:** toàn bộ bản nháp đã qua G1–G9.
- **Việc:** chạy toàn bộ script; `calc_capacity.py` tính lại lần cuối; Reviewer soát toàn bộ theo Q1–Q8; `promote_drafts.py` chép lại mọi phần cùng `README.md` sang `architecture/` (phần nào đổi sau gate của nó thì được cập nhật); `archive_release.py` chụp workspace vào `archive/vN/` và cập nhật `CHANGELOG.md`, chỉ khi `architecture/` còn đúng bản vừa promote G10 (báo cáo promote ghi hash từng file).
- **Điều kiện qua gate:** tính lại toàn bộ số khớp, mọi script sạch, người dùng duyệt phát hành vN. Trọng tâm: cả Q1–Q8.
- **File tạo ra:** `README.md` (mục lục, phiên bản, mức áp dụng) và `CHANGELOG.md` (chế độ nâng cấp: khác gì bản trước) của `architecture/`; `.agent-workspace/archive/vN/`, `checks/*-<ngày>.md`.
- **Script:** toàn bộ: `calc_capacity.py`, `call_council_cli.py`, `tally_votes.py`, `check_links.py`, `check_trace.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py`, `check_workspace.py`, `promote_drafts.py`, `archive_release.py`.
