"""Regenerate the arXiv abstract in SUBMISSION-PACKAGE.md from the current manuscript.

The packaged plain-text abstract is the version from before today's edits. It
still carries the uncalibrated consequence claim that was corrected in the
claim-support pass, and it lacks the data-product framing, the pooled-sample
disclosure, the glosses and the closing repairs. Posting it would publish an
abstract that disagrees with the paper it is attached to.

This extracts the live abstract, strips LaTeX, rewraps it, and rewrites the
block together with its character count.
"""
import io
import re

tex = io.open("paper/latex/main.tex", encoding="utf-8").read()
body = tex.split("\\begin{abstract}", 1)[1].split("\\end{abstract}", 1)[0]

# Strip the markup arXiv's abstract box cannot take.
s = body
s = re.sub(r"\\texttt\{([^{}]*)\}", r"\1", s)
s = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", s)
s = re.sub(r"\\textit\{([^{}]*)\}", r"\1", s)
s = re.sub(r"\\S\\,\\ref\{[^}]*\}", "", s)
s = re.sub(r"\\cite\{[^}]*\}", "", s)
s = s.replace("\\%", "%").replace("\\&", "&").replace("\\_", "_")
s = re.sub(r"``|''", '"', s)
s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
s = re.sub(r"[{}]", "", s)
s = re.sub(r"\s+", " ", s).strip()

assert "\\" not in s, "residual LaTeX: " + s[:120]

# Wrap at 96 columns, matching the block already in the file.
words, lines, cur = s.split(" "), [], ""
for w in words:
    if len(cur) + len(w) + 1 > 96:
        lines.append(cur)
        cur = w
    else:
        cur = (cur + " " + w).strip()
lines.append(cur)
wrapped = "\n".join(lines)

pkg = io.open("SUBMISSION-PACKAGE.md", encoding="utf-8").read()
start = pkg.index("## Abstract (plain text, LaTeX stripped, for arXiv's abstract box)")
end = pkg.index("## Categories")
block = (
    "## Abstract (plain text, LaTeX stripped, for arXiv's abstract box)\n\n"
    "%d characters, against arXiv's 1,920-character limit. Regenerated from\n"
    "paper/latex/main.tex; re-run the generator if the abstract changes again.\n\n"
    "```\n%s\n```\n\n" % (len(s), wrapped)
)
io.open("SUBMISSION-PACKAGE.md", "w", encoding="utf-8", newline="").write(
    pkg[:start] + block + pkg[end:])

print("abstract regenerated:", len(s), "characters")
print("first 90:", s[:90])
