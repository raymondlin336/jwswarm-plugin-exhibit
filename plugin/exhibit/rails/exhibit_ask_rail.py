"""Dialogs and guards for the exhibit tool, enforced in code instead of left to the agent.

1. Format question: asks "exhibit or answer in chat?" before a new exhibit is shown (details below).
2. Delete confirmation: every `exhibit` delete asks "Delete '<title>'?" in WorkSwarm's dialog.
   Picking Delete lets the call run with confirm set; anything else cancels it.
3. Preview-panel guard: `send_file_to_user` with an .html file that has scripts is refused once
   per turn, telling the agent to use an exhibit (the panel blocks scripts, so charts come out
   blank). Sending the same files again that turn goes through, for when the user wants the file.
4. Skill guard: `exhibit` show is refused until the agent has loaded the "exhibit" skill in this
   chat, so it always has the instructions for writing one.
5. Loop guard: after the same `exhibit` call (same action and fields) fails 3 times in a turn,
   further identical tries are refused and the agent is told to fix the call or stop and explain.

Format question:

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

import ast
import json
import os
import re
from pathlib import Path
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
_SEND_FILE_TOOL = "send_file_to_user"
_SKILL_TOOL = "skill_tool"
_SKILL_NAME = "exhibit"
_SCRIPT_RE = re.compile(r"<script\b", re.IGNORECASE)
_MAX_SCAN_BYTES = 5_000_000
_EXHIBIT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
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
        "delete_question": "Delete \u201c{title}\u201d?",
        "delete_header": "Delete",
        "delete": "Delete",
        "delete_desc": "Permanently delete it, with all its versions and saved data",
        "keep": "Keep it",
        "keep_desc": "Don't delete anything",
    },
    "zh": {
        "question": "要做成展品，还是直接在对话中回答？",
        "header": "形式",
        "exhibit": "展品",
        "exhibit_desc": "在浏览器中打开的交互页面，我可以继续修改，并会保存你填写的内容",
        "chat": "在对话中回答",
        "chat_desc": "在对话中给出静态图表（SVG 或 PNG）、表格，或文档（PDF、Word 或 Excel）",
        "delete_question": "删除\u201c{title}\u201d？",
        "delete_header": "删除",
        "delete": "删除",
        "delete_desc": "永久删除它及其所有版本和保存的数据",
        "keep": "保留",
        "keep_desc": "不删除任何内容",
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
_KEPT = (
    "[USER_KEPT] The user was asked to confirm deleting the exhibit and chose to keep it. Nothing was "
    "deleted. Don't call delete again for it unless they ask."
)
_DELETE_REPLIED = (
    "[USER_REPLIED] The user was asked to confirm deleting the exhibit and replied in their own words: "
    "{answer!r}. Nothing was deleted. Follow their reply; if they do want it deleted, call delete again."
)
_USE_EXHIBIT = (
    "[USE_EXHIBIT] Not sent: {files} is HTML with scripts, and WorkSwarm's file preview panel blocks "
    "scripts, so charts and buttons would show up blank. Show it with the exhibit tool instead (action "
    "show, with the HTML). Only if the user explicitly asked for the HTML file itself, call "
    "send_file_to_user again with the same files and it will go through."
)
_LOAD_SKILL = (
    '[LOAD_SKILL] Not shown yet: load the exhibit instructions first by calling skill_tool with '
    'skill_name "exhibit", then call exhibit show again. Follow them when writing the HTML.'
)
_MAX_SAME_FAILURES = 3
_STOP_LOOP = (
    "[STOP_RETRYING] Not sent: this same exhibit call has already failed {count} times this turn with: "
    "{error} Sending it again won't help. Change the call (for a missing or long page, save it with "
    "write_file and pass its path as html_file), or stop and tell the user plainly what went wrong."
)
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


def _call_shape(args: dict[str, Any]) -> str:
    """An exhibit call's action plus the fields it actually filled in, to spot identical retries."""
    filled = sorted(k for k, v in args.items() if v not in (None, "", [], {}))
    return f"{args.get('action')}|{','.join(filled)}"


