# Truy vết yêu cầu

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Đây là nơi **định nghĩa** `FR-xx` (ô đầu dòng bảng; không định nghĩa FR ở file khác). `NFR-xx` định nghĩa ở [quality-attributes.md](quality-attributes.md), `C-xx` ở [constraints.md](constraints.md): ở đây chỉ nhắc, không đặt ở ô đầu dòng. Các cột FL, SVC, TBL/BKT điền dần theo gate (G1 để "—", G6 điền FL, G7 điền phần còn lại).

## Yêu cầu chức năng
<!-- required -->

| ID | Mô tả | Nguồn BA | NFR | Ràng buộc | Luồng (FL) | Dịch vụ (SVC) | Bảng / bucket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-xxx | <hành vi hệ thống phải làm, một câu> | <file BA, mục> | <NFR-xx> | <C-xx hoặc —> | <FL-xxx hoặc —> | <SVC-xxx hoặc —> | <TBL-xxx, BKT-xxx hoặc —> |

## Phủ yêu cầu phi chức năng
<!-- required -->

Mỗi NFR được ít nhất một FR hoặc một thành phần hạ tầng đáp ứng. Mỗi NFR một dòng gạch đầu dòng (không dùng bảng có NFR ở ô đầu dòng: ô đầu dòng là chỗ định nghĩa ID, mà `NFR-xx` định nghĩa ở quality-attributes.md).

- <NFR-xx: được đáp ứng bởi FR-xx, SVC-xxx hoặc link mục>

## Yêu cầu chưa phủ

Liệt kê FR/NFR chưa có luồng hoặc thành phần, kèm lý do và gate sẽ phủ. Không có thì ghi "không có".
