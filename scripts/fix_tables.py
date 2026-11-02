import re, sys
p = sys.argv[1] if len(sys.argv) > 1 else "docs/REPORT.md"
s = open(p, encoding="utf-8").read()
# first-column header -> relative column widths (pandoc sizes columns by dash count)
tables = {
    ("Layer", "Technology", "Job"): [14, 16, 38],
    ("Intent", "Example", "Route"): [18, 30, 26],
    ("Order", "Provider", "Key needed", "Notes"): [7, 18, 10, 36],
    ("Node", "What it does"): [15, 54],
}
fixed = []
for cols, widths in tables.items():
    header = r"\|\s*" + r"\s*\|\s*".join(map(re.escape, cols)) + r"\s*\|"
    pat = r"(?:<!-- prettier-ignore -->\n)?(" + header + r")\n\|[-:| ]+\|"
    sep = "|" + "|".join("-" * w for w in widths) + "|"
    s, n = re.subn(pat, lambda m: "<!-- prettier-ignore -->\n" + m.group(1) + "\n" + sep, s, count=1)
    if n:
        fixed.append(cols[0])
    else:
        print(f"WARNING: could not find the '{cols[0]}' table")
# Author / Repository on separate lines (backslash break survives Prettier and whitespace trimming)
s, n = re.subn(r"(\*\*Author:\*\* [^\n]*?)[ \\]*\n(\*\*Repository:\*\*)", r"\1\\\n\2", s, count=1)
if n:
    fixed.append("Author line")
open(p, "w", encoding="utf-8").write(s)
print("Fixed tables:", ", ".join(fixed) if fixed else "none")