def _tool_failure(result: Any) -> tuple[bool, str] | None:
    """(succeeded, error) from an exhibit tool result, or None if it isn't one (e.g. a rail's message)."""
    if isinstance(result, str) and result.lstrip().startswith("{"):
        for parse in (json.loads, ast.literal_eval):
            try:
                result = parse(result)
                break
            except (ValueError, SyntaxError):
                continue
    if not isinstance(result, dict) or "success" not in result:
        return None
    return bool(result.get("success")), str(result.get("error") or result.get("error_code") or "")


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


def _labels(*keys: str) -> dict[str, str]:
    """Map every language's label for each key (casefolded) to that key."""
    return {text[key].casefold(): key for text in _TEXT.values() for key in keys}


_FORMAT_LABELS = _labels("exhibit", "chat")
_DELETE_LABELS = _labels("delete", "keep")


def _classify(user_input: Any, labels: dict[str, str] | None = None) -> tuple[str, str]:
    """Return (a key from labels | "skip" | "cancel" | "text" | "empty", answer text)."""
    labels = _FORMAT_LABELS if labels is None else labels
    values = _answer_values(user_input)
    if not values:
        return "empty", ""
    if any(v in _CANCELLED_TEXTS for v in values):
        return "cancel", values[0]
    if any(v in _SKIPPED_TEXTS for v in values):
        return "skip", values[0]
    for value in values:
        if value.casefold() in labels:
            return labels[value.casefold()], value
    return "text", "; ".join(values)


def _delete_question(language: str, title: str) -> dict[str, Any]:
    t = _TEXT[language]
    return {
        "question": t["delete_question"].format(title=title),
        "header": t["delete_header"],
        "options": [
            {"label": t["delete"], "description": t["delete_desc"]},
            {"label": t["keep"], "description": t["keep_desc"]},
        ],
        "multi_select": False,
    }


