# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Run a spike (a small trial in a container) and write its result.

The spec is `.agent-workspace/stack/layers/<layer>/spikes/S-<n>-<name>.md`, written by the Designer (template
`templates/workspace/spike.md`): a frontmatter with `image`, `network`, `commands`, `expect` (`exit_code`, `output_contains`,
`output_not_contains`) and the sections Mục tiêu, Lệnh, Kết quả mong đợi. The result goes to `S-<n>-<name>.result.md` next to it,
written only by this script: `đạt`, `không đạt` (it ran, an expectation failed) or `lỗi` (it could not run: image pull failed,
timeout, the engine's own error).

It runs only when `state.md` (section "Spike được duyệt chạy") has a row for exactly this spike ID where the user's verbatim words
read `S-<n>: chạy`, with a date and the sha256 of the spec as it is now: the user approved this very text, so a spec edited after
the approval needs a new one. `--show` prints what would run, with the hash to put in that row, and runs nothing.

The container (Docker, or Podman when Docker is absent or not running) gets no host folder, no device, no extra capability, is
not privileged, has no network unless the spec says `bridge`, and has memory, CPU, process and time limits (data/spike.yaml); the
image must be pinned. The commands run in one container with `sh -ec`.

Exit 0: the spike passed. Exit 1: it did not pass, could not run, is not approved, or the spec is invalid. Exit 2: bad arguments or
no such spike. Each run is appended to `<workspace>/checks/spike-<date>.md`.

    uv run run_spike.py --spike S-02 [--workspace DIR] [--show] [--engine auto|docker|podman]
"""

import argparse
import datetime
import hashlib
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tally_votes as tv  # noqa: E402

ENCODING = "utf-8"
CORE = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = CORE / "data" / "spike.yaml"
SPEC_KEYS = ("spike", "layer", "image", "network", "timeout", "memory", "cpus", "commands", "expect")
REQUIRED_KEYS = ("spike", "layer", "image", "commands", "expect")
EXPECT_KEYS = ("exit_code", "output_contains", "output_not_contains")
SECTIONS = ("Mục tiêu", "Lệnh", "Kết quả mong đợi")
IMAGE_CHARS = re.compile(r"[A-Za-z0-9._/:@-]+")
SHA_RE = re.compile(r"[0-9a-f]{64}")
ENGINE_FAILURE_CODE = 125  # `docker run` / `podman run` exit code for an error of the engine itself


# --- configuration ---------------------------------------------------------------------------------------------------------

@dataclass
class Config:
    engines: list[str]
    id_re: re.Pattern
    section: str
    word: str
    networks: list[str]
    default_network: str
    timeout_default: int
    timeout_max: int
    pull_timeout: int
    memory_default: str
    memory_re: re.Pattern
    memory_max_mb: int
    cpus_default: float
    cpus_max: float
    pids_limit: int
    max_commands: int
    max_command_chars: int
    max_output: int
    forbidden_tags: list[str]
    suffix: str
    ok: str
    failed: str
    error: str
    xl_required_layers: list[str]
    optional_layers: list[str]


def load_config(path: Path) -> tuple[Config | None, list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except (OSError, yaml.YAMLError) as error:
        return None, [f"{path}: {error}"]
    if not isinstance(data, dict):
        return None, [f"{path}: phải là một mapping"]
    errors: list[str] = []

    def get(*keys, kind=None, positive=False):
        value = data
        for key in keys:
            value = value.get(key) if isinstance(value, dict) else None
        if kind is not None and (not isinstance(value, kind) or isinstance(value, bool)):
            errors.append(f"{'.'.join(keys)}: kiểu không đúng")
            return None
        if positive and (value is None or value <= 0):
            errors.append(f"{'.'.join(keys)}: phải dương")
            return None
        return value

    def names(*keys):
        value = get(*keys, kind=list)
        if value is not None and (not value or not all(isinstance(v, str) and v for v in value)):
            errors.append(f"{'.'.join(keys)}: phải là danh sách chuỗi không rỗng")
            return []
        return value or []

    engines, networks = names("engines"), names("networks")
    forbidden, xl, optional = names("forbidden_image_tags"), names("xl_required_layers"), names("optional_layers")
    id_pattern, section, phrase = get("id_pattern", kind=str), get("approval", "section", kind=str), get("approval", "phrase", kind=str)
    default_network, suffix = get("default_network", kind=str), get("result_suffix", kind=str)
    ints = {k: get(*k, kind=int, positive=True) for k in (("timeout", "default"), ("timeout", "max"), ("pull_timeout",), ("pids_limit",), ("max_commands",), ("max_command_chars",), ("max_output_chars",), ("memory", "max_megabytes"))}
    cpus_default, cpus_max = get("cpus", "default", kind=(int, float), positive=True), get("cpus", "max", kind=(int, float), positive=True)
    mem_default, mem_pattern = get("memory", "default", kind=str), get("memory", "pattern", kind=str)
    states = {k: get("states", k, kind=str) for k in ("ok", "failed", "error")}
    if phrase and ("{id}" not in phrase or ":" not in phrase):
        errors.append("approval.phrase phải có {id} và dấu hai chấm, ví dụ \"{id}: chạy\"")
    if default_network and networks and default_network not in networks:
        errors.append("default_network phải nằm trong networks")
    if mem_default and mem_pattern and not re.fullmatch(mem_pattern, mem_default):
        errors.append("memory.default không khớp memory.pattern")
    if errors:
        return None, errors
    try:
        id_re, memory_re = re.compile(id_pattern), re.compile(mem_pattern)
    except re.error as error:
        return None, [f"regex không hợp lệ: {error}"]
    return Config(
        engines, id_re, section, phrase.split(":", 1)[1].strip(), networks, default_network, ints[("timeout", "default")], ints[("timeout", "max")],
        ints[("pull_timeout",)], mem_default, memory_re, ints[("memory", "max_megabytes")], cpus_default, cpus_max, ints[("pids_limit",)],
        ints[("max_commands",)], ints[("max_command_chars",)], ints[("max_output_chars",)], forbidden, suffix, states["ok"], states["failed"], states["error"], xl, optional,
    ), []


# --- the spec --------------------------------------------------------------------------------------------------------------

@dataclass
class Spec:
    id: str
    layer: str
    name: str
    path: Path
    rel: str
    sha: str
    image: str
    network: str
    timeout: int
    memory: str
    cpus: float
    commands: list[str]
    exit_code: int
    contains: list[str]
    not_contains: list[str]
    suffix: str

    @property
    def result_path(self) -> Path:
        return self.path.with_name(self.path.stem + self.suffix)


def spec_hash(text: str) -> str:
    """sha256 of the spec with line endings normalised (git may turn LF into CRLF on Windows)."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode(ENCODING)).hexdigest()


def megabytes(value: str) -> int:
    number, unit = int(value[:-1]), value[-1]
    return number * 1024 if unit == "g" else number


def placeholder(lines: list[str]) -> bool:
    text = [re.sub(r"<!--.*?-->", "", line).strip() for line in lines]
    text = [line for line in text if line]
    return not text or all(re.fullmatch(r"<[^<>]*>", line) for line in text)


def find_specs(workspace: Path, spike_id: str, cfg: Config) -> list[Path]:
    root = workspace / "stack" / "layers"
    found = [p for p in root.glob(f"*/spikes/{spike_id}-*.md") if p.is_file() and not p.name.endswith(cfg.suffix)] if root.is_dir() else []
    return sorted(found)


def parse_spec(path: Path, workspace: Path, cfg: Config) -> tuple[Spec | None, list[str]]:
    rel = path.relative_to(workspace).as_posix()
    problems: list[str] = []

    def bad(code: str, message: str) -> None:
        problems.append(f"{rel}: [{code}] {message}")

    match = re.fullmatch(rf"({cfg.id_re.pattern})-(.+)\.md", path.name)
    if not match or path.name.endswith(cfg.suffix):
        bad("spec-file-name", "tên file phải là S-<số>-<tên>.md")
        return None, problems
    spike_id, name = match.group(1), match.group(2)
    text = tv.read_text(path)
    data, body, error = tv.parse_frontmatter(text)
    if data is None:
        bad("spec-frontmatter", error)
        return None, problems
    for key in REQUIRED_KEYS:
        if key not in data:
            bad("spec-key-missing", f"thiếu khóa `{key}`")
    for key in data:
        if key not in SPEC_KEYS:
            bad("spec-key-unknown", f"khóa lạ `{key}`")
    if problems:
        return None, problems
    if data["spike"] != spike_id:
        bad("spec-id", f"spike {data['spike']!r} khác phần đầu tên file ({spike_id})")
    layer = path.parent.parent.name
    if path.parent.name != "spikes" or path.parent.parent.parent.name != "layers":
        bad("spec-location", "file phải nằm ở stack/layers/<lớp>/spikes/")
    elif data["layer"] != layer:
        bad("spec-layer", f"layer {data['layer']!r} khác thư mục chứa file ({layer})")

    image = data["image"]
    if not isinstance(image, str) or not IMAGE_CHARS.fullmatch(image) or image.startswith(("-", "/", ":", "@")):
        bad("spec-image", f"image không hợp lệ: {image!r}")
    elif "@sha256:" not in image:
        tag = image.rsplit("/", 1)[-1]
        version = tag.split(":", 1)[1] if ":" in tag else ""
        if not version:
            bad("spec-image-unpinned", f"image {image} chưa ghim tag hoặc digest")
        elif version in cfg.forbidden_tags:
            bad("spec-image-unpinned", f"image {image}: tag \"{version}\" không cố định")
    elif not re.search(r"@sha256:[0-9a-f]{64}\Z", image):
        bad("spec-image", f"digest của image phải là sha256 đủ 64 ký tự hex: {image}")

    network = data.get("network", cfg.default_network)
    if network not in cfg.networks:
        bad("spec-network", f"network phải là một trong {', '.join(cfg.networks)}, đang là {network!r}")
    timeout = data.get("timeout", cfg.timeout_default)
    if not tv.is_int(timeout) or not 1 <= timeout <= cfg.timeout_max:
        bad("spec-timeout", f"timeout phải là số nguyên 1-{cfg.timeout_max} giây, đang là {timeout!r}")
    memory = str(data.get("memory", cfg.memory_default)).lower()
    if not cfg.memory_re.fullmatch(memory) or megabytes(memory) > cfg.memory_max_mb:
        bad("spec-memory", f"memory phải dạng 512m hoặc 2g, tối đa {cfg.memory_max_mb}m, đang là {data.get('memory')!r}")
    cpus = data.get("cpus", cfg.cpus_default)
    if isinstance(cpus, bool) or not isinstance(cpus, (int, float)) or not 0 < cpus <= cfg.cpus_max:
        bad("spec-cpus", f"cpus phải là số trong (0, {cfg.cpus_max}], đang là {cpus!r}")

    commands = data["commands"]
    if not isinstance(commands, list) or not commands or not all(isinstance(c, str) and c.strip() for c in commands):
        bad("spec-commands", "commands phải là danh sách lệnh (chuỗi) không rỗng")
        commands = []
    elif len(commands) > cfg.max_commands or any(len(c) > cfg.max_command_chars or "\x00" in c for c in commands):
        bad("spec-commands", f"tối đa {cfg.max_commands} lệnh, mỗi lệnh tối đa {cfg.max_command_chars} ký tự")
    expect = data["expect"]
    exit_code, contains, not_contains = 0, [], []
    if not isinstance(expect, dict) or set(expect) - set(EXPECT_KEYS):
        bad("spec-expect", f"expect phải là mapping với khóa trong {', '.join(EXPECT_KEYS)}")
    else:
        exit_code = expect.get("exit_code", 0)
        if not tv.is_int(exit_code) or not 0 <= exit_code <= 255:
            bad("spec-expect", f"expect.exit_code phải là số nguyên 0-255, đang là {exit_code!r}")
        for key in ("output_contains", "output_not_contains"):
            value = expect.get(key, [])
            if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value) or len(value) > 50:
                bad("spec-expect", f"expect.{key} phải là danh sách chuỗi không rỗng (tối đa 50)")
        contains, not_contains = list(expect.get("output_contains") or []), list(expect.get("output_not_contains") or [])
    for title in SECTIONS:
        lines = tv.section(body, title)
        if lines is None or placeholder(lines):
            bad("spec-section", f"thiếu mục \"## {title}\" hoặc mục còn nguyên chỗ trống của template")
    if problems:
        return None, problems
    return Spec(spike_id, layer, name, path, rel, spec_hash(text), image, network, timeout, memory, float(cpus), list(commands), exit_code, contains, not_contains, cfg.suffix), []


