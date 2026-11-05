"""Asks the user "exhibit or answer in chat?" before the agent shows a new exhibit.

The agent can't be relied on to ask first, so this rail does it in code. It
pauses `exhibit` calls with the same interrupt mechanism WorkSwarm's ask_user
uses, so the user gets the regular option dialog. The agent never decides
whether to ask.

No question is asked when:
- the call isn't `show` for a new exhibit (edits with exhibit_id, read, open,
  list, delete and stop pass straight through);
- the user's message this turn mentions an exhibit;
- the user already picked "Exhibit" in this chat, or answered the dialog in
  their own words this turn.

If the user picks "Exhibit", the paused call runs as it is, so the HTML the agent
already wrote is used with no extra round trip. If they pick "Answer in chat",
the call is cancelled and the agent is told to answer in chat instead. The dialog's
Skip button counts as "you decide" (the exhibit is shown); Cancel stops the call.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

try:
    from openjiuwen.harness.rails.interrupt.ask_user_rail import AskUserPayload, AskUserRequest
    from openjiuwen.harness.rails.interrupt.interrupt_base import BaseInterruptRail, InterruptDecision

    _INTERRUPTS_AVAILABLE = True
except ImportError:  # older openjiuwen without interrupt rails: never ask, never block
    from openjiuwen.harness.rails.base import DeepAgentRail as BaseInterruptRail

    AskUserPayload = AskUserRequest = InterruptDecision = None
    _INTERRUPTS_AVAILABLE = False

try:
    from openjiuwen.core.single_agent.interrupt.state import RESUME_USER_INPUT_KEY
except ImportError:
    RESUME_USER_INPUT_KEY = None

_TOOL_NAME = "exhibit"
_STATE_KEY = "exhibit_ask_gate"
_MENTION_RE = re.compile(r"\bexhibits?\b|展品", re.IGNORECASE)
_CJK_RE = re.compile(r"[㐀-鿿]")

_TEXT = {
    "en": {
        "question": "Should I make this an exhibit or answer in chat?",
        "header": "Format",
        "exhibit": "Exhibit",
        "exhibit_desc": "An interactive page in your browser that I can update and that keeps what you enter",
        "chat": "Answer in chat",
        "chat_desc": "A static chart (SVG or PNG), a table, or a document (PDF, Word or Excel) here in the conversation",
    },
    "zh": {
        "question": "要做成展品，还是直接在对话中回答？",
        "header": "形式",
        "exhibit": "展品",
        "exhibit_desc": "在浏览器中打开的交互页面，我可以继续修改，并会保存你填写的内容",
        "chat": "在对话中回答",
        "chat_desc": "在对话中给出静态图表（SVG 或 PNG）、表格，或文档（PDF、Word 或 Excel）",
    },
}

_CHOSE_CHAT = (
    "[USER_CHOSE_CHAT] The user was asked whether they want an exhibit and chose an answer in chat. "
    "Answer in chat instead{offered}, and don't call exhibit again for this request. "
    "The HTML you wrote was not shown."
)
_FREE_TEXT = (
    "[USER_REPLIED] The user was asked whether they want an exhibit or an answer in chat, and replied "
    "in their own words: {answer!r}. Follow their reply. If they want an exhibit, call exhibit again "
    "(you won't be asked again this turn); otherwise answer in chat."
)
_CANCELLED = (
    "[USER_CANCELLED] The user dismissed the question about showing an exhibit without answering. "
    "Nothing was shown. Don't call exhibit again for this request; reply briefly in chat and let "
    "them say how they'd like it."
)
# WorkSwarm's dialog always shows Skip and Cancel next to the options, and sends these fixed
# texts for them (web frontend InteractionPrompt.tsx). Skip means "you decide": go ahead with
# the exhibit, the recommended option. Cancel means stop.
_SKIPPED_TEXTS = ("用户已跳过此题，未选择任何选项。",)
_CANCELLED_TEXTS = ("用户已取消本次问答，未作答。",)
_DECLINED_THIS_TURN = (
    "[USER_CHOSE_CHAT] The user already chose an answer in chat for this request. "
    "Answer in chat instead of calling exhibit."
)


# ------------------------------------------------------------ pure helpers


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _is_new_show(args: dict[str, Any]) -> bool:
    return args.get("action") == "show" and not args.get("exhibit_id")


def _mentions_exhibit(text: Any) -> bool:
    return isinstance(text, str) and bool(_MENTION_RE.search(text))


def _language(text: Any) -> str:
    return "zh" if isinstance(text, str) and _CJK_RE.search(text) else "en"


_MAX_ALTERNATIVE_CHARS = 120


def _chat_alternative(args: dict[str, Any]) -> str:
    """The agent's own short description of the non-exhibit version, if it gave one."""
    text = args.get("chat_alternative")
    if not isinstance(text, str):
        return ""
    text = " ".join(text.split())
    if len(text) > _MAX_ALTERNATIVE_CHARS:
        text = text[: _MAX_ALTERNATIVE_CHARS - 1].rstrip() + "…"
    return text