def _exhibit_title(exhibit_id: Any) -> str | None:
    """The exhibit's title from its saved metadata, or None if there's no such exhibit."""
    if not isinstance(exhibit_id, str) or not _EXHIBIT_ID_RE.match(exhibit_id):
        return None
    home = Path(os.environ.get("EXHIBIT_HOME") or (Path.home() / ".exhibit"))
    try:
        meta = json.loads((home / "exhibits" / exhibit_id / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    title = meta.get("title") if isinstance(meta, dict) else None
    return title if isinstance(title, str) and title else exhibit_id


def _file_paths(raw: Any) -> list[str]:
    """send_file_to_user's abs_file_path_list: a list, a JSON list, or a single path."""
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = raw
        raw = parsed
    if isinstance(raw, str):
        raw = [raw]
    return [p for p in raw if isinstance(p, str) and p.strip()] if isinstance(raw, (list, tuple)) else []


def _scripted_html(paths: list[str]) -> list[str]:
    """The .html/.htm files among paths that contain a <script> tag."""
    found = []
    for item in paths:
        if Path(item).suffix.lower() not in (".html", ".htm"):
            continue
        try:
            with open(item, "rb") as handle:
                text = handle.read(_MAX_SCAN_BYTES).decode("utf-8", "ignore")
        except OSError:
            continue
        if _SCRIPT_RE.search(text):
            found.append(item)
    return found


def _should_ask(args: dict[str, Any], gate: dict[str, Any]) -> bool:
    if not _is_new_show(args):
        return False
    if gate.get("chose_exhibit") or gate.get("mentioned_this_turn") or gate.get("replied_this_turn"):
        return False
    return True


# ------------------------------------------------------------------- rail


class ExhibitAskRail(BaseInterruptRail):
    """Asks before new exhibits and deletes, keeps scripted HTML out of the preview panel, and makes sure the skill is loaded."""

    # Higher runs first. WorkSwarm's permission rail (90) checks every tool call, and on resume
    # it treats any answer waiting for that call as a permission approval: our dialog answer
    # isn't one, so it denied the call. Run before it and consume our answer (see
    # _consume_resume_input) so it sees an ordinary first call. Stays below the circuit
    # breaker (95) and the permission queue binding (100).
    priority: int = 92

    def __init__(self) -> None:
        if _INTERRUPTS_AVAILABLE:
            super().__init__(tool_names=[_TOOL_NAME, _SEND_FILE_TOOL, _SKILL_TOOL])
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
    def _stateful(ctx: Any) -> bool:
        session = getattr(ctx, "session", None)
        return callable(getattr(session, "get_state", None)) and callable(getattr(session, "update_state", None))

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
        mentioned = _mentions_exhibit(query)
        if mentioned:
            gate["chose_exhibit"] = True  # an explicit ask counts for the rest of the chat
        gate.update(
            mentioned_this_turn=mentioned,
            failures={},
            replied_this_turn=False,
            declined_this_turn=False,
            warned_files=[],
            asked=None,
            language=_language(query),
        )
        self._save_gate(ctx, gate)

    async def after_tool_call(self, ctx: Any) -> None:
        """Count identical failing exhibit calls this turn (see the loop guard)."""
        inputs = getattr(ctx, "inputs", None)
        if getattr(inputs, "tool_name", None) != _TOOL_NAME:
            return
        outcome = _tool_failure(getattr(inputs, "tool_result", None))
        if outcome is None:
            return
        succeeded, error = outcome
        gate = self._gate(ctx)
        if succeeded:
            if gate.get("failures"):
                gate["failures"] = {}
                self._save_gate(ctx, gate)
            return
        raw = getattr(inputs, "tool_args", None) or getattr(getattr(inputs, "tool_call", None), "arguments", None)
        shape = _call_shape(_parse_args(raw))
        failures = dict(gate.get("failures") or {})
        entry = failures.get(shape) or {"count": 0}
        failures[shape] = {"count": int(entry.get("count", 0)) + 1, "error": error}
        gate["failures"] = failures
        self._save_gate(ctx, gate)

    def _ask(self, ctx: Any, gate: dict[str, Any], call_id: str, question: dict[str, Any]) -> Any:
        """Pause this call and show one question; remember which call we asked about."""
        gate["asked"] = call_id
        self._save_gate(ctx, gate)
        return self.interrupt(
            AskUserRequest(message="", payload_schema=AskUserPayload.to_schema(), questions=[question])
        )

    async def resolve_interrupt(
        self,
        ctx: Any,
        tool_call: Any,
        user_input: Optional[Any],
        auto_confirm_config: Optional[dict] = None,
    ) -> Any:
        name = getattr(tool_call, "name", None) or getattr(getattr(ctx, "inputs", None), "tool_name", "")
        args = _parse_args(getattr(tool_call, "arguments", None))
        gate = self._gate(ctx)
        call_id = getattr(tool_call, "id", "") or ""
        language = gate.get("language", "en")

        if name == _SKILL_TOOL:
            if args.get("skill_name") == _SKILL_NAME and not gate.get("skill_loaded"):
                gate["skill_loaded"] = True
                self._save_gate(ctx, gate)
            return self.approve()

        if name == _SEND_FILE_TOOL:
            scripted = _scripted_html(_file_paths(args.get("abs_file_path_list")))
            warned = set(gate.get("warned_files") or [])
            if scripted and not set(scripted) <= warned:
                gate["warned_files"] = sorted(warned | set(scripted))
                self._save_gate(ctx, gate)
                return self.reject(tool_result=_USE_EXHIBIT.format(files=", ".join(scripted)))
            return self.approve()

        # The exhibit tool. A waiting answer is ours only if we asked about this very call;
        # anything else belongs to another rail and is left alone.
        if user_input is not None and call_id and gate.get("asked") == call_id:
            self._consume_resume_input(ctx, tool_call)
            gate["asked"] = None
            if args.get("action") == "delete":
                return self._after_delete_answer(ctx, gate, args, tool_call, user_input)
            return self._after_format_answer(ctx, gate, args, call_id, user_input)

        failed = (gate.get("failures") or {}).get(_call_shape(args))
        if failed and int(failed.get("count", 0)) >= _MAX_SAME_FAILURES:
            return self.reject(tool_result=_STOP_LOOP.format(count=failed["count"], error=failed.get("error", "")))

        action = args.get("action")
        if action == "delete":
            title = _exhibit_title(args.get("exhibit_id"))
            if title is None:
                return self.approve()  # the tool reports that it doesn't exist
            return self._ask(ctx, gate, call_id, _delete_question(language, title))
        if action != "show":
            return self.approve()
        if self._stateful(ctx) and not gate.get("skill_loaded"):
            return self.reject(tool_result=_LOAD_SKILL)
        if not _is_new_show(args):
            return self.approve()
        if gate.get("declined_this_turn"):
            return self.reject(tool_result=_DECLINED_THIS_TURN)
        if not _should_ask(args, gate):
            return self.approve()
        return self._ask(ctx, gate, call_id, _question(language, _chat_alternative(args)))

    @staticmethod
    def _confirmed_args(tool_call: Any, args: dict[str, Any]) -> str:
        """Add confirm: true to the call itself, not just this rail's copy of its arguments.

        WorkSwarm's StreamEventRail runs after this rail and rebuilds ctx.inputs.tool_args from
        tool_call.arguments, so a change to tool_args alone is lost and the tool refuses the delete.
        """
        confirmed = {**args, "confirm": True}
        text = json.dumps(confirmed, ensure_ascii=False)
        try:
            tool_call.arguments = confirmed if isinstance(tool_call.arguments, dict) else text
        except (AttributeError, TypeError):
            pass
        return text

    def _after_delete_answer(self, ctx: Any, gate: dict[str, Any], args: dict[str, Any], tool_call: Any,
                             user_input: Any) -> Any:
        call_id = getattr(tool_call, "id", "") or ""
        choice, answer = _classify(user_input, _DELETE_LABELS)
        self._save_gate(ctx, gate)
        if choice == "delete":
            return self.approve(new_args=self._confirmed_args(tool_call, args))
        if choice == "text":
            return self.reject(tool_result=_DELETE_REPLIED.format(answer=answer))
        if choice == "empty":
            title = _exhibit_title(args.get("exhibit_id")) or args.get("exhibit_id", "")
            return self._ask(ctx, gate, call_id, _delete_question(gate.get("language", "en"), title))
        return self.reject(tool_result=_KEPT)  # Keep it, Skip or Cancel: never delete by default

    def _after_format_answer(self, ctx: Any, gate: dict[str, Any], args: dict[str, Any], call_id: str,
                             user_input: Any) -> Any:
        choice, answer = _classify(user_input, _FORMAT_LABELS)
        if choice == "exhibit":
            gate["chose_exhibit"] = True
            self._save_gate(ctx, gate)
            return self.approve()
        if choice == "skip":
            self._save_gate(ctx, gate)
            return self.approve()  # "you decide": show the exhibit, but ask again next time
        if choice in ("cancel", "chat"):
            gate["declined_this_turn"] = True
            self._save_gate(ctx, gate)
            if choice == "cancel":
                return self.reject(tool_result=_CANCELLED)
            alternative = _chat_alternative(args)
            offered = f" (you offered: {alternative})" if alternative else ""
            return self.reject(tool_result=_CHOSE_CHAT.format(offered=offered))
        if choice == "text":
            gate["replied_this_turn"] = True
            self._save_gate(ctx, gate)
            return self.reject(tool_result=_FREE_TEXT.format(answer=answer))
        # Empty answer: ask again rather than guess.
        return self._ask(ctx, gate, call_id, _question(gate.get("language", "en"), _chat_alternative(args)))