# --- approval --------------------------------------------------------------------------------------------------------------

def approval_error(state_text: str, spec: Spec, cfg: Config) -> str:
    lines = tv.section(state_text, cfg.section)
    how = f"chạy `run_spike.py --spike {spec.id} --show`, trình người dùng, và khi họ nói \"{spec.id}: {cfg.word}\" thì Orchestrator ghi một dòng vào mục \"{cfg.section}\" của state.md (ID, nguyên văn, ngày, sha256 đề bài)"
    if lines is None:
        return f"state.md không có mục \"{cfg.section}\": {how}"
    rows = []
    for line in lines:
        if line.lstrip().startswith("|"):
            cells = tv.split_cells(line)
            if len(cells) >= 4 and cells[0] == spec.id:
                rows.append(cells)
    if not rows:
        return f"state.md chưa có dòng người dùng đồng ý cho {spec.id}: {how}"
    _, quote, date, sha = rows[-1][:4]
    pattern = rf"(?<![\w-]){re.escape(spec.id)}(?![\w-])\s*:\s*{re.escape(tv.nfc(cfg.word)).replace(chr(92) + ' ', chr(92) + 's+')}"
    if not re.search(pattern, tv.nfc(quote), re.IGNORECASE):
        return f"dòng của {spec.id} trong state.md không có lời người dùng dạng \"{spec.id}: {cfg.word}\" (đang là \"{quote}\"): \"ok\" hay câu mơ hồ không phải đồng ý"
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return f"dòng của {spec.id} trong state.md thiếu ngày hợp lệ (YYYY-MM-DD), đang là \"{date}\""
    if not SHA_RE.fullmatch(sha.lower()) or sha.lower() != spec.sha:
        return f"sha256 đề bài trong dòng của {spec.id} ({sha[:12] or 'trống'}…) khác đề bài hiện tại ({spec.sha[:12]}…): đề bài đã đổi sau khi người dùng đồng ý, hoặc dòng ghi sai; trình lại người dùng"
    return ""


