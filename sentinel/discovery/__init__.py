"""Discovery package: ingest, gap detection, agent channels and elicitation text.

Gap persistence lives in `sentinel.gaps`; the names below are the ones callers import
from `sentinel.discovery` (IMP-338: explicit instead of a star import of one module).
"""

from .intake import (
    extract_requirement_units,
    ingest,
    load_domain_context,
    mature_requirement_rubric,
    regenerate_gaps,
)
from .detection import (
    detect_gaps,
    detect_unit_anchored_gaps,
    extract_functional_signals,
    extract_metric_signals,
    extract_personas,
    gap_question_warnings,
    split_evidence_sentences,
)
from .channels import (
    AnnotationError,
    GAP_ID_RE,
    apply_annotation,
    apply_challenge,
    apply_scrutiny,
    known_requirement_unit_ids,
    raw_input_text,
    record_gap_disposition,
    refresh_knowledge_ledger,
    scrutiny_grounding_text,
    validate_agent_gaps,
    validate_scrutiny_gaps,
)
from .elicitation import (
    build_faq,
    build_interview_script,
    interview_probing_for_gap,
    render_faq,
    render_interview_script,
)
from ..gaps import (
    brief_section_for_gap,
    candidate_options_for_gap,
    expected_format_for_gap,
    next_readiness_stage,
    parse_gap_rows,
    prd_section_for_gap,
    question_for_gap,
    render_gaps,
    unblocks_for_gap,
)

__all__ = [
    "AnnotationError",
    "GAP_ID_RE",
    "apply_annotation",
    "apply_challenge",
    "apply_scrutiny",
    "brief_section_for_gap",
    "build_faq",
    "build_interview_script",
    "candidate_options_for_gap",
    "detect_gaps",
    "detect_unit_anchored_gaps",
    "expected_format_for_gap",
    "extract_functional_signals",
    "extract_metric_signals",
    "extract_personas",
    "extract_requirement_units",
    "gap_question_warnings",
    "ingest",
    "interview_probing_for_gap",
    "known_requirement_unit_ids",
    "load_domain_context",
    "mature_requirement_rubric",
    "next_readiness_stage",
    "parse_gap_rows",
    "prd_section_for_gap",
    "question_for_gap",
    "raw_input_text",
    "record_gap_disposition",
    "refresh_knowledge_ledger",
    "regenerate_gaps",
    "render_faq",
    "render_gaps",
    "render_interview_script",
    "scrutiny_grounding_text",
    "split_evidence_sentences",
    "unblocks_for_gap",
    "validate_agent_gaps",
    "validate_scrutiny_gaps",
]
