"""Detector validation scoring -- experiments/detector_analysis_plan.md sec 4.1, 4.3, 4.4, 5.

This module implements exactly what the pre-registered plan commits to for SCORING a mutant
corpus: it does not generate or run the real corpus (CLAUDE.md forbids that in this milestone),
and is exercised only against toy/bank.py mutants built with mutation/sites.py and
mutation/equivalence.py.

    wilson_interval              -- sec 5: Wilson score interval at 95%, point estimate + bounds
    tool_clustered_wilson        -- sec 5: "pooled intervals ... tool-clustered method"
    Rate / lower_bound_claim     -- sec 5: "claims are stated at the interval's lower bound,
                                    never at the point estimate" -- enforced by the type, not by
                                    caller discipline (see Rate.claim()).
    precision_recall_report      -- per-class, per-tool AND pooled, denominators always printed
    is_behaviorally_live         -- sec 4.1's mechanical survival definition
    classify_escape              -- sec 4.3's three-way clause/probe/canonicalization decomposition
    adjudicate_equivalence       -- sec 4.4's mechanical rules 2 and 3 (rule 1 is left to a human,
                                    see the function's docstring -- not automatable as written)

DEVIATION FLAGGED PER CLAUDE.md ("do not quietly deviate, report it"): sec 5 names Wilson score
intervals and a tool-clustered method for POOLED figures, but does not pin down which clustering
method. There is no closed form that is simultaneously exact, clustering-aware, and free of
resampling for arbitrarily unbalanced cluster sizes -- and CLAUDE.md's methodological constraints
rule out any bootstrap/resampling method by name (a prior rejection was for exactly that). The
concrete choice made here is a **design-effect-adjusted Wilson interval**: an intracluster
correlation coefficient (ICC) is estimated from the per-tool proportions via the standard
one-way-ANOVA estimator for binary/proportion data (Fleiss & Cuzick 1979; Donner & Klar 2000,
*Design and Analysis of Cluster Randomization Trials*, sec 2.2), the design effect is
`1 + (mean_cluster_size - 1) * ICC` (Kish 1965), and the pooled Wilson interval is computed on an
effective sample size `n / design_effect` rather than the raw pooled n. This is closed-form,
deterministic, involves no resampling and no hypothesis test, and collapses to the ordinary
pooled Wilson interval when every tool's proportion is identical (ICC = 0, design effect = 1) --
verified in tests/test_mutation_score.py. It is reported here, in the open, specifically so a
methods reviewer sees the choice rather than inferring one was made silently.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from adapters.contract_check import check_effects, check_precondition_enforcement, to_result_binding
from core.canonical import CanonicalConfig, canonical_equal, diff
from core.model import Contract
from core.predicates import compile_predicate
from core.verdict import ClauseVerdict, Verdict

__all__ = [
    "Z_95",
    "Rate",
    "wilson_interval",
    "design_effect",
    "tool_clustered_wilson",
    "precision_recall_report",
    "InvocationOutcome",
    "invoke_direct",
    "is_behaviorally_live",
    "EscapeCause",
    "classify_escape",
    "EquivalenceRule",
    "adjudicate_equivalence",
]

Z_95 = 1.959963984540054  # scipy.stats.norm.ppf(0.975), hardcoded so this module has no SciPy dependency.


# ---------------------------------------------------------------------------------------------
# sec 5 -- Wilson intervals, and lower-bound-only reporting.
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rate:
    """A rate with its denominator and Wilson interval, always carried together (sec 5:
    "Denominators are printed with every rate"). `point` is exposed for transparency (e.g. a
    table column), but `claim()` is the ONLY method that produces the string a paper may assert
    -- it is always phrased at the lower bound, never the point estimate, so a caller cannot
    accidentally report the point estimate as if it were the claim."""

    successes: float
    n: float
    point: float
    lower: float
    upper: float

    def claim(self, label: str) -> str:
        """"<label> >= <lower bound>, n=<n> (Wilson 95% CI [<lower>, <upper>], point <point>)" --
        sec 5: "Claims are stated at the interval's lower bound, never at the point estimate."""
        if self.n == 0:
            return f"{label}: no data (n=0)"
        return (
            f"{label} >= {self.lower:.3f} (n={self.n:g}; Wilson 95% CI [{self.lower:.3f}, {self.upper:.3f}], "
            f"point estimate {self.point:.3f})"
        )