# --- the container ---------------------------------------------------------------------------------------------------------

@dataclass
class Outcome:
    exit_code: int | None = None
    output: str = ""
    seconds: float = 0.0
    error: str = ""
    notes: list[str] = field(default_factory=list)


def run_command(argv: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=timeout)


def decode(data: bytes) -> str:
    return data.decode(ENCODING, errors="replace")


def find_engine(cfg: Config, wanted: str, prefix: list[str] | None) -> tuple[str, list[str]]:
    """(name, command prefix). Raises LookupError with every reason when none works."""
    if prefix:
        return "engine-thử", prefix
    reasons = []
    for name in ([wanted] if wanted != "auto" else cfg.engines):
        path = shutil.which(name)
        if not path:
            reasons.append(f"{name}: không có trong PATH")
            continue
        try:
            info = run_command([path, "info"], 90)
        except (OSError, subprocess.SubprocessError) as error:
            reasons.append(f"{name}: {error}")
            continue
        if info.returncode == 0:
            return name, [path]
        reasons.append(f"{name}: `{name} info` lỗi (mã {info.returncode}): {decode(info.stdout).strip().splitlines()[-1][:160] if info.stdout.strip() else 'không rõ'}")
    raise LookupError("không có Docker hay Podman chạy được: " + "; ".join(reasons))


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n… (cắt {len(text) - limit} ký tự giữa) …\n{text[-half:]}"


