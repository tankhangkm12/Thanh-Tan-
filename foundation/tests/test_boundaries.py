"""Foundation knows nothing about any plugin family or what an extension is for."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "agentflow"
REPO = Path(__file__).resolve().parents[2]
# Words that belong to dev-backend (or to software-dev at all), not to the shared engine.
BANNED = re.compile(r"backend|migration|postgres|squawk|schemathesis|openapi|\bsql\b|db-engineer|database|software-dev", re.I)


def test_foundation_source_has_no_family_or_plugin_vocabulary():
    offenders = []
    for path in [*SRC.rglob("*.py"), *SRC.rglob("*.json")]:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if BANNED.search(line):
                offenders.append(f"{path.relative_to(SRC)}:{number}: {line.strip()}")
    assert offenders == []


def test_plugins_of_other_families_do_not_reach_into_each_other():
    families = [p for p in (REPO / "families").iterdir() if p.is_dir()]
    for family in families:
        for other in families:
            if other == family:
                continue
            for path in family.rglob("*"):
                if path.is_file() and path.suffix in {".md", ".yaml", ".json"}:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    assert f"families/{other.name}/" not in text, f"{path} points into the {other.name} family"
