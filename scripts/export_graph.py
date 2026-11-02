"""Export the LangGraph workflow as a Mermaid diagram (docs/workflow.mmd).

    python scripts/export_graph.py

Paste the file contents into https://mermaid.live to get a PNG for the report,
or view it directly on GitHub (it renders ```mermaid blocks).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newsgenie.graph import build_graph  # noqa: E402

mermaid = build_graph().get_graph().draw_mermaid()
path = ROOT / "docs" / "workflow.mmd"
path.parent.mkdir(exist_ok=True)
path.write_text(mermaid, encoding="utf-8")
print(mermaid)
print(f"\nWrote {path}")