def run_container(engine: list[str], spec: Spec, cfg: Config) -> Outcome:
    outcome = Outcome()
    try:
        present = run_command([*engine, "image", "inspect", spec.image], 120).returncode == 0
        if not present:
            pulled = run_command([*engine, "pull", spec.image], cfg.pull_timeout)
            if pulled.returncode != 0:
                outcome.error = f"không kéo được image {spec.image} (mã {pulled.returncode}): {decode(pulled.stdout).strip()[-300:]}"
                return outcome
            outcome.notes.append(f"đã kéo image {spec.image}")
    except subprocess.TimeoutExpired:
        outcome.error = f"quá thời gian khi kiểm hoặc kéo image {spec.image}"
        return outcome
    except OSError as error:
        outcome.error = f"không chạy được engine: {error}"
        return outcome
    name = f"spike-{spec.id.lower()}-{secrets.token_hex(4)}"
    argv = [
        *engine, "run", "--rm", "--name", name, "--network", spec.network, "--memory", spec.memory, "--cpus", f"{spec.cpus:g}",
        "--pids-limit", str(cfg.pids_limit), "--security-opt", "no-new-privileges", "--entrypoint", "sh", spec.image, "-ec", "\n".join(spec.commands),
    ]
    started = time.monotonic()
    try:
        proc = run_command(argv, spec.timeout)
    except subprocess.TimeoutExpired:
        outcome.seconds = time.monotonic() - started
        outcome.error = f"quá {spec.timeout}s: đã dừng container"
        try:
            run_command([*engine, "rm", "-f", name], 60)
        except (OSError, subprocess.SubprocessError):
            outcome.notes.append(f"CHƯA gỡ được container {name}: chạy `{engine[0]} rm -f {name}`")
        return outcome
    except OSError as error:
        outcome.error = f"không chạy được engine: {error}"
        return outcome
    outcome.seconds = time.monotonic() - started
    outcome.exit_code = proc.returncode
    outcome.output = clip(decode(proc.stdout), cfg.max_output)
    if proc.returncode == ENGINE_FAILURE_CODE:
        outcome.error = f"engine báo lỗi lúc chạy container (mã {ENGINE_FAILURE_CODE}): {outcome.output.strip()[-300:]}"
    return outcome


