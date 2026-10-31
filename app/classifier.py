"""
Prompt classification with hard safety override for high-stakes domains.
Baseline regex classifier and architecture for embedding extension.
"""

import re
from typing import Tuple

# High-stakes domains (legal, medical, financial, tax, investment, contract, dosage, diagnosis)
# Non-negotiable: MUST ALWAYS RUN FIRST AND WIN
HIGH_STAKES_PATTERNS = [
    r"\b(legal|lawyer|attorney|lawsuit|litigation|court|subpoena|deposition|statute)\b",
    r"\b(contract|liability|indemnity|nda|arbitration|patent|trademark|infringement)\b",
    r"\b(medical|doctor|physician|medicine|diagnosis|diagnose|symptom|prescription|dosage)\b",
    r"\b(chemotherapy|cardiology|oncology|neurology|radiology|disease|disorder|pharmaceutical)\b",
    r"\b(financial|tax|taxes|irs|investment|investing|stock|portfolio|dividend|mortgage)\b",
    r"\b(crypto|equity|retirement|401k|ira|capital\s+gains|financial\s+advice)\b",
    r"\b(is\s+this\s+cancer|what\s+dose|should\s+i\s+take|how\s+many\s+mg)\b",
]

CODE_PATTERNS = [
    r"\b(def|class|function|async|await|return|import|from\s+\w+\s+import)\b",
    r"\b(const|let|var|console\.log|println!|public\s+static\s+void|std::)\b",
    r"\b(select\s+.+\s+from|insert\s+into|update\s+.+\s+set|delete\s+from)\b",
    r"\b(python|javascript|typescript|c\+\+|golang|rust|html|css|sql|bash|dockerfile)\b",
    r"(\{|\}|\(\)|=>|===|!==|\[\]|->|\bnull\b|\bundefined\b|\bNone\b)",
    r"\b(debug|refactor|compile|compiler|runtime\s+error|stack\s*trace|syntax\s*error)\b",
    r"\b(git\s+(commit|push|pull|rebase|merge|checkout|status))\b",
]

MATH_PATTERNS = [
    r"\b(solve|equation|equations|derivative|integral|integrate|differentiate)\b",
    r"\b(matrix|matrices|eigenvalue|eigenvector|vector\s+space|polynomial)\b",
    r"\b(algebra|calculus|geometry|trigonometry|arithmetic|prime\s+number)\b",
    r"\b(theorem|proof|prove\s+that|lemma|corollary|qed)\b",
    r"(\d+[\+\-\*\/\^]\d+|[\$|\\\[].*[\$|\\\]]|\\frac|\\sqrt|\\int|\\sum)",
    r"\b(calculate|compute\s+the\s+sum|find\s+the\s+value\s+of|probability)\b",
]

SUMMARIZE_PATTERNS = [
    r"\b(summarize|summarise|summary|tl;?dr|synopsis|recap|abstract)\b",
    r"\b(key\s+takeaways|bullet\s+points|condense|in\s+a\s+nutshell)\b",
    r"\b(briefly\s+explain|give\s+me\s+the\s+highlights|shorten\s+this)\b",
]


_re_high_stakes = re.compile("|".join(HIGH_STAKES_PATTERNS), re.IGNORECASE)
_re_code = re.compile("|".join(CODE_PATTERNS), re.IGNORECASE)
_re_math = re.compile("|".join(MATH_PATTERNS), re.IGNORECASE)
_re_summarize = re.compile("|".join(SUMMARIZE_PATTERNS), re.IGNORECASE)


def is_high_stakes(prompt: str) -> bool:
    """Check if prompt matches any high-stakes pattern. Non-negotiable override."""
    return bool(_re_high_stakes.search(prompt))


def classify_by_regex(prompt: str) -> Tuple[str, float]:
    """
    Rule-based classifier with strict high-stakes precedence.
    Returns (category, confidence).
    """
    # 1. HARD SAFETY OVERRIDE: high-stakes check ALWAYS runs first and wins
    if is_high_stakes(prompt):
        return "high_stakes", 1.0

    # 2. Check code
    if _re_code.search(prompt):
        return "code", 0.90

    # 3. Check math
    if _re_math.search(prompt):
        return "math", 0.90

    # 4. Check summarize
    if _re_summarize.search(prompt):
        return "summarize", 0.85

    # 5. Default chat
    return "chat", 0.70


def classify_prompt(prompt: str) -> Tuple[str, float]:
    """
    Unified classification entrypoint.
    Runs high-stakes check first. If embeddings are available and initialized (Phase 3),
    uses centroid similarity with fallback.
    """
    # HARD SAFETY OVERRIDE: runs first and wins unconditionally
    if is_high_stakes(prompt):
        return "high_stakes", 1.0

    # In Phase 1, use regex classifier
    return classify_by_regex(prompt)
