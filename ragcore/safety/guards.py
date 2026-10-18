from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from ragcore.core.config import settings
from ragcore.core.exceptions import GuardrailViolationError
from ragcore.core.logger import get_logger

logger = get_logger("ragcore.safety")

JAILBREAK_PATTERNS: list[str] = [
    r"(?i)\bignore\s+(?:all\s+|any\s+)?(?:previous|prior|earlier|above)\s+(?:instructions?|prompts?|rules?|context)\b",
    r"(?i)\bdisregard\s+(?:all\s+|your\s+|the\s+)?(?:previous|prior|system|initial)\b",
    r"(?i)\bforget\s+(?:everything|all\s+(?:previous|prior)|your\s+(?:previous|instructions))\b",
    r"(?i)\bsystem\s*(?:override|prompt\s+override)\b",
    r"(?i)\bsystem\s+message\b",
    r"(?i)\bjail\s*break(?:ed|ing)?\b",
    r"(?i)\bdo\s+anything\s+now\b|\byou\s+are\s+dan\b",
    r"(?i)\b(?:act|behave|operate)\s+as\s+(?:an?\s+)?(?:unrestricted|uncensored|unfiltered|jailbroken|evil)\b",
    r"(?i)\bwithout\s+(?:any\s+)?(?:restrictions?|rules?|limitations?|guidelines?|filters?)\b",
    r"(?i)\byou\s+(?:have|must\s+have)\s+no\s+(?:restrictions?|rules?|limitations?|filters?)\b",
    r"(?i)\b(?:print|repeat|output|reveal|show)\s+(?:your\s+)?(?:initial\s+)?(?:instructions?|system\s+prompt|programmed\s+conditions)\b",
    r"(?i)\bpretend\s+(?:that\s+)?(?:your\s+)?(?:safety\s+)?rules?\s+(?:don'?t|do\s+not|aren'?t|are\s+not)\s+exist\b",
    r"(?i)\byou\s+are\s+now\s+an?\s+",
    r"(?i)\b(?:developer|admin|god)\s+mode\b",
    r"(?i)\boverride\s+(?:your\s+)?(?:safety|initial|previous|system)\b",
    r"(?i)###\s*ADMIN\s+MODE",
    r"(?i)\bdecode\b[^.\n]{0,120}\b(?:follow|obey)\b",
    r"(?i)\b(?:follow|obey)\s+(?:this|the\s+following|these)\s+(?:instruction|directive|message)s?\b",
    r"(?i)\bwhat\s+(?:were|are)\s+you\s+(?:told|given|instructed)\b",
    r"(?i)\bprint\s+it\s+in\s+full\b",
    r"\b(?=[A-Za-z0-9+/]{50,}\b)(?=[A-Za-z0-9+/]*[A-Z])(?=[A-Za-z0-9+/]*[a-z])[A-Za-z0-9+/]{50,}\b",
]

SECRET_PATTERNS: list[str] = [
    r"\bsk-[A-Za-z0-9\-_]{16,}",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bghp_[A-Za-z0-9]{20,}\b",
    r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b",
    r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*[\"']?[^\s\"']{8,}",
    r"\b\d{3}-\d{2}-\d{4}\b",
]

SELF_CHECK_OUTPUT_PROMPT = (
    "Your task is to check if the bot message below complies with the policy.\n"
    "\n"
    "Policy for the bot:\n"
    "- must not contain explicit, abusive, offensive, or harmful content\n"
    "- must not contain racially insensitive content\n"
    "- must not contain insults, threats, or hostile language\n"
    "- must not leak secrets, API keys, passwords, or credentials\n"
    "- if a message is a refusal, it should be polite\n"
    "\n"
    'Bot message: "{{ bot_response }}"\n'
    "\n"
    "Should the message be blocked (Yes or No)?\n"
    "Answer:"
)

SELF_CHECK_FACTS_PROMPT = (
    "Check whether the response is supported by the evidence.\n"
    "A response that declines to answer, says the evidence does not contain the\n"
    "answer, or makes no factual claims is supported.\n"
    "\n"
    "Evidence:\n"
    "{{ evidence }}\n"
    "\n"
    "Response:\n"
    "{{ response }}\n"
    "\n"
    "Is the response supported by the evidence? Answer with a single word: Yes or No.\n"
    "Answer:"
)


@dataclass(frozen=True)
class GuardrailCheck:
    stage: str
    rail: str
    status: str  # "passed" | "blocked"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class GuardrailResult:
    triggered: bool
    action: Literal["pass", "flag", "block"]
    checks: tuple[GuardrailCheck, ...] = ()
    dropped_chunks: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "triggered": self.triggered,
            "action": self.action,
            "checks": [c.to_dict() for c in self.checks],
            "dropped_chunks": self.dropped_chunks,
        }


