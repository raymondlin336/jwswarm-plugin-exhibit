"""Tests for the exhibit ask rail. Run with: python -m unittest discover -s plugin/tests"""

import asyncio
import importlib.util
import json
import sys
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
    def __init__(self, **args):
        self.arguments = json.dumps(args)
        self.id = "call-1"
        self.name = "exhibit"


SHOW_NEW = {"action": "show", "title": "Chart", "html": "<p>x</p>"}


class ExhibitAskRailTests(unittest.TestCase):
    def setUp(self):
        self.rail = MOD.ExhibitAskRail()
        self.session = FakeSession()

    def turn(self, query):
        asyncio.run(self.rail.before_invoke(FakeCtx(self.session, query)))

    def resolve(self, user_input=None, **args):
        call = FakeToolCall(**(args or SHOW_NEW))
        return asyncio.run(self.rail.resolve_interrupt(FakeCtx(self.session), call, user_input))

    def test_watches_only_the_exhibit_tool(self):
        self.assertEqual(self.rail.tool_names, {"exhibit"})

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
            decision = asyncio.run(self.rail.resolve_interrupt(ctx, call, {"a": "Exhibit"}))
            self.assertEqual(decision.kind, "approve")
            self.assertNotIn(key, ctx.extra)

    def test_other_calls_answers_are_left_alone(self):
        self.turn("chart this data")
        ctx = FakeCtx(self.session)
        carrier = types.SimpleNamespace(user_inputs={"call-1": {"a": "Exhibit"}, "call-2": {"ok": True}})
        ctx.extra = {MOD.RESUME_USER_INPUT_KEY: carrier}
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

    def test_mention_detection(self):
        self.assertTrue(MOD._mentions_exhibit("Show it as an Exhibit please"))
        self.assertTrue(MOD._mentions_exhibit("list my exhibits"))
        self.assertTrue(MOD._mentions_exhibit("做成展品"))
        self.assertFalse(MOD._mentions_exhibit("make a chart"))
        self.assertFalse(MOD._mentions_exhibit("exhibition hall"))


if __name__ == "__main__":
    unittest.main()