def wilson_interval(successes: float, n: float, z: float = Z_95) -> Rate:
    """Wilson score interval at confidence level implied by `z` (default 95%). `successes`/`n`
    may be non-integer (tool_clustered_wilson feeds it an effective sample size) -- the formula
    is defined identically either way. Raises ValueError for n<=0 or successes not in [0, n]:
    sec 5 requires printing the denominator, which is meaningless for n=0, so this is a caller
    error to surface immediately rather than paper over with a placeholder interval."""
    if n <= 0:
        raise ValueError(f"cannot compute a rate with denominator n={n}")
    if not (0 <= successes <= n):
        raise ValueError(f"successes={successes} out of range for n={n}")
    phat = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (phat + z2 / (2 * n)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n)) / denom
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return Rate(successes=successes, n=n, point=phat, lower=lower, upper=upper)


# ---------------------------------------------------------------------------------------------
# sec 5 -- tool-clustered pooling. See module docstring's flagged deviation for the method choice.
# ---------------------------------------------------------------------------------------------


def _icc_binary_anova(per_cluster: "list[tuple[float, float]]") -> float:
    """One-way-ANOVA ICC estimator for a binary/proportion outcome across clusters (Fleiss &
    Cuzick 1979; Donner & Klar 2000 sec 2.2). `per_cluster` is [(successes_i, n_i), ...], one
    entry per tool. Returns 0.0 (no clustering penalty) if there are fewer than 2 clusters, if
    every cluster has the same size-1 (n_i<=1 everywhere, giving zero within-cluster degrees of
    freedom), or if the raw estimate is negative -- truncating a negative ICC to 0 is the
    standard convention in this literature (a negative estimate is sampling noise around "no
    clustering effect", not evidence of anti-clustering)."""
    k = len(per_cluster)
    if k < 2:
        return 0.0
    ns = [n for _, n in per_cluster]
    total_n = sum(ns)
    if total_n <= 0:
        return 0.0
    total_x = sum(x for x, _ in per_cluster)
    p_bar = total_x / total_n

    ssb = sum(n * ((x / n if n > 0 else 0.0) - p_bar) ** 2 for x, n in per_cluster)
    ssw = sum((x / n) * (1 - x / n) * n if n > 0 else 0.0 for x, n in per_cluster)

    df_between = k - 1
    df_within = total_n - k
    if df_within <= 0:
        return 0.0
    msb = ssb / df_between
    msw = ssw / df_within

    sum_n2 = sum(n * n for n in ns)
    m0 = (total_n - sum_n2 / total_n) / df_between if df_between > 0 else 0.0
    if m0 <= 1e-9:
        return 0.0

    denom = msb + (m0 - 1) * msw
    if denom <= 0:
        return 0.0
    icc = (msb - msw) / denom
    return max(0.0, min(1.0, icc))


def design_effect(per_cluster: "list[tuple[float, float]]") -> float:
    """Kish's design effect `1 + (mean cluster size - 1) * ICC`, with ICC estimated by
    `_icc_binary_anova`. Always >= 1: clustering can only inflate variance relative to the naive
    (independent-trials) estimate, never shrink it, under this model."""
    k = len(per_cluster)
    if k == 0:
        return 1.0
    ns = [n for _, n in per_cluster]
    total_n = sum(ns)
    if total_n <= 0:
        return 1.0
    m_bar = total_n / k
    icc = _icc_binary_anova(per_cluster)
    return 1.0 + (m_bar - 1.0) * icc


