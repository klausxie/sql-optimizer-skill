#!/usr/bin/env python3
import re
import sys
from pathlib import Path

skill_dir = Path(sys.argv[1])
skill_md = skill_dir / "SKILL.md"
if not skill_md.exists():
    raise SystemExit("missing SKILL.md")
text = skill_md.read_text(encoding="utf-8")
if not text.startswith("---\n"):
    raise SystemExit("missing frontmatter")
if not re.search(r"\nname:\s*[^\n]+", text):
    raise SystemExit("missing name in frontmatter")
if not re.search(r"\ndescription:\s*[^\n]+", text):
    raise SystemExit("missing description in frontmatter")
if not (skill_dir / "agents" / "openai.yaml").exists():
    raise SystemExit("missing agents/openai.yaml")
print("ok")