def evaluate(spec: Spec, outcome: Outcome, cfg: Config) -> tuple[str, list[tuple[bool, str]]]:
    if outcome.error:
        return cfg.error, []
    checks = [(outcome.exit_code == spec.exit_code, f"exit_code = {spec.exit_code} (thực tế {outcome.exit_code})")]
    checks += [(text in outcome.output, f"đầu ra có \"{text}\"") for text in spec.contains]
    checks += [(text not in outcome.output, f"đầu ra không có \"{text}\"") for text in spec.not_contains]
    return (cfg.ok if all(ok for ok, _ in checks) else cfg.failed), checks


# --- the result file -------------------------------------------------------------------------------------------------------

def fence_for(text: str) -> str:
    longest = max((len(m.group(0)) for m in re.finditer(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def render_result(spec: Spec, state: str, checks: list[tuple[bool, str]], outcome: Outcome, engine: str, today: str, cfg: Config) -> str:
    head = {
        "spike": spec.id, "layer": spec.layer, "result": state, "ran_at": today, "engine": engine, "image": spec.image, "network": spec.network,
        "exit_code": outcome.exit_code, "duration_seconds": round(outcome.seconds, 1), "spec": spec.rel, "spec_sha256": spec.sha,
    }
    lines = ["---", yaml.safe_dump(head, sort_keys=False, allow_unicode=True).rstrip(), "---", "", f"# Kết quả spike {spec.id}: {state}", "",
             f"`run_spike.py` sinh ngày {today} từ [{spec.path.name}]({spec.path.name}); không agent nào sửa file này. Kết quả chỉ có giá trị khi `spec_sha256` còn bằng sha256 của đề bài.", ""]
    if outcome.error:
        lines += ["## Lỗi", "", f"- {outcome.error}", ""]
    if checks:
        lines += ["## Kiểm", ""] + [f"- [{'x' if ok else ' '}] {text}" for ok, text in checks] + [""]
    if outcome.notes:
        lines += ["## Ghi chú", ""] + [f"- {note}" for note in outcome.notes] + [""]
    if outcome.output:
        fence = fence_for(outcome.output)
        lines += ["## Đầu ra", "", f"{fence}text", outcome.output.rstrip("\n"), fence, ""]
    return "\n".join(lines)


def current_result(spec_path: Path, cfg: Config) -> str | None:
    """State of the result file of a spec if it was produced from the spec as it is now; None when there is none or it is stale."""
    result = spec_path.with_name(spec_path.stem + cfg.suffix)
    if not result.is_file() or not spec_path.is_file():
        return None
    data, _, _ = tv.parse_frontmatter(tv.read_text(result))
    if not data or data.get("spec_sha256") != spec_hash(tv.read_text(spec_path)):
        return None
    return data.get("result") if data.get("result") in (cfg.ok, cfg.failed, cfg.error) else None


# --- main ------------------------------------------------------------------------------------------------------------------

def summary(spec: Spec) -> list[str]:
    lines = [
        f"{spec.id} ({spec.rel})", f"  image: {spec.image}", f"  network: {spec.network}", f"  giới hạn: {spec.timeout}s, {spec.memory}, {spec.cpus:g} cpu",
        "  lệnh (sh -ec, một container):",
    ]
    lines += [f"    {i}. {command}" for i, command in enumerate(spec.commands, start=1)]
    lines.append(f"  mong đợi: exit_code = {spec.exit_code}" + "".join(f"; có \"{t}\"" for t in spec.contains) + "".join(f"; không có \"{t}\"" for t in spec.not_contains))
    lines.append(f"  sha256 đề bài: {spec.sha}")
    return lines


def append_report(workspace: Path, today: str, lines: list[str]) -> Path:
    target = workspace / "checks" / f"spike-{today}.md"
    existing = tv.read_text(target) if target.is_file() else f"# run_spike {today}\n"
    tv.write_text(target, existing.rstrip("\n") + "\n\n" + "\n".join(lines) + "\n")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, default=Path(".agent-workspace"), help="default: ./.agent-workspace")
    parser.add_argument("--spike", required=True, help="spike ID, for example S-02")
    parser.add_argument("--show", action="store_true", help="print what would run and the hash to record in state.md; run nothing")
    parser.add_argument("--engine", choices=("auto", "docker", "podman"), default="auto", help="default: the first of data/spike.yaml that works")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="limits and defaults (default: core/data/spike.yaml)")
    parser.add_argument("--engine-prefix", action="append", help=argparse.SUPPRESS)  # tests: replace the engine executable by this command
    parser.add_argument("--date", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"not a folder: {workspace} (run init_workspace.py first)", file=sys.stderr)
        return 2
    cfg, config_errors = load_config(args.config.resolve())
    if cfg is None:
        print("config error: " + "; ".join(config_errors), file=sys.stderr)
        return 2
    if not cfg.id_re.fullmatch(args.spike):
        print(f"--spike phải có dạng {cfg.id_re.pattern}, ví dụ S-02", file=sys.stderr)
        return 2
    specs = find_specs(workspace, args.spike, cfg)
    if not specs:
        print(f"không có đề bài {args.spike}-<tên>.md trong stack/layers/*/spikes/", file=sys.stderr)
        return 2
    if len(specs) > 1:
        print(f"{args.spike} có {len(specs)} đề bài: {', '.join(p.relative_to(workspace).as_posix() for p in specs)}", file=sys.stderr)
        return 2
    today = args.date or datetime.date.today().isoformat()
    spec, problems = parse_spec(specs[0], workspace, cfg)
    if spec is None:
        append_report(workspace, today, [f"## {args.spike}", ""] + [f"- LỖI {p}" for p in problems])
        print(f"error: đề bài {args.spike} không hợp lệ")
        for problem in problems:
            print(f"error: {problem}")
        return 1
    state_path = workspace / "state.md"
    refusal = approval_error(tv.read_text(state_path), spec, cfg) if state_path.is_file() else f"không có {state_path}"
    if args.show:
        print("\n".join(summary(spec)))
        print(f"  duyệt: {'đã có dòng hợp lệ trong state.md' if not refusal else 'CHƯA: ' + refusal}")
        return 0
    if refusal:
        append_report(workspace, today, [f"## {spec.id}", "", f"- TỪ CHỐI (không chạy): {refusal}"])
        print(f"error: không chạy {spec.id}: {refusal}")
        return 1
    try:
        engine_name, engine = find_engine(cfg, args.engine, args.engine_prefix)
    except LookupError as error:
        append_report(workspace, today, [f"## {spec.id}", "", f"- LỖI (không chạy): {error}"])
        print(f"error: {error}")
        return 1
    outcome = run_container(engine, spec, cfg)
    state, checks = evaluate(spec, outcome, cfg)
    tv.write_text(spec.result_path, render_result(spec, state, checks, outcome, engine_name, today, cfg))
    rel = spec.result_path.relative_to(workspace).as_posix()
    lines = [f"## {spec.id} · {state}", "", f"- engine {engine_name}, image {spec.image}, network {spec.network}, {outcome.seconds:.1f}s, exit_code {outcome.exit_code}", f"- kết quả: {rel}"]
    lines += [f"- {'đạt' if ok else 'HỎNG'}: {text}" for ok, text in checks]
    lines += [f"- LỖI: {outcome.error}"] if outcome.error else []
    report = append_report(workspace, today, lines)
    print(f"run_spike {spec.id}: {state} ({engine_name}, {outcome.seconds:.1f}s, exit_code {outcome.exit_code}); kết quả: {rel}; báo cáo: {report}")
    if outcome.error:
        print(f"error: {outcome.error}")
    for ok, text in checks:
        if not ok:
            print(f"error: không đạt: {text}")
    return 0 if state == cfg.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
