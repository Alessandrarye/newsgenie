import re, sys
p = sys.argv[1] if len(sys.argv) > 1 else "docs/REPORT.md"
s = open(p, encoding="utf-8").read()
if "screenshots/app-overview.png" in s:
    sys.exit("Images already added; nothing changed.")
img = lambda alt, f: f"![{alt}](screenshots/{f})"
edits = [
    ("\n## 2. AI chatbot design",
     img("NewsGenie interface with category news, reliability ratings, and workflow trace", "app-overview.png")),
    ("\n### 2.3 Response guidelines",
     img('Follow-up "Tell me more about 2" resolved by the LLM classifier using conversation memory', "follow-up.png")),
    ("\n### 4.3 Performance",
     img("NewsAPI rejected an invalid key (401); the workflow fell back to GNews and still delivered headlines", "fallback.png")),
]
for anchor, line in edits:
    if s.count(anchor) != 1:
        sys.exit(f"Could not find a unique spot for: {anchor.strip()}  (nothing changed)")
    s = s.replace(anchor, f"\n{line}\n{anchor}")
s, n = re.subn(r"```mermaid\n.*?```", img("NewsGenie LangGraph workflow with routing conditions", "workflow.png"),
              s, count=1, flags=re.S)
if n != 1:
    sys.exit("Could not find the mermaid block in 4.1 (nothing changed)")
open(p, "w", encoding="utf-8").write(s)
print("Added 4 images to", p)
