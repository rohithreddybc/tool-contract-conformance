"""Static analysis half of the conformance checker: extract.py (draft clauses for human review)
and checks.py (AST candidate-defect-site checks). Nothing in this package executes benchmark
code -- both modules operate on source text and `ast` trees only, which is what lets them run
under this repo's ambient 3.11.7 interpreter against tau2-bench sources despite tau2 itself
requiring >=3.12 (ARCHITECTURE-FINAL.md sec 2, "Adapter process model").
"""