def _question(language: str, alternative: str = "") -> dict[str, Any]:
    t = _TEXT[language]
    return {
        "question": t["question"],
        "header": t["header"],
        "options": [
            {"label": t["exhibit"], "description": t["exhibit_desc"]},
            {"label": t["chat"], "description": alternative or t["chat_desc"]},
        ],
        "multi_select": False,
    }


def _answer_values(user_input: Any) -> list[str]:
    """Collect the answer strings from any of the shapes the frontend sends."""
    answers = getattr(user_input, "answers", None)
    if answers is None and isinstance(user_input, dict):
        answers = user_input.get("answers", user_input)
    if answers is None:
        answers = {"": user_input}
    values: list[str] = []
    items = answers.values() if isinstance(answers, dict) else [answers]
    for value in items:
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, (list, tuple)):
            values.extend(v for v in value if isinstance(v, str))
    return [v.strip() for v in values if v and v.strip()]


def _classify(user_input: Any) -> tuple[str, str]:
    """Return ("exhibit" | "chat" | "skip" | "cancel" | "text" | "empty", answer text)."""
    values = _answer_values(user_input)
    if not values:
        return "empty", ""
    if any(v in _CANCELLED_TEXTS for v in values):
        return "cancel", values[0]
    if any(v in _SKIPPED_TEXTS for v in values):
        return "skip", values[0]
    exhibit_labels = {t["exhibit"].casefold() for t in _TEXT.values()}
    chat_labels = {t["chat"].casefold() for t in _TEXT.values()}
    folded = {v.casefold() for v in values}
    if folded & exhibit_labels:
        return "exhibit", values[0]
    if folded & chat_labels:
        return "chat", values[0]
    return "text", "; ".join(values)


def _should_ask(args: dict[str, Any], gate: dict[str, Any]) -> bool:
    if not _is_new_show(args):
        return False
    if gate.get("chose_exhibit") or gate.get("mentioned_this_turn") or gate.get("replied_this_turn"):
        return False
    return True


# ------------------------------------------------------------------- rail


