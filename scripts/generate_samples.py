"""Generate the 'Real-time news integration' sample outputs for the report.

Runs the real workflow (real APIs, real keys from .env) for Technology, Finance,
and Sports, plus one topic search, one follow-up, and one general question, and
writes everything to docs/sample_outputs.md.

    python scripts/generate_samples.py
"""

from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newsgenie.config import load_settings  # noqa: E402
from newsgenie.graph import ask, build_graph  # noqa: E402

RUNS = [
    ("Technology headlines (sidebar button)", "Show me the latest technology headlines", "technology"),
    ("Finance headlines (sidebar button)", "Show me the latest finance headlines", "business"),
    ("Sports headlines (sidebar button)", "Show me the latest sports headlines", "sports"),
    ("Follow-up on a listed article", "tell me more about #1", None),
    ("Topic news typed in chat", "any news about Nvidia?", None),
    ("General question", "What is the difference between a stock and a bond?", None),
]


def main() -> None:
    settings = load_settings()
    graph = build_graph(settings)
    thread = str(uuid.uuid4())
    out = [
        "# NewsGenie sample outputs",
        f"Generated {datetime.now():%B %d, %Y at %I:%M %p}. Configured services: "
        + ", ".join(f"{k} {'on' if v else 'off'}" for k, v in settings.status().items()) + ".",
    ]
    for title, text, cat in RUNS:
        print(f"-> {title}")
        start = time.perf_counter()
        result = ask(graph, text, thread, selected_category=cat)
        elapsed = time.perf_counter() - start
        out += [
            f"\n---\n\n## {title}",
            f"**User:** {text}",
            "**Workflow trace:** " + " → ".join(result.get("trace", [])) + f" ({elapsed:.1f}s)",
        ]
        if result.get("errors"):
            out.append("**Fallback events:** " + "; ".join(result["errors"]))
        if result.get("hidden_articles"):
            out.append(f"**Hidden for low reliability:** {len(result['hidden_articles'])}")
        out.append("\n**NewsGenie:**\n\n" + result.get("response", ""))
    path = ROOT / "docs" / "sample_outputs.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n\n".join(out), encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
