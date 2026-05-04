"""Detects repetitive tool-call patterns during agent execution.

Moved from ``agent_extraction.loop_detector`` to the shared agent framework
so any agent (not just extraction) benefits from loop protection.
"""

from __future__ import annotations

import hashlib
from enum import IntEnum


class LoopAction(IntEnum):
    NONE = 0
    WARN = 1
    STOP = 2


# Only tools in this set break read-only streaks.
# Agents should register their "mutating" tools here.
DEFAULT_MUTATING_TOOLS: set[str] = {"finalize_extraction"}


class ToolLoopDetector:
    """Three parallel detectors; highest severity wins.

    1. **Exact-call repetition** — same (name + args) hash.
    2. **Read-only streak** — consecutive calls to non-mutating tools.
    3. **Same-result hash** — identical output from the same tool.
    """

    def __init__(
        self,
        *,
        exact_warn: int = 3,
        exact_stop: int = 5,
        read_only_warn: int = 8,
        read_only_stop: int = 12,
        same_result_warn: int = 4,
        same_result_stop: int = 6,
        mutating_tools: set[str] | None = None,
    ) -> None:
        self._exact_calls: dict[str, int] = {}
        self._read_only_streak = 0
        self._result_hashes: dict[str, dict[str, int]] = {}
        self.exact_warn = exact_warn
        self.exact_stop = exact_stop
        self.read_only_warn = read_only_warn
        self.read_only_stop = read_only_stop
        self.same_result_warn = same_result_warn
        self.same_result_stop = same_result_stop
        self.mutating_tools = mutating_tools or DEFAULT_MUTATING_TOOLS

    def record_tool_call(self, tool_name: str, args: str, result: str) -> LoopAction:
        worst = LoopAction.NONE

        # 1. Exact-call repetition
        call_key = _hash_string(tool_name + "\x00" + args)
        self._exact_calls[call_key] = self._exact_calls.get(call_key, 0) + 1
        worst = max(
            worst,
            self._action_from_count(
                self._exact_calls[call_key], self.exact_warn, self.exact_stop
            ),
        )

        # 2. Read-only streak
        if tool_name in self.mutating_tools:
            self._read_only_streak = 0
        else:
            self._read_only_streak += 1
        worst = max(
            worst,
            self._action_from_count(
                self._read_only_streak, self.read_only_warn, self.read_only_stop
            ),
        )

        # 3. Same-result hash
        result_key = _hash_string(result)
        bucket = self._result_hashes.setdefault(tool_name, {})
        bucket[result_key] = bucket.get(result_key, 0) + 1
        worst = max(
            worst,
            self._action_from_count(
                bucket[result_key], self.same_result_warn, self.same_result_stop
            ),
        )

        return worst

    @staticmethod
    def warn_message() -> str:
        return (
            "You appear to be in a loop. Try a different approach or "
            "finalize your result with the appropriate tool."
        )

    @staticmethod
    def stop_message() -> str:
        return (
            "Tool loop guard: stop repeating the same tool calls. You must "
            "finalize your result now with your best-effort output, even if "
            "imperfect."
        )

    @staticmethod
    def _action_from_count(count: int, warn_at: int, stop_at: int) -> LoopAction:
        if count >= stop_at:
            return LoopAction.STOP
        if count >= warn_at:
            return LoopAction.WARN
        return LoopAction.NONE


def _hash_string(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()
