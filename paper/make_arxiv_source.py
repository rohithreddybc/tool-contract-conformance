"""Build an arXiv-ready source tree with the private review mark-up removed.

arXiv distributes LaTeX source, not only the PDF. The manuscript carries
Zichong Wang's review comments and our replies as \zichong{} and \response{}
macro calls. Those are invisible in the compiled submission copy, because
\reviewfalse makes both macros expand to nothing, but anyone who downloads the
arXiv source package would read them in full.

This writes paper/arxiv/ containing a copy of the manuscript with every
\zichong{...} and \response{...} call removed, their definitions removed, and
the review switch removed, plus the bibliography and the .bbl. The output is
compiled and checked before it is considered usable.

Run: python paper/make_arxiv_source.py
"""
import io
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "latex")
OUT = os.path.join(HERE, "arxiv")


def strip_call(text, macro):
    """Remove every \\macro{...} call, matching braces so nesting survives."""
    token = "\\" + macro + "{"
    removed = 0
    while True:
        start = text.find(token)
        if start == -1:
            return text, removed
        i = start + len(token) - 1
        depth = 0
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        text = text[:start] + text[i + 1:]
        removed += 1


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    text = io.open(os.path.join(SRC, "main.tex"), encoding="utf-8").read()

    total = 0
    for macro in ("zichong", "response", "wenbin", "pending", "pendingblock"):
        text, n = strip_call(text, macro)
        total += n
        if n:
            print("removed %d \\%s{} call(s)" % (n, macro))

    # Drop the definitions and the review switch, so nothing survives to hint at them.
    text = re.sub(r"(?m)^\\newcommand\{\\(zichong|response|wenbin|pending|pendingblock)\}.*\n", "", text)
    text = re.sub(r"(?m)^\\newif\\ifreview\s*\n", "", text)
    text = re.sub(r"(?m)^\\review(true|false)\s*\n", "", text)
    text = re.sub(r"(?m)^% Review mark-up\..*\n(?:^%.*\n)*", "", text)

    # Comments can carry the same text; arXiv ships them too.
    kept = []
    for line in text.split("\n"):
        low = line.lstrip().lower()
        if low.startswith("%") and any(w in low for w in ("zichong", "wenbin", "reviewer", "co-author")):
            continue
        kept.append(line)
    text = "\n".join(kept)

    io.open(os.path.join(OUT, "main.tex"), "w", encoding="utf-8", newline="").write(text)
    for name in ("references.bib", "main.bbl"):
        src = os.path.join(SRC, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(OUT, name))

    # The author block legitimately carries the co-authors' names; only macro
    # calls and the review switch count as a leak.
    leaks = [w for w in ("\\zichong{", "\\response{", "\\wenbin{", "ifreview") if w in text]
    print("residual review markup:", leaks if leaks else "none")

    for _ in range(2):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "main.tex"],
                       cwd=OUT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = io.open(os.path.join(OUT, "main.log"), encoding="utf-8", errors="ignore").read()
    pages = re.search(r"main\.pdf \((\d+) pages", log)
    print("compiled pages:", pages.group(1) if pages else "unknown")
    print("errors:", log.count("\n!"), "| undefined:", log.lower().count("undefined"))
    print("\narXiv source written to", OUT)
    return 0 if (pages and pages.group(1) == "10" and not leaks) else 1


if __name__ == "__main__":
    sys.exit(main())