def tool_clustered_wilson(per_tool: "dict[str, tuple[float, float]]", z: float = Z_95) -> Rate:
    """Pooled Wilson interval across tools, variance-inflated by the design effect (see module
    docstring). `per_tool` maps tool name -> (successes, n). The pooled point estimate is the
    ordinary pooled proportion (unaffected by clustering); only the interval widens."""
    per_cluster = list(per_tool.values())
    total_x = sum(x for x, _ in per_cluster)
    total_n = sum(n for _, n in per_cluster)
    if total_n <= 0:
        raise ValueError("cannot compute a pooled rate with total denominator 0")
    deff = design_effect(per_cluster)
    n_eff = total_n / deff
    phat = total_x / total_n
    x_eff = phat * n_eff
    return wilson_interval(x_eff, n_eff, z=z)


# ---------------------------------------------------------------------------------------------
# sec 5 -- precision/recall report shape: per-class, per-tool, and pooled, with denominators.
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassReport:
    operator: str
    per_tool: "dict[str, Rate]"
    pooled: Rate


def precision_recall_report(
    per_operator_per_tool_counts: "dict[str, dict[str, tuple[float, float]]]",
) -> "dict[str, ClassReport]":
    """Build the sec 5 report shape from raw (successes, n) counts, one entry per
    (operator/defect-class, tool). Never computes a plain pooled Wilson over the raw total n --
    always routes pooling through `tool_clustered_wilson` per sec 5's clustering requirement."""
    out: dict[str, ClassReport] = {}
    for operator, per_tool_counts in per_operator_per_tool_counts.items():
        per_tool_rates = {tool: wilson_interval(x, n) for tool, (x, n) in per_tool_counts.items() if n > 0}
        pooled = tool_clustered_wilson(per_tool_counts)
        out[operator] = ClassReport(operator=operator, per_tool=per_tool_rates, pooled=pooled)
    return out


# ---------------------------------------------------------------------------------------------
# sec 4.1 -- mechanical survival definition.
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class InvocationOutcome:
    success: bool
    raw: Any
    error: Optional[str]
    post_state: Any


def invoke_direct(instance: Any, tool: str, args: dict) -> InvocationOutcome:
    """Call `tool` on a live, already-constructed instance (a toy/bank.py-shaped object: state is
    `instance.state`, methods raise on precondition failure) and capture (success, raw/error,
    resulting state). Deliberately generic over *any* exception, not just the object's own error
    type -- a mutant can raise something the original code never would (NameError, TypeError from
    a bad AST transform), and that is itself a real, reportable behavioural difference, not
    something to let propagate and abort scoring."""
    try:
        raw = getattr(instance, tool)(**args)
        return InvocationOutcome(success=True, raw=raw, error=None, post_state=instance.state)
    except Exception as e:  # noqa: BLE001 -- see docstring
        return InvocationOutcome(success=False, raw=None, error=str(e), post_state=instance.state)


def is_behaviorally_live(
    original_cls: type, mutant_cls: type, tool: str, probe_args_list: "list[dict]",
    cfg: Optional[CanonicalConfig] = None,
) -> bool:
    """sec 4.1: "A mutant is behaviourally live iff, on at least one probe in the sec 2 corpus, it
    produces a canonicalized post-state or a canonicalized result differing from the unmutated
    tool on at least one probe." Each probe is run against a FRESH instance of both `original_cls`
    and `mutant_cls` (both zero-arg constructible, matching toy.bank.ToyBank's shape), so probes
    never interact with each other's state -- deliberately: sec 2's corpus is a set of
    independent probes, not a trajectory, and conflating the two would make survival depend on
    probe order."""
    cfg = cfg or CanonicalConfig()
    for args in probe_args_list:
        orig = invoke_direct(original_cls(), tool, args)
        mut = invoke_direct(mutant_cls(), tool, args)
        if not canonical_equal(orig.post_state, mut.post_state, cfg):
            return True
        orig_result = to_result_binding(orig.raw, orig.success, orig.error)
        mut_result = to_result_binding(mut.raw, mut.success, mut.error)
        if not canonical_equal(orig_result, mut_result, cfg):
            return True
    return False


