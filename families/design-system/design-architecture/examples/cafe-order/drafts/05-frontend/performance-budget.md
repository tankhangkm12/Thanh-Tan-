# Ngân sách hiệu năng

## Ngân sách tài nguyên
<!-- required -->

| App | Tài nguyên | Giới hạn (số + đơn vị) | Cơ sở |
| --- | --- | --- | --- |
| order-web | JS tải ban đầu | 170 KB nén | NFR-001 |
| order-web | JS thêm mỗi route | 60 KB nén | NFR-001 |

## Tối ưu
<!-- required -->

Đo trên thiết bị chuẩn của [device-matrix.md](device-matrix.md).

| App | Chỉ số | Mức sàn | Mục tiêu dự án | NFR | Thiết bị chuẩn |
| --- | --- | --- | --- | --- | --- |
| order-web | LCP | 2,5 s | 2,5 s | NFR-001 | [device-matrix.md](device-matrix.md) |
| order-web | INP | 200 ms | 200 ms | NFR-001 | [device-matrix.md](device-matrix.md) |
| order-web | CLS | 0,1 | 0,1 | NFR-001 | [device-matrix.md](device-matrix.md) |

## Cách đo
<!-- required -->

| Loại đo | Công cụ | Khi nào chạy | Ngưỡng lỗi |
| --- | --- | --- | --- |
| phòng thí nghiệm | bước đo hiệu năng trong CI, trên thiết bị chuẩn | mỗi lần build | LCP trên 2,5 s hoặc JS tải ban đầu trên 170 KB (NFR-001) |
| thực tế người dùng | log truy cập của order-service (kích thước tải, mã lỗi) | liên tục | tỉ lệ lỗi tải file tĩnh trên 1% (NFR-002) |

## Thi hành
<!-- required -->

- Bước CI: `perf-budget` (bước đo hiệu năng so với bảng "Ngân sách tài nguyên")
- Khi vượt: chặn merge

Chi tiết pipeline ở [build-delivery.md](order-web/build-delivery.md) và [ci-cd.md](../09-infrastructure/ci-cd.md).

## Rủi ro
<!-- required -->

Rủi ro hiệu năng trên thiết bị yếu đã khai trong [sổ rủi ro](../11-risks/risk-register.md): R-001.
