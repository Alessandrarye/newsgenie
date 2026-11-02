import re, sys
p = sys.argv[1] if len(sys.argv) > 1 else "docs/REPORT.md"
s = open(p, encoding="utf-8").read()
done = []
s2 = s.replace("**Author:** Alessandra Rye\n**Repository:**", "**Author:** Alessandra Rye  \n**Repository:**")
if s2 != s: done.append("author line break")
s = s2
widths = {
    "| Layer | Technology | Job |": "|--------------|----------------|--------------------------------------|",
    "| Intent | Example | Route |": "|------------------|------------------------------|--------------------------|",
    "| Order | Provider | Key needed | Notes |": "|-------|------------------|----------|------------------------------------|",
    "| Node | What it does |": "|---------------|------------------------------------------------------|",
}
for header, sep in widths.items():
    s, n = re.subn(re.escape(header) + r"\n\|[-:| ]+\|", header + "\n" + sep, s, count=1)
    if n: done.append(header.split("|")[1].strip() + " table")
s, n = re.subn(r"\n> Run `python scripts/generate_samples\.py`.*?\n(?=\n|$)", "\n", s, count=1, flags=re.S)
if n: done.append("removed 3.2 note")
open(p, "w", encoding="utf-8").write(s)
print("Fixed:", ", ".join(done) if done else "nothing needed")