# ---------------------------------------------------------------------------------------------
# sec 4.3 -- three-way escape decomposition.
# ---------------------------------------------------------------------------------------------


class EscapeCause:
    CLAUSE_GAP = "clause_gap"
    PROBE_GAP = "probe_gap"
    CANONICALIZATION_GAP = "canonicalization_gap"


def _referenced_literal_segments(predicate_src: str) -> "set[str]":
    """Every literal (constant-string) subscript/attribute key referenced anywhere in a compiled
    predicate, e.g. `post.accounts[args.id].balance` contributes {"accounts", "balance"} (not
    "id" -- that subscript key is a dynamic path, `args.id`, not a literal). Coarse by
    construction (sec 4.3: "Classification is mechanical where possible") -- it is a bag of
    literal names, not a structural path match, so it can under-discriminate (a clause mentioning
    "balance" anywhere is treated as covering any "balance" field, even in an unrelated part of
    the snapshot). Documented as a known limitation rather than silently assumed precise."""
    compiled = compile_predicate(predicate_src)
    segments: set[str] = set()
    import ast as _ast

    for node in _ast.walk(compiled.tree):
        if isinstance(node, _ast.Subscript) and isinstance(node.slice, _ast.Constant) and isinstance(node.slice.value, str):
            segments.add(node.slice.value)
        if isinstance(node, _ast.Attribute):
            segments.add(node.attr)
    return segments


def _changed_path_segments(pre: Any, post: Any, cfg: Optional[CanonicalConfig] = None) -> "set[str]":
    """Every dotted-path segment name appearing in the diff between pre and post (canonicalized
    per `cfg`), e.g. a diff key "items.widget.tags.0" contributes {"items","widget","tags","0"}."""
    delta = diff(pre, post, cfg)
    segments: set[str] = set()
    for key in delta:
        segments.update(key.split("."))
    return segments


def classify_escape(
    contract: Contract, pre: Any, post_mut: Any, args: dict, result_mut: Any,
    *, error_mut: Optional[str] = None,
    unmasked_cfg: Optional[CanonicalConfig] = None, masked_cfg: Optional[CanonicalConfig] = None,
) -> str:
    """Classify one escape (a behaviourally-live mutant the checker did not flag VIOLATES) into
    exactly one of the sec 4.3 causes, in the mechanical order the plan specifies:

      1. clause_gap: no effect/precondition clause's predicate references any of the literal
         path segments that changed between pre and post_mut.
      2. canonicalization_gap: re-run clause evaluation with volatility masking DISABLED
         (`unmasked_cfg`, default an empty CanonicalConfig) and the checker's own report of
         "no VIOLATES" flips to VIOLATES -- the difference was masked as declared-volatile.
      3. probe_gap: everything else -- a clause covers the changed path, unmasking does not
         change the verdict, so by elimination the specific call this escape was scored against
         did not drive the tool into a state the clause's predicate resolves as VIOLATES for.
         This is the residual/elimination bucket the plan itself designates ("Only genuinely
         ambiguous cases go to sec 4.4") -- see module docstring for the one place this can
         over-attribute a weak predicate (rather than a genuine probe-selection gap) to this
         bucket, which is a limitation of a purely mechanical classifier, not a silent guess.

    `error_mut` is the mutant call's actual raised message (None if it did not raise) -- it is
    NOT reconstructible from `result_mut` alone (a witness result mapping does not distinguish
    "the call returned this dict" from "the call raised with this message" once flattened), so
    the caller must pass it explicitly. An earlier version of this function hardcoded `error=None`
    when calling check_precondition_enforcement, which made the error_signal half of
    on_precondition_violation.expect vacuously always-satisfied for a real error and always-
    violated for a real success -- silently short-circuiting the state_delta half the
    canonicalization-gap path depends on (see tests/test_mutation_score.py's regression test).
    """
    masked_cfg = masked_cfg if masked_cfg is not None else CanonicalConfig()
    unmasked_cfg = unmasked_cfg if unmasked_cfg is not None else CanonicalConfig()

    # Deliberately the UNMASKED diff here, not `masked_cfg`'s: clause_gap asks "does any clause
    # cover what genuinely changed", and a field that changed but got hidden by masking is still
    # a genuine change -- using the masked diff would make every masked-away difference
    # self-report as clause_gap (nothing "changed" once masked) and canonicalization_gap would
    # then be unreachable by construction. This ordering bug was caught by
    # tests/test_mutation_score.py's canonicalization_gap regression test.
    changed = _changed_path_segments(pre, post_mut, unmasked_cfg)
    referenced: set = set()
    for clause in list(contract.effects) + list(contract.preconditions):
        referenced |= _referenced_literal_segments(clause.predicate)
    if not (changed & referenced):
        return EscapeCause.CLAUSE_GAP

    def _any_violates(cfg: CanonicalConfig) -> bool:
        effect_verdicts = check_effects(contract, pre, post_mut, args, result_mut, cfg=cfg)
        precond_verdict = check_precondition_enforcement(contract, pre, post_mut, args, result_mut, error_mut, cfg=cfg)
        verdicts: list[ClauseVerdict] = list(effect_verdicts)
        if precond_verdict is not None:
            verdicts.append(precond_verdict)
        return any(v.verdict == Verdict.VIOLATES for v in verdicts)

    if not _any_violates(masked_cfg) and _any_violates(unmasked_cfg):
        return EscapeCause.CANONICALIZATION_GAP

    return EscapeCause.PROBE_GAP


