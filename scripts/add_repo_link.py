import sys
p = sys.argv[1] if len(sys.argv) > 1 else "docs/REPORT.md"
s = open(p, encoding="utf-8").read()
url = "https://github.com/Alessandrarye/newsgenie"
done = []

# 1. Make the top Repository line a clickable link
old = "**Repository:** github.com/Alessandrarye/newsgenie"
if old in s:
    s = s.replace(old, f"**Repository:** <{url}>")
    done.append("clickable Repository link")

# 2. Add the sentence at the end of section 1
sentence = f"Full source code, tests, and setup instructions are available at <{url}>."
anchor = "\n## 2. AI chatbot design"
if sentence in s:
    pass
elif s.count(anchor) == 1:
    s = s.replace(anchor, f"\n{sentence}\n{anchor}")
    done.append("section 1 sentence")
else:
    sys.exit("Could not find the start of section 2 (nothing changed)")

open(p, "w", encoding="utf-8").write(s)
print("Added:", ", ".join(done) if done else "nothing needed (already there)")
