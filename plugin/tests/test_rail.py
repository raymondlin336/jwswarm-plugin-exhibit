"""Tests for the exhibit ask rail. Run with: python -m unittest discover -s plugin/tests"""

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

RAIL_FILE = Path(__file__).parents[1] / "exhibit" / "rails" / "exhibit_ask_rail.py"


def _install_interrupt_stand_ins() -> None:
    """Minimal stand-ins for openjiuwen's interrupt rail classes."""

    class Decision:
        def __init__(self, kind, **fields):
            self.kind = kind
            self.__dict__.update(fields)

    class BaseInterruptRail:
        def __init__(self, tool_names=None):
            self.tool_names = set(tool_names or [])

        def approve(self, new_args=None):
            return Decision("approve", new_args=new_args)

        def reject(self, tool_result=None):
            return Decision("reject", tool_result=tool_result)

        def interrupt(self, request):
            return Decision("interrupt", request=request)

    class AskUserRequest:
        def __init__(self, **fields):
            self.__dict__.update(fields)

    class AskUserPayload:
        @classmethod
        def to_schema(cls):
            return {}

    modules = {
        "openjiuwen": types.ModuleType("openjiuwen"),
        "openjiuwen.harness": types.ModuleType("openjiuwen.harness"),
        "openjiuwen.harness.rails": types.ModuleType("openjiuwen.harness.rails"),
        "openjiuwen.harness.rails.interrupt": types.ModuleType("openjiuwen.harness.rails.interrupt"),
        "openjiuwen.harness.rails.interrupt.ask_user_rail": types.ModuleType("ask_user_rail"),
        "openjiuwen.harness.rails.interrupt.interrupt_base": types.ModuleType("interrupt_base"),
    }
    modules["openjiuwen.harness.rails.interrupt.ask_user_rail"].AskUserRequest = AskUserRequest
    modules["openjiuwen.harness.rails.interrupt.ask_user_rail"].AskUserPayload = AskUserPayload
    modules["openjiuwen.harness.rails.interrupt.interrupt_base"].BaseInterruptRail = BaseInterruptRail
    modules["openjiuwen.harness.rails.interrupt.interrupt_base"].InterruptDecision = Decision
    for name in ("openjiuwen.core", "openjiuwen.core.single_agent", "openjiuwen.core.single_agent.interrupt"):
        modules[name] = types.ModuleType(name)
    state = types.ModuleType("openjiuwen.core.single_agent.interrupt.state")
    state.RESUME_USER_INPUT_KEY = "_resume_user_input"
    modules["openjiuwen.core.single_agent.interrupt.state"] = state
    for name, module in modules.items():
        sys.modules.setdefault(name, module)
    for name in (
        "openjiuwen.harness.rails.interrupt.ask_user_rail",
        "openjiuwen.harness.rails.interrupt.interrupt_base",
        "openjiuwen.core.single_agent.interrupt.state",
    ):
        sys.modules[name] = modules[name]