class SafetyGuard:
    """Balanced-mode NeMo Guardrails wrapper.

    - Input and retrieval gates are heuristic/regex-only (no LLM calls, ~0.01s/check).
    - Output gate runs regex secret detection plus optional LLM self-checks
      (toxicity via `self check output`, grounding via `self check facts`).
    - `check_input`/`check_output` raise `GuardrailViolationError` when blocked
      in fail_mode="block"; in "flag" mode they return action="flag" and the
      caller continues. `check_retrieval` never raises; blocked chunks are dropped.
    - Internal guardrail errors fail open (logged, request continues) to preserve
      availability; the heuristic gates remain best-effort mitigations, not a
      hard security boundary.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._enabled: bool = self._cfg("guardrails_enabled", settings.guardrails_enabled)
        self._fail_mode: str = self._cfg("guardrails_fail_mode", settings.guardrails_fail_mode)
        self._input_scan: bool = self._cfg("guardrails_input_scan", settings.guardrails_input_scan)
        self._retrieval_scan: bool = self._cfg(
            "guardrails_retrieval_scan", settings.guardrails_retrieval_scan
        )
        self._output_moderation: bool = self._cfg(
            "guardrails_output_moderation", settings.guardrails_output_moderation
        )
        self._output_secrets: bool = self._cfg(
            "guardrails_output_secrets", settings.guardrails_output_secrets
        )
        self._grounding: bool = self._cfg(
            "guardrails_grounding_check", settings.guardrails_grounding_check
        )
        self._any_output_check = self._output_secrets or self._output_moderation or self._grounding
        self._rails: Any = None

    def _cfg(self, key: str, default: Any) -> Any:
        return self.config.get(key, default)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _build_rails(self) -> Any:
        from nemoguardrails.rails.llm.config import RailsConfig
        from nemoguardrails.rails.llm.llmrails import LLMRails

        output_flows: list[str] = []
        if self._output_secrets:
            output_flows.append("regex check output")
        if self._output_moderation:
            output_flows.append("self check output")
        if self._grounding:
            output_flows.append("self check facts")

        config: dict[str, Any] = {
            "prompts": [
                {"task": "self_check_output", "content": SELF_CHECK_OUTPUT_PROMPT},
                {"task": "self_check_facts", "content": SELF_CHECK_FACTS_PROMPT},
            ],
            "rails": {
                "input": {"flows": ["regex check input"]},
                "output": {"flows": output_flows},
                "config": {
                    "regex_detection": {
                        "input": {"patterns": JAILBREAK_PATTERNS, "case_insensitive": True},
                        "output": {"patterns": SECRET_PATTERNS, "case_insensitive": True},
                    }
                },
            },
        }
        if self._output_moderation or self._grounding:
            config["models"] = [
                {
                    "type": "main",
                    "engine": "openai",
                    "model": settings.llm_model,
                    "parameters": {
                        "base_url": settings.llm_base_url.rstrip("/") + "/v1",
                        "api_key": "ollama",
                    },
                }
            ]
        return LLMRails(RailsConfig.from_content(config=config))

    @property
    def rails(self) -> Any:
        if self._rails is None:
            self._rails = self._build_rails()
        return self._rails

    def check_input(self, text: str) -> GuardrailResult:
        """Run input rails on a user-supplied text (question or history entry)."""
        if not (self._enabled and self._input_scan):
            return GuardrailResult(triggered=False, action="pass")
        try:
            from nemoguardrails.rails.llm.options import RailType

            r = self.rails.check([{"role": "user", "content": text}], rail_types=[RailType.INPUT])
        except GuardrailViolationError:
            raise
        except Exception as e:
            logger.warning(f"Input guardrail error (failing open): {e}")
            return GuardrailResult(triggered=False, action="pass")
        blocked = r.status.name == "BLOCKED"
        check = GuardrailCheck("input", r.rail or "input", "blocked" if blocked else "passed")
        if not blocked:
            return GuardrailResult(triggered=False, action="pass", checks=(check,))
        return self._enforce("input", check)

    def check_retrieval(self, chunks: list[str]) -> tuple[list[str], GuardrailResult]:
        """Scan each retrieved chunk with input rails and drop blocked ones.

        Never raises; blocked chunks are dropped regardless of fail_mode.
        """
        if not (self._enabled and self._retrieval_scan) or not chunks:
            return chunks, GuardrailResult(triggered=False, action="pass")
        from nemoguardrails.rails.llm.options import RailType

        kept: list[str] = []
        dropped = 0
        blocked_rails: list[str] = []
        for text in chunks:
            try:
                r = self.rails.check(
                    [{"role": "user", "content": text}], rail_types=[RailType.INPUT]
                )
            except Exception as e:
                logger.warning(f"Retrieval guardrail error on chunk (failing open): {e}")
                kept.append(text)
                continue
            if r.status.name == "BLOCKED":
                dropped += 1
                blocked_rails.append(r.rail or "input")
            else:
                kept.append(text)
        if not dropped:
            return kept, GuardrailResult(triggered=False, action="pass")
        check = GuardrailCheck("retrieval", blocked_rails[0], f"blocked {dropped} chunk(s)")
        logger.warning(f"Retrieval guardrail dropped {dropped}/{len(chunks)} chunk(s)")
        # Dropping is the mitigation; "flag" records it without failing the query.
        return kept, GuardrailResult(
            triggered=True, action="flag", checks=(check,), dropped_chunks=dropped
        )

    def check_output(
        self, answer: str, question: str, evidence: list[str] | None
    ) -> GuardrailResult:
        """Run output rails on the generated answer."""
        if not (self._enabled and self._any_output_check):
            return GuardrailResult(triggered=False, action="pass")
        messages: list[dict[str, Any]] = []
        if evidence and self._grounding:
            messages.append(
                {
                    "role": "context",
                    "content": {
                        "check_facts": True,
                        "relevant_chunks": "\n\n".join(evidence),
                    },
                }
            )
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": answer})
        try:
            from nemoguardrails.rails.llm.options import RailType

            r = self.rails.check(messages, rail_types=[RailType.OUTPUT])
        except GuardrailViolationError:
            raise
        except Exception as e:
            logger.warning(f"Output guardrail error (failing open): {e}")
            return GuardrailResult(triggered=False, action="pass")
        blocked = r.status.name == "BLOCKED"
        check = GuardrailCheck("output", r.rail or "output", "blocked" if blocked else "passed")
        if not blocked:
            return GuardrailResult(triggered=False, action="pass", checks=(check,))
        return self._enforce("output", check)

    def _enforce(self, stage: str, check: GuardrailCheck) -> GuardrailResult:
        if self._fail_mode == "block":
            logger.warning(f"Guardrail blocked {stage} (rail={check.rail})")
            raise GuardrailViolationError(
                f"Blocked by safety guardrail at {stage} stage",
                stage=stage,
                rail=check.rail,
                checks=[check.to_dict()],
            )
        logger.warning(f"Guardrail flagged {stage} (rail={check.rail})")
        return GuardrailResult(triggered=True, action="flag", checks=(check,))


def matches_any(patterns: list[str], text: str) -> str | None:
    """Return the first pattern name that matches text, or None. Test helper."""
    for p in patterns:
        if re.search(p, text):
            return p
    return None