# ---------------------------------------------------------------------------------------------
# sec 4.4 -- equivalence adjudication. Rules 2 and 3 are mechanical; rule 1 is not automatable
# as written and is left to the human annotator the plan already requires (20% dual-adjudicated).
# ---------------------------------------------------------------------------------------------


class EquivalenceRule:
    RULE_1_INTERFACE_INVISIBLE = "rule_1_interface_invisible"
    RULE_2_VOLATILE_FIELD = "rule_2_volatile_field"
    RULE_3_SEMANTICS_PRESERVING_REFACTOR = "rule_3_semantics_preserving_refactor"


def adjudicate_equivalence(
    *, changed_paths: "set[str]", volatile_paths_matched: "set[str]",
    generated_by_refactor_generator: bool, interface_invisible: Optional[bool] = None,
) -> Optional[str]:
    """Mechanical scaffolding for sec 4.4's three admissible reclassification rules. Returns the
    applicable rule name, or None if no rule applies (the escape stands).

    Rule 2 (volatile field) is fully mechanical: true iff every changed path the mutant touched
    is covered by the canonicalization config's declared-volatile patterns.

    Rule 3 (semantics-preserving refactor) is fully mechanical ONLY in the narrow sense that this
    project can check "was this mutant generated by mutation/equivalence.py's refactor
    generators" (`generated_by_refactor_generator`) -- it cannot independently verify semantic
    equivalence for an arbitrary mutant from first principles; that verification is the burden
    the refactor generators themselves carry (see tests/test_mutation_equivalence.py's exhaustive
    behavioural diffing), not something this function re-derives.

    Rule 1 (interface-invisible) is explicitly NOT automated here: sec 4.4 requires proving "no
    return, no state field, and no error can reflect" the change, which is a claim about the
    COMPLETE surface of every possible future call, not something decidable from one escape's
    witness. `interface_invisible` is accepted as an optional pre-adjudicated boolean (a human
    annotator's call, per sec 4.4's required dual-annotation) rather than computed -- passing
    True here is a statement that a human already made this determination, not that this
    function did.
    """
    if interface_invisible:
        return EquivalenceRule.RULE_1_INTERFACE_INVISIBLE
    if changed_paths and changed_paths.issubset(volatile_paths_matched):
        return EquivalenceRule.RULE_2_VOLATILE_FIELD
    if generated_by_refactor_generator:
        return EquivalenceRule.RULE_3_SEMANTICS_PRESERVING_REFACTOR
    return None