class ExhibitAskRail(BaseInterruptRail):
    """Asks the user whether they want an exhibit before a new one is shown, unless they asked for one."""

    # Higher runs first. WorkSwarm's permission rail (90) checks every tool call, and on resume
    # it treats any answer waiting for that call as a permission approval: our dialog answer
    # isn't one, so it denied the call. Run before it and consume our answer (see
    # _consume_resume_input) so it sees an ordinary first call. Stays below the circuit
    # breaker (95) and the permission queue binding (100).
    priority: int = 92

    def __init__(self) -> None:
        if _INTERRUPTS_AVAILABLE:
            super().__init__(tool_names=[_TOOL_NAME])
        else:
            super().__init__()

    # Session state ---------------------------------------------------------
    @staticmethod
    def _gate(ctx: Any) -> dict[str, Any]:
        session = getattr(ctx, "session", None)
        get_state = getattr(session, "get_state", None)
        if not callable(get_state):
            return {}
        try:
            state = get_state(_STATE_KEY)
        except Exception:  # noqa: BLE001 - missing state means a fresh chat
            return {}
        return dict(state) if isinstance(state, dict) else {}

    @staticmethod
    def _save_gate(ctx: Any, gate: dict[str, Any]) -> None:
        session = getattr(ctx, "session", None)
        update_state = getattr(session, "update_state", None)
        if callable(update_state):
            update_state({_STATE_KEY: gate})

    @staticmethod
    def _consume_resume_input(ctx: Any, tool_call: Any) -> None:
        """Remove our dialog answer so rails after us (the permission rail) don't treat it as theirs."""
        extra = getattr(ctx, "extra", None)
        if RESUME_USER_INPUT_KEY is None or not isinstance(extra, dict) or RESUME_USER_INPUT_KEY not in extra:
            return
        raw = extra[RESUME_USER_INPUT_KEY]
        call_id = getattr(tool_call, "id", "") or ""
        inputs = getattr(raw, "user_inputs", None)
        if isinstance(inputs, dict):  # InteractiveInput: answers keyed by tool call id
            inputs.pop(call_id, None)
            if not inputs:
                extra.pop(RESUME_USER_INPUT_KEY, None)
            return
        if isinstance(raw, dict) and call_id in raw:
            raw.pop(call_id, None)
            if not raw:
                extra.pop(RESUME_USER_INPUT_KEY, None)
            return
        # A bare answer that isn't keyed by call id belongs to this call.
        extra.pop(RESUME_USER_INPUT_KEY, None)

    # Hooks -----------------------------------------------------------------
    async def before_invoke(self, ctx: Any) -> None:
        """Start of a turn: note whether the user's new message mentions an exhibit."""
        query = getattr(getattr(ctx, "inputs", None), "query", None)
        if not isinstance(query, str):
            return  # resuming after the dialog: keep this turn's state
        gate = self._gate(ctx)
        gate.update(
            mentioned_this_turn=_mentions_exhibit(query),
            replied_this_turn=False,
            declined_this_turn=False,
            language=_language(query),
        )
        self._save_gate(ctx, gate)

    async def resolve_interrupt(
        self,
        ctx: Any,
        tool_call: Any,
        user_input: Optional[Any],
        auto_confirm_config: Optional[dict] = None,
    ) -> Any:
        args = _parse_args(getattr(tool_call, "arguments", None))
        gate = self._gate(ctx)

        if user_input is None:
            if not _is_new_show(args):
                return self.approve()
            if gate.get("declined_this_turn"):
                return self.reject(tool_result=_DECLINED_THIS_TURN)
            if not _should_ask(args, gate):
                return self.approve()
            return self.interrupt(
                AskUserRequest(
                    message="",
                    payload_schema=AskUserPayload.to_schema(),
                    questions=[_question(gate.get("language", "en"), _chat_alternative(args))],
                )
            )

        self._consume_resume_input(ctx, tool_call)
        choice, answer = _classify(user_input)
        if choice == "exhibit":
            gate["chose_exhibit"] = True
            self._save_gate(ctx, gate)
            return self.approve()
        if choice == "skip":
            return self.approve()  # "you decide": show the exhibit, but ask again next time
        if choice == "cancel":
            gate["declined_this_turn"] = True
            self._save_gate(ctx, gate)
            return self.reject(tool_result=_CANCELLED)
        if choice == "chat":
            gate["declined_this_turn"] = True
            self._save_gate(ctx, gate)
            alternative = _chat_alternative(args)
            offered = f" (you offered: {alternative})" if alternative else ""
            return self.reject(tool_result=_CHOSE_CHAT.format(offered=offered))
        if choice == "text":
            gate["replied_this_turn"] = True
            self._save_gate(ctx, gate)
            return self.reject(tool_result=_FREE_TEXT.format(answer=answer))
        # Empty answer: ask again rather than guess.
        return self.interrupt(
            AskUserRequest(
                message="",
                payload_schema=AskUserPayload.to_schema(),
                questions=[_question(gate.get("language", "en"), _chat_alternative(args))],
            )
        )
