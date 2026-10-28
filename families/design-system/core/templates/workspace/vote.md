---
decision: D-<xxx>
round: <1 | 2>
perspective: <fit | cost-ops | numbers-nfr | evolution | risk-data>
member: <model-slug, trùng phần cuối tên file>
model: <tên model thật>
via: <subagent | cli>
choice: <A | B | ... | none>
scores:
  A: {<TC-01>: <0-5>, <TC-02>: <0-5>}
  B: {<TC-01>: <0-5>, <TC-02>: <0-5>}
exclusions:
  A: {<TC-05>: <pass | fail>}
  B: {<TC-05>: <pass | fail>}
overreach:
  A: {points: <0 hoặc số nguyên dương>, reason: "<bắt buộc khi points > 0>"}
  B: {points: 0, reason: ""}
tie_reason: ""
cites: [<TC-xx>, <NFR-xx>, <R-xx>]
---

# Phiếu D-<xxx> · vòng <1 | 2> · <góc nhìn> · <model>

> Thành viên hội đồng ghi vào `decisions/D-xxx-<tên>/votes/r<vòng>-<góc-nhìn>-<model>.md`, mỗi người một file, chỉ ghi phiếu của chính mình. Phần giữa hai dấu `---` là dữ liệu cho `tally_votes.py`; sai định dạng thì phiếu bị từ chối. **Thành viên không tự tính tổng:** chỉ ghi điểm thô; script tính tổng có trọng số từ trọng số trong frontmatter của `brief.md`.
>
> **Khóa frontmatter**
> - `perspective`: một trong năm góc nhìn (`fit` phù hợp và vừa sức; `cost-ops` chi phí và vận hành; `numbers-nfr` số liệu và NFR; `evolution` tiến hóa; `risk-data` rủi ro và dữ liệu).
> - `scores`: điểm thô 0–5 (số nguyên) cho **mọi** TC có trọng số trong brief, với **mọi** phương án. Thiếu ô hoặc thừa TC thì phiếu bị từ chối.
> - `exclusions`: `pass` hoặc `fail` cho **mọi** TC loại trừ trong brief, với mọi phương án. Phương án có `fail` bị loại khỏi phiếu này: không được chọn, không tính tổng.
> - `overreach`: điểm trừ "làm quá tay" cho từng phương án, số nguyên không âm, tối đa 20 mỗi phương án mỗi phiếu (vượt thì phiếu bị từ chối), tính trên tổng quy về thang 100. `points > 0` thì `reason` bắt buộc, nêu cái thừa so với nhu cầu và trích hồ sơ, NFR hoặc `TC`. Phương án vượt xa nhu cầu mà tốn thêm chi phí hoặc độ phức tạp thì bị trừ.
> - `choice`: ID phương án có tổng cao nhất **do script tính** (sau khi loại phương án vi phạm TC loại trừ và trừ điểm làm quá tay). Nếu `choice` lệch phương án đó, `tally_votes.py` báo lỗi phiếu.
> - `tie_reason`: chỉ điền khi có từ hai phương án chênh nhau dưới 0,01 điểm (so giá trị chưa làm tròn), coi là hòa. Thành viên chọn một và ghi lý do trích nguồn; để `""` khi không hòa.
> - `choice: none` ("không phương án nào phù hợp") hợp lệ khi (a) mọi phương án vi phạm ít nhất một TC loại trừ, hoặc (b) `cites` không rỗng và phần "Lý do" nêu vì sao không phương án nào đạt, có trích nguồn.
> - `cites`: mọi ID `TC`, `NFR`, ràng buộc (`C-xx`), giả định (`A-xx`), `R-xx` mà lý do bên dưới trích. Con số trong `03-capacity` thì ghi vào lý do kèm giá trị, không đưa vào `cites`. Phiếu chọn `none` theo (b) phải có `cites` không rỗng.
> - **Số trong lý do:** mọi con số trong một dòng "Lý do" phải xuất hiện nguyên văn trong `brief.md` (hội đồng chỉ đọc brief; brief trích số từ `03-capacity`). Số không có trong brief thì phiếu bị từ chối. Chữ số trong ID (`TC-01`) không phải con số.
> - `via`: `subagent` khi là subagent Claude Code, `cli` khi script gọi CLI ngoài.

## Điểm thô theo tiêu chí

<!-- Chép lại đúng số trong frontmatter để người đọc xem nhanh. KHÔNG ghi tổng. Thang điểm thô: 0 không đáp ứng · 1 kém · 2 dưới mức cần · 3 đạt mức cần · 4 tốt · 5 vượt mức cần (vượt xa nhu cầu thì ghi ở "Làm quá tay", không cộng thêm). -->

| TC | Loại | A | B |
| --- | --- | --- | --- |
| TC-<01> | có trọng số | <0-5> | <0-5> |
| TC-<05> | loại trừ | <pass | fail> | <pass | fail> |

## Lý do

<!-- Mỗi lý do trích ít nhất một TC, NFR, ràng buộc, giả định, con số trong brief (kèm giá trị; số phải có nguyên văn trong brief) hoặc R-xx. Lý do kiểu "chuẩn ngành", "đang phổ biến" không được tính. -->

1. <Lý do> — <TC-xx / NFR-xx / C-xx / giá trị từ 03-capacity / R-xx>

## Làm quá tay

<!-- Khớp `overreach` trong frontmatter. Không có thì ghi "không có". -->

- <Phương án>: <thêm gì so với nhu cầu nào (trích hồ sơ/NFR/TC)>; trừ <n> điểm

## Rủi ro mới

<!-- Rủi ro phương án đã chọn sinh ra mà brief chưa có. Designer sẽ khai vào sổ rủi ro (Q6). Không có thì ghi "không có". -->

- <mô tả ngắn: khả năng 1–5, tác động 1–5 nếu có cơ sở>