def _load_module():
    try:
        importlib.import_module("openjiuwen.harness.rails.interrupt.interrupt_base")
    except Exception:  # noqa: BLE001 - no real openjiuwen here (or another test's stand-in)
        _install_interrupt_stand_ins()
    spec = importlib.util.spec_from_file_location("exhibit_ask_rail", RAIL_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load_module()


def _decision(raw):
    """Normalize a decision from the stand-ins or from the real openjiuwen classes."""
    kind = getattr(raw, "kind", None) or {
        "ApproveResult": "approve", "RejectResult": "reject", "InterruptResult": "interrupt",
    }[type(raw).__name__]
    return types.SimpleNamespace(
        kind=kind, request=getattr(raw, "request", None), tool_result=getattr(raw, "tool_result", None)
    )


class FakeSession:
    def __init__(self):
        self.state = {}

    def get_state(self, key=None):
        return self.state.get(key)

    def update_state(self, data):
        self.state.update(json.loads(json.dumps(data)))  # must be JSON-safe


class FakeCtx:
    def __init__(self, session, query=None):
        self.session = session
        self.inputs = types.SimpleNamespace(query=query)


class FakeToolCall:
    def __init__(self, _name="exhibit", _id="call-1", **args):
        self.arguments = json.dumps(args)
        self.id = _id
        self.name = _name


SHOW_NEW = {"action": "show", "title": "Chart", "html": "<p>x</p>"}


class ExhibitAskRailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_home = os.environ.get("EXHIBIT_HOME")
        os.environ["EXHIBIT_HOME"] = self.tmp.name
        self.addCleanup(self.restore_home)
        meta = Path(self.tmp.name, "exhibits", "budget-abc123", "meta.json")
        meta.parent.mkdir(parents=True)
        meta.write_text(json.dumps({"id": "budget-abc123", "title": "Monthly budget"}), encoding="utf-8")
        self.rail = MOD.ExhibitAskRail()
        self.session = FakeSession()
        self.call("skill_tool", skill_name="exhibit")  # most tests assume the skill was loaded

    def restore_home(self):
        if self.old_home is None:
            os.environ.pop("EXHIBIT_HOME", None)
        else:
            os.environ["EXHIBIT_HOME"] = self.old_home

    def turn(self, query):
        asyncio.run(self.rail.before_invoke(FakeCtx(self.session, query)))

    def mark_asked(self, call_id="call-1"):
        gate = dict(self.session.state.get(MOD._STATE_KEY) or {})
        gate["asked"] = call_id
        self.session.state[MOD._STATE_KEY] = gate

    def call(self, tool, user_input=None, **args):
        call = FakeToolCall(_name=tool, **args)
        return _decision(asyncio.run(self.rail.resolve_interrupt(FakeCtx(self.session), call, user_input)))

    def resolve(self, user_input=None, **args):
        if user_input is not None:
            self.mark_asked()  # an answer only counts for a call the rail asked about
        call = FakeToolCall(**(args or SHOW_NEW))
        return _decision(asyncio.run(self.rail.resolve_interrupt(FakeCtx(self.session), call, user_input)))

    def test_watches_exhibit_send_file_and_skill_tools(self):
        names = self.rail.get_tools() if hasattr(self.rail, "get_tools") else self.rail.tool_names
        self.assertEqual(set(names), {"exhibit", "send_file_to_user", "skill_tool"})

    def test_runs_before_the_permission_rail(self):
        # WorkSwarm's permission rail has priority 90 and denies any resume answer it finds.
        self.assertGreater(MOD.ExhibitAskRail.priority, 90)
        self.assertLess(MOD.ExhibitAskRail.priority, 95)

    def test_dialog_answer_is_consumed_so_later_rails_see_a_first_call(self):
        self.turn("chart this data")
        call = FakeToolCall(**SHOW_NEW)
        key = MOD.RESUME_USER_INPUT_KEY
        for carrier in (
            types.SimpleNamespace(user_inputs={"call-1": {"a": "Exhibit"}}),  # InteractiveInput shape
            {"call-1": {"a": "Exhibit"}},  # dict keyed by call id
            {"a": "Exhibit"},  # bare answer
        ):
            ctx = FakeCtx(self.session)
            ctx.extra = {key: carrier}
            self.mark_asked()
            decision = _decision(asyncio.run(self.rail.resolve_interrupt(ctx, call, {"a": "Exhibit"})))
            self.assertEqual(decision.kind, "approve")
            self.assertNotIn(key, ctx.extra)

    def test_other_calls_answers_are_left_alone(self):
        self.turn("chart this data")
        ctx = FakeCtx(self.session)
        carrier = types.SimpleNamespace(user_inputs={"call-1": {"a": "Exhibit"}, "call-2": {"ok": True}})
        ctx.extra = {MOD.RESUME_USER_INPUT_KEY: carrier}
        self.mark_asked()
        asyncio.run(self.rail.resolve_interrupt(ctx, FakeToolCall(**SHOW_NEW), {"a": "Exhibit"}))
        self.assertEqual(carrier.user_inputs, {"call-2": {"ok": True}})

    def test_vague_request_asks_with_two_options(self):
        self.turn("can you make me a chart of this benchmark")
        decision = self.resolve()
        self.assertEqual(decision.kind, "interrupt")
        (question,) = decision.request.questions
        self.assertEqual([o["label"] for o in question["options"]], ["Exhibit", "Answer in chat"])
        self.assertFalse(question["multi_select"])

    def test_agent_alternative_replaces_the_generic_chat_description(self):
        self.turn("chart this data")
        args = dict(SHOW_NEW, chat_alternative="A static bar chart image   of the scores")
        (question,) = self.resolve(**args).request.questions
        self.assertEqual(question["options"][1]["description"], "A static bar chart image of the scores")
        decision = self.resolve({"a": "Answer in chat"}, **args)
        self.assertIn("you offered: A static bar chart image of the scores", decision.tool_result)

    def test_generic_chat_description_is_used_without_an_alternative(self):
        self.turn("chart this data")
        (question,) = self.resolve().request.questions
        self.assertEqual(question["options"][1]["description"], MOD._TEXT["en"]["chat_desc"])
        decision = self.resolve({"a": "Answer in chat"})
        self.assertNotIn("you offered", decision.tool_result)

    def test_long_alternative_is_trimmed(self):
        self.turn("chart this data")
        (question,) = self.resolve(**dict(SHOW_NEW, chat_alternative="x" * 500)).request.questions
        self.assertLessEqual(len(question["options"][1]["description"]), MOD._MAX_ALTERNATIVE_CHARS)

    def test_mentioning_an_exhibit_skips_the_question(self):
        self.turn("Make me an exhibit of a budget planner")
        self.assertEqual(self.resolve().kind, "approve")

    def test_edits_and_other_actions_never_ask(self):
        self.turn("make the bars blue")
        self.assertEqual(self.resolve(action="show", exhibit_id="chart-abc123", html="<p>v2</p>").kind, "approve")
        for action in ("list", "read", "open", "delete", "stop"):
            self.assertEqual(self.resolve(action=action, exhibit_id="chart-abc123").kind, "approve")

    def test_choosing_exhibit_approves_and_is_remembered(self):
        self.turn("chart this data")
        self.assertEqual(self.resolve({"answers": {"Should I make this an exhibit or answer in chat?": "Exhibit"}}).kind, "approve")
        self.turn("now chart the other table")  # later turn in the same chat
        self.assertEqual(self.resolve().kind, "approve")

    def test_choosing_chat_rejects_and_blocks_retries_this_turn(self):
        self.turn("chart this data")
        decision = self.resolve({"q": "Answer in chat"})
        self.assertEqual(decision.kind, "reject")
        self.assertTrue(decision.tool_result.startswith("[USER_CHOSE_CHAT]"))
        retry = self.resolve()
        self.assertEqual(retry.kind, "reject")
        self.assertTrue(retry.tool_result.startswith("[USER_CHOSE_CHAT]"))
        self.turn("ok fine, chart something else")  # a new turn asks again
        self.assertEqual(self.resolve().kind, "interrupt")

    def test_free_text_answer_is_passed_on_and_next_call_goes_through(self):
        self.turn("chart this data")
        decision = self.resolve("yes but only the top 5 rows")
        self.assertEqual(decision.kind, "reject")
        self.assertIn("top 5 rows", decision.tool_result)
        self.assertTrue(decision.tool_result.startswith("[USER_REPLIED]"))
        self.assertEqual(self.resolve().kind, "approve")

    def test_skip_button_shows_the_exhibit_without_remembering(self):
        self.turn("chart this data")
        q = "Should I make this an exhibit or answer in chat?"
        self.assertEqual(self.resolve({"answers": {q: "用户已跳过此题，未选择任何选项。"}}).kind, "approve")
        self.turn("chart the other table")
        self.assertEqual(self.resolve().kind, "interrupt")  # Skip isn't a lasting choice

    def test_cancel_button_cancels_and_blocks_retries_this_turn(self):
        self.turn("chart this data")
        decision = self.resolve({"answers": {"q": "用户已取消本次问答，未作答。"}})
        self.assertEqual(decision.kind, "reject")
        self.assertTrue(decision.tool_result.startswith("[USER_CANCELLED]"))
        self.assertEqual(self.resolve().kind, "reject")

    def test_empty_answer_asks_again(self):
        self.turn("chart this data")
        self.assertEqual(self.resolve({"answers": {"q": "  "}}).kind, "interrupt")

    def test_chinese_request_gets_chinese_options(self):
        self.turn("帮我把这个基准测试做成图表")
        (question,) = self.resolve().request.questions
        self.assertEqual([o["label"] for o in question["options"]], ["展品", "在对话中回答"])
        self.assertEqual(self.resolve({"a": "展品"}).kind, "approve")

    def test_resume_turn_keeps_state(self):
        self.turn("chart this data")
        asyncio.run(self.rail.before_invoke(FakeCtx(self.session, query=object())))  # InteractiveInput on resume
        self.assertEqual(self.resolve().kind, "interrupt")

    def test_answers_to_questions_we_didnt_ask_are_left_alone(self):
        # e.g. a permission dialog's answer waiting for this call: not ours, so not consumed or used.
        self.turn("make an exhibit of this")
        ctx = FakeCtx(self.session)
        ctx.extra = {MOD.RESUME_USER_INPUT_KEY: {"call-1": {"approved": True}}}
        call = FakeToolCall(**SHOW_NEW)
        decision = _decision(asyncio.run(self.rail.resolve_interrupt(ctx, call, {"approved": True})))
        self.assertEqual(decision.kind, "approve")
        self.assertIn(MOD.RESUME_USER_INPUT_KEY, ctx.extra)

    # Delete confirmation ----------------------------------------------------
    def test_delete_always_asks_with_the_title(self):
        self.turn("delete my budget")
        for args in ({"exhibit_id": "budget-abc123"}, {"exhibit_id": "budget-abc123", "confirm": True}):
            decision = self.resolve(action="delete", **args)  # even if the agent passes confirm itself
            self.assertEqual(decision.kind, "interrupt")
            (question,) = decision.request.questions
            self.assertEqual(question["question"], "Delete \u201cMonthly budget\u201d?")
            self.assertEqual([o["label"] for o in question["options"]], ["Delete", "Keep it"])

    def test_choosing_delete_lets_it_run(self):
        self.turn("delete my budget")
        decision = self.resolve({"a": "Delete"}, action="delete", exhibit_id="budget-abc123")
        self.assertEqual(decision.kind, "approve")

    def test_confirm_is_written_into_the_call_itself(self):
        # WorkSwarm's StreamEventRail runs after ours and rebuilds tool_args from tool_call.arguments,
        # so confirm must be on the call, or the tool refuses the delete.
        self.turn("delete my budget")
        self.mark_asked()
        call = FakeToolCall(action="delete", exhibit_id="budget-abc123")
        decision = asyncio.run(self.rail.resolve_interrupt(FakeCtx(self.session), call, {"a": "Delete"}))
        self.assertEqual(_decision(decision).kind, "approve")
        self.assertIs(json.loads(call.arguments)["confirm"], True)
        if hasattr(decision, "new_args"):
            self.assertIs(json.loads(decision.new_args)["confirm"], True)

    def test_keep_skip_and_cancel_never_delete(self):
        self.turn("delete my budget")
        for answer in ("Keep it", "用户已跳过此题，未选择任何选项。", "用户已取消本次问答，未作答。"):
            decision = self.resolve({"a": answer}, action="delete", exhibit_id="budget-abc123")
            self.assertEqual(decision.kind, "reject")
            self.assertTrue(decision.tool_result.startswith("[USER_KEPT]"))
        replied = self.resolve("actually rename it instead", action="delete", exhibit_id="budget-abc123")
        self.assertTrue(replied.tool_result.startswith("[USER_REPLIED]"))
        self.assertIn("rename it instead", replied.tool_result)

    def test_deleting_a_missing_exhibit_passes_through(self):
        self.assertEqual(self.resolve(action="delete", exhibit_id="nope-000000").kind, "approve")

    # Scripted HTML sent to the preview panel ---------------------------------
    def write(self, name, text):
        path = Path(self.tmp.name, name)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_scripted_html_is_sent_back_once_per_turn(self):
        self.turn("chart this data")
        chart = self.write("chart.html", '<html><script src="chart.js"></script></html>')
        first = self.call("send_file_to_user", abs_file_path_list=chart)
        self.assertEqual(first.kind, "reject")
        self.assertTrue(first.tool_result.startswith("[USE_EXHIBIT]"))
        self.assertIn("chart.html", first.tool_result)
        self.assertEqual(self.call("send_file_to_user", abs_file_path_list=[chart]).kind, "approve")  # on purpose
        self.turn("send it again")
        self.assertEqual(self.call("send_file_to_user", abs_file_path_list=[chart]).kind, "reject")  # new turn

    def test_other_files_pass_through(self):
        self.turn("send me the report")
        static = self.write("static.html", "<html><body><h1>No scripts</h1></body></html>")
        image = self.write("chart.png", "<script>not really html</script>")
        self.assertEqual(self.call("send_file_to_user", abs_file_path_list=[static, image]).kind, "approve")
        self.assertEqual(self.call("send_file_to_user", abs_file_path_list=["C:/missing.html"]).kind, "approve")

    # Skill before show --------------------------------------------------------
    def test_show_waits_for_the_skill(self):
        self.session = FakeSession()  # a fresh chat: skill not loaded yet
        self.turn("make an exhibit of this")
        decision = self.resolve()
        self.assertEqual(decision.kind, "reject")
        self.assertTrue(decision.tool_result.startswith("[LOAD_SKILL]"))
        for action in ("list", "gallery", "read", "open"):
            self.assertEqual(self.resolve(action=action, exhibit_id="budget-abc123").kind, "approve")
        self.call("skill_tool", skill_name="some-other-skill")
        self.assertEqual(self.resolve().kind, "reject")
        self.call("skill_tool", skill_name="exhibit")
        self.assertEqual(self.resolve().kind, "approve")

    # Loop guard -------------------------------------------------------------
    def tool_finished(self, result, **args):
        ctx = FakeCtx(self.session)
        ctx.inputs = types.SimpleNamespace(tool_name="exhibit", tool_result=result, tool_args=json.dumps(args),
                                           tool_call=FakeToolCall(**args))
        asyncio.run(self.rail.after_tool_call(ctx))

    def test_identical_failures_are_stopped_after_three(self):
        self.turn("make an exhibit deck of this repo")
        no_html = {"action": "show", "title": "Deck", "summary": "Five slides"}
        failure = {"success": False, "error_code": "missing_html", "error": "No page was sent."}
        for _ in range(3):
            self.assertEqual(self.resolve(**no_html).kind, "approve")
            self.tool_finished(failure, **no_html)
        stopped = self.resolve(**no_html)
        self.assertEqual(stopped.kind, "reject")
        self.assertTrue(stopped.tool_result.startswith("[STOP_RETRYING]"))
        self.assertIn("3 times", stopped.tool_result)
        self.assertIn("No page was sent.", stopped.tool_result)
        fixed = dict(no_html, html_file="C:/work/deck.html")  # a changed call is allowed through
        self.assertEqual(self.resolve(**fixed).kind, "approve")
        self.turn("try again")  # a new turn starts the count over
        self.assertEqual(self.resolve(**no_html).kind, "approve")

    def test_success_clears_the_count_and_other_results_are_ignored(self):
        self.turn("make an exhibit")
        args = {"action": "show", "title": "Deck"}
        failure = str({"success": False, "error_code": "missing_html", "error": "x"})  # as WorkSwarm logs it
        self.tool_finished(failure, **args)
        self.tool_finished(failure, **args)
        self.tool_finished("[USER_CHOSE_CHAT] not a tool result", **args)  # a rail message: ignored
        self.tool_finished({"success": True, "exhibit_id": "deck-1"}, action="show", title="Other")
        self.tool_finished(failure, **args)
        self.assertEqual(self.resolve(**args).kind, "approve")  # 1 since the success, not 3

    def test_explicit_mention_counts_for_the_whole_chat(self):
        self.turn("make me a deck about this repo, with exhibit")
        self.assertEqual(self.resolve().kind, "approve")
        self.turn("what?")  # a follow-up without the word
        self.assertEqual(self.resolve().kind, "approve")

    def test_mention_detection(self):
        self.assertTrue(MOD._mentions_exhibit("Show it as an Exhibit please"))
        self.assertTrue(MOD._mentions_exhibit("list my exhibits"))
        self.assertTrue(MOD._mentions_exhibit("做成展品"))
        self.assertFalse(MOD._mentions_exhibit("make a chart"))
        self.assertFalse(MOD._mentions_exhibit("exhibition hall"))


if __name__ == "__main__":
    unittest.main()
