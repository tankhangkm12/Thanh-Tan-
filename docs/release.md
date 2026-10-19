# Phát hành (gitflow, làm tay)

Các bước dưới đây do **bạn** chạy. Agent không merge vào `main`, không tạo tag, không push `main`. Ví dụ dùng bản `1.0.0`; thay số khi phát hành bản khác.

Số phiên bản hiện tại: agentflow 0.7.0 (`foundation/pyproject.toml`), dev-core 0.6.0, dev-backend 0.3.0 (`.claude-plugin/plugin.json` của từng plugin). Chưa nâng lên 1.0.0.

## 0. Chuẩn bị

1. `develop` đã chứa mọi thay đổi muốn phát hành, cây làm việc sạch: `git status`.
2. Mục `[Unreleased]` của [CHANGELOG.md](../CHANGELOG.md) đã đúng.
3. Đóng mọi phiên Antigravity (phiên đang chạy giữ file `agentflow.exe`).

## 1. Nhánh release

```
git switch develop
git pull
git switch -c release/1.0.0
```

## 2. Nâng số phiên bản trên nhánh release

Sửa cùng một số phiên bản (hoặc số riêng cho từng thành phần, nếu bạn muốn) ở:

| File | Trường |
|---|---|
| `foundation/pyproject.toml` | `version` |
| `families/software-dev/core/.claude-plugin/plugin.json` | `version` |
| `families/software-dev/backend/.claude-plugin/plugin.json` | `version` |

Rồi:

```
cd foundation
uv lock
cd ..
```

Trong `CHANGELOG.md` đổi `## [Unreleased]` thành `## [1.0.0] - AAAA-MM-DD`, thêm một mục `## [Unreleased]` trống phía trên, và thêm link so sánh nếu có remote. Cập nhật dòng "Số phiên bản hiện tại" ở đầu file.

Chỉ sửa trên nhánh release những gì phục vụ phát hành (số phiên bản, changelog, lỗi nhỏ). Tính năng mới đi vào `develop`.

## 3. Kiểm tra trên nhánh release

```
cd foundation
uv run --python 3.14 pytest
uv run --python 3.12 pytest
cd ..
uv run --with pyyaml --with pytest pytest tools
uv run tools/build.py --check
uv run tools/build.py --plugin families/software-dev/backend --check
claude plugin validate families/software-dev/core --strict
claude plugin validate families/software-dev/backend --strict
agy plugin validate families/software-dev/core
agy plugin validate families/software-dev/backend
uv run tools/smoke.py
uv run tools/smoke_backend.py
uv run tools/smoke_modes.py
```

Quét secret (Docker đang chạy):

```
docker run --rm -v "${PWD}:/repo" zricethezav/gitleaks:v8.24.0 git --redact --no-banner /repo
```

Commit phần nâng phiên bản: `git add -A` rồi `git commit -m "release 1.0.0: versions and changelog"` (trong repo plugin này không có `.agentflow/` nên hook chặn commit trực tiếp không áp dụng).

## 4. Merge vào main và gắn tag

```
git switch main
git pull
git merge --no-ff release/1.0.0 -m "Merge release/1.0.0"
git tag -a v1.0.0 -m "1.0.0"
```

## 5. Merge ngược về develop

```
git switch develop
git merge --no-ff release/1.0.0 -m "Merge release/1.0.0 back into develop"
```

Có xung đột thì giữ số phiên bản và changelog của bản release.

## 6. Đẩy lên remote

```
git push origin main develop
git push origin v1.0.0
```

Xóa nhánh release khi xong: `git branch -d release/1.0.0` và `git push origin --delete release/1.0.0`.

## 7. Cập nhật marketplace và máy dùng

`.claude-plugin/marketplace.json` không ghi số phiên bản, Claude Code đọc `version` trong `plugin.json` của từng plugin. Sau khi push:

- Hiện mọi plugin dùng nguồn đường dẫn tương đối (`./families/...`), nên người dùng nhận đúng nhánh mà marketplace được thêm từ đó (mặc định nhánh mặc định của repo). Nguồn đường dẫn tương đối không ghim được `ref`/`sha`. Muốn ghim vào tag `v1.0.0`, đổi `source` của từng plugin sang dạng object `git-subdir` (`url`, `path`, `ref`) theo [tài liệu marketplace](https://code.claude.com/docs/en/plugins/marketplace-reference#plugin-sources); đây là quyết định của bạn, không bắt buộc.
- Cài lại agentflow: `uv tool install --force --reinstall ./foundation` (đóng phiên Antigravity trước).
- Claude Code: `claude plugin marketplace update thanh-tan-plugins`, rồi `claude plugin update dev-core@thanh-tan-plugins` và `claude plugin update dev-backend@thanh-tan-plugins`.
- Antigravity: `agy plugin install` lại từng plugin (lệnh cài chép một bản vào máy).
- Kiểm: `claude plugin list`, `agy plugin list`, `agy agents`.

## Hotfix sau phát hành

Nhánh `hotfix/...` tách từ `main`, sửa, merge `--no-ff` vào `main`, gắn tag `v1.0.1`, rồi merge ngược vào `develop`. Quy trình giống mục 4–6.
