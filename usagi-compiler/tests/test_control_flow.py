import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from usagi.compiler import CompileError, compile_source, lex
from usagi.toolchain import ToolchainError, build, find_clang


ROOT = Path(__file__).resolve().parents[1]


def program(body):
    return f"우사기!\n{body}\n!우사기\n"


def output(value):
    return f"우~라~ {value} 야하!"


class ControlFlowFrontendTests(unittest.TestCase):
    def test_distinct_control_keywords_and_input_token(self):
        tokens = lex("갸웃? 갸웃! 야호! 하아... 우우... 우쨔? 우쨔! 뿌야! 푸루룻! 푸루룻? 삐익! 휙! 하아?")
        self.assertEqual([t.kind for t in tokens[:-1]],
                         ["SIGN", "SIGN_END", "POSITIVE", "ZERO", "NEGATIVE", "COUNT", "COUNT_END", "REMAINING", "REPEAT", "REPEAT_TEST", "BREAK", "CONTINUE", "INPUT"])

    def test_control_tokens_delimit_names_and_are_literal_inside_strings(self):
        tokens = lex("하치와레: 결과 값 갸웃? 뿌 하아... 갸웃!")
        self.assertEqual((tokens[0].kind, tokens[0].text), ("NAME", "결과 값"))
        self.assertEqual(lex("하치! 갸웃? 우쨔! 휙! 뿌야! 와레!")[0].kind, "TEXT")

    def test_missing_mismatched_and_stray_delimiters(self):
        fixtures = ["갸웃? 뿌 야호!", "우쨔? 뿌르", "푸루룻!", "갸웃? 뿌 야호! 우쨔!",
                    "우쨔? 뿌르 갸웃!", "야호!", "하아...", "우우...", "우쨔!", "푸루룻? 뿌",
                    "우랏! 우쨔? 뿌르 우라랏!", "우쨔? 뿌르 우랏! 우쨔!",
                    "푸루룻! 갸웃? 뿌 야호! 푸루룻? 뿌"]
        for body in fixtures:
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_source(program(body))

    def test_reactions_require_at_least_one_and_cannot_repeat(self):
        for body in ("갸웃? 뿌 갸웃!", "갸웃? 뿌 야호! 야호! 갸웃!", "갸웃? 뿌 하아... 하아... 갸웃!"):
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_source(program(body))
        compile_source(program("갸웃? 뿌 우우... 야호! 하아... 갸웃!"))

    def test_conditions_must_be_numeric_and_count_must_be_integer(self):
        for body in ("갸웃? 하치! a 와레! 야호! 갸웃!", "푸루룻! 푸루룻? 하치! a 와레!",
                     "우쨔? 하치! a 와레! 우쨔!", "우쨔? 뿌르.뿌 우쨔!"):
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_source(program(body))

    def test_break_and_continue_require_an_enclosing_loop_in_same_function(self):
        for body in ("삐익! 야하!", "휙! 야하!", "갸웃? 뿌 야호! 삐익! 야하! 갸웃!"):
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, "반복문 안"):
                compile_source(program(body))
        source = "우나! 하치와레: 탈출 삐익! 야하! 우~나! 뿌\n" + program("우쨔? 뿌르 하치와레: 탈출 우라! 우라라! 야하! 우쨔!")
        with self.assertRaisesRegex(CompileError, "반복문 안"):
            compile_source(source)

    def test_remaining_requires_lexically_enclosing_counted_loop(self):
        for body in (output("뿌야!"), "푸루룻! " + output("뿌야!") + " 푸루룻? 뿌", "우쨔? 뿌야! 우쨔!"):
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, r"우쨔\?"):
                compile_source(program(body))
        source = "우나! 하치와레: 횟수 우~나! 뿌야!\n" + program("우쨔? 뿌르 " + output("하치와레: 횟수 우라! 우라라!") + " 우쨔!")
        with self.assertRaisesRegex(CompileError, r"우쨔\?"):
            compile_source(source)

    def test_remaining_is_read_only(self):
        for body in ("뿌야! 야~하! 뿌 야하!", "하아? 뿌야! 야하!", "얏! 뿌야! 뿌 야하!"):
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_source(program("우쨔? 뿌르 " + body + " 우쨔!"))

    def test_branch_and_loop_local_declarations_do_not_escape(self):
        for body in ("갸웃? 뿌 야호! 얏! 야 뿌 야하! 갸웃! " + output("야"),
                     "우쨔? 뿌르 얏! 야 뿌 야하! 우쨔! " + output("야"),
                     "푸루룻! 얏! 야 뿌 야하! 푸루룻? 뿌 " + output("야")):
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, "선언되지 않은 변수"):
                compile_source(program(body))
        compile_source(program("갸웃? 뿌 야호! 얏! 야 뿌 야하! 하아... 얏! 야 뿌 야하! 갸웃!"))

    def test_repeat_condition_uses_outer_scope_and_cannot_read_body_local(self):
        with self.assertRaisesRegex(CompileError, "선언되지 않은 변수"):
            compile_source(program("푸루룻! 얏! 야 뿌 야하! 푸루룻? 야"))
        compile_source(program("얏! 야 뿌 야하! 푸루룻! 얏! 야 뿌르 야하! 푸루룻? 야"))

    def test_control_flow_cannot_close_function_early(self):
        with self.assertRaisesRegex(CompileError, "갸웃!"):
            compile_source("우나! 하치와레: 값 갸웃? 뿌 야호! 우~나! 뿌\n" + program(""))

    def test_errors_keep_original_line_and_column(self):
        source = "우사기!\n    우쨔? 뿌르.뿌\n    우쨔!\n!우사기\n"
        try:
            compile_source(source)
        except CompileError as error:
            self.assertEqual((error.token.line, error.token.column), (2, 9))
        else:
            self.fail("real repetition count must be rejected")


class ControlFlowNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.cc = find_clang()
        except ToolchainError as error:
            raise unittest.SkipTest(str(error))
        cls.temporary = tempfile.TemporaryDirectory(prefix="usagi-control-tests-")
        cls.root = Path(cls.temporary.name)
        cls.binaries = {}
        fixtures = {name: (ROOT / "examples" / f"{name}.usagi").read_text(encoding="utf-8")
                    for name in ("three_reactions", "countdown", "repeat_input", "skip_and_stop")}
        fixtures["count_input"] = program("얏! 야 뿌 야하! 냠? 야 야하! 우쨔? 야 " + output("뿌야!") + " 우쨔!")
        fixtures["sign_real"] = program("핫! 야 뿌 야하! 냠? 야 야하! 갸웃? 야 우우... " + output("릇뿌뿌르") + " 하아... " + output("뿌") + " 야호! " + output("뿌르") + " 갸웃!")
        fixtures["partial"] = program("얏! 야 뿌 야하! 냠? 야 야하! 갸웃? 야 야호! " + output("뿌르") + " 갸웃! " + output("뿌르르"))
        fixtures["snapshot"] = program("얏! 야 뿌르르르 야하! 우쨔? 야 야 야~하! 뿌 야하! " + output("뿌야!") + " 우쨔! " + output("야"))
        fixtures["nested"] = program("우쨔? 뿌르르 " + output("뿌야!") + " 우쨔? 뿌야! " + output("뿌야!") + " 우쨔! " + output("뿌야!") + " 우쨔!")
        fixtures["repeat_once"] = program("푸루룻! " + output("뿌르") + " 푸루룻? 뿌")
        fixtures["repeat_continue"] = program("얏! 야 뿌르르르 야하! 푸루룻! 야 야~하! 야 하아! 뿌르 야하! " + output("야") + " 휙! 야하! " + output("뿌릇") + " 푸루룻? 야")
        fixtures["repeat_break"] = program("푸루룻! " + output("뿌르") + " 삐익! 야하! 푸루룻? 뿌르 푸루! 뿌")
        fixtures["inner_break"] = program("우쨔? 뿌르르 우쨔? 뿌르르르 " + output("뿌야!") + " 삐익! 야하! 우쨔! " + output("뿌야!") + " 우쨔!")
        fixtures["nested_sign"] = program("갸웃? 뿌 야호! " + output("뿌릇") + " 하아... 갸웃? 릇뿌뿌르 우우... " + output("뿌르르") + " 갸웃! " + output("뿌르르르") + " 우우... " + output("뿌릇") + " 갸웃!")
        fixtures["scope"] = program("얏! 야 뿌릇 야하! 우쨔? 뿌르르 얏! 야 뿌르 야하! " + output("야") + " 우쨔! 갸웃? 뿌 하아... 얏! 야 뿌르르 야하! " + output("야") + " 갸웃! " + output("야"))
        reader = "우나! 하치와레: 읽기 얏! 야 뿌 야하! 냠? 야 야하! 우~나! 야\n"
        fixtures["sign_once"] = reader + program("갸웃? 하치와레: 읽기 우라! 우라라! 야호! " + output("뿌르") + " 하아... " + output("뿌") + " 우우... " + output("릇뿌뿌르") + " 갸웃! " + output("하치와레: 읽기 우라! 우라라!"))
        fixtures["repeat_retest"] = reader + program("푸루룻! " + output("뿌르") + " 휙! 야하! 푸루룻? 하치와레: 읽기 우라! 우라라!")
        fixtures["count_once"] = reader + program("우쨔? 하치와레: 읽기 우라! 우라라! " + output("뿌야!") + " 우쨔! " + output("하치와레: 읽기 우라! 우라라!"))
        fixtures["mixed_remaining"] = program("우쨔? 뿌르르 푸루룻! " + output("뿌야!") + " 푸루룻? 뿌 우쨔!")
        fixtures["repeat_shadow"] = program("얏! 야 뿌 야하! 푸루룻! 얏! 야 뿌르 야하! " + output("야") + " 푸루룻? 야")
        fixtures["counter_math"] = program("우쨔? 뿌르르 " + output("뿌야! 하핫! 뿌르르") + " 우쨔!")
        fixtures["function_control"] = ("우나! 하치와레: 합계 얏! 야 뿌 야하! 우쨔? 뿌르르르 야 야~하! 야 하! 뿌야! 야하! 우쨔! 우~나! 야\n" + program(output("하치와레: 합계 우라! 우라라!")))
        fixtures["mixed_continue"] = program("우쨔? 뿌르르 얏! 야 뿌르르 야하! 푸루룻! 야 야~하! 야 하아! 뿌르 야하! 우쨔? 뿌르 휙! 야하! 우쨔! " + output("야") + " 푸루룻? 야 우쨔!")
        cls.fixture_count = len(fixtures)
        try:
            for name, source in fixtures.items():
                output_path = cls.root / (name + (".exe" if os.name == "nt" else ""))
                cls.binaries[name] = build(compile_source(source, "제어문 테스트.usagi"), output_path, cls.cc)
        except Exception:
            cls.temporary.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_program(self, name, input_text=""):
        return subprocess.run([str(self.binaries[name])], input=input_text, capture_output=True,
                              encoding="utf-8", timeout=5)

    def assert_output(self, name, expected, input_text=""):
        result = self.run_program(name, input_text)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ""))

    def test_three_reactions(self):
        for value, expected in ((6, "다섯보다 많아!"), (5, "정확히 다섯!"), (4, "다섯보다 적어!")):
            self.assert_output("three_reactions", expected + "\n", str(value) + "\n")

    def test_real_conditions_including_negative_zero(self):
        for value, expected in (("0.5", "1"), ("-0.5", "-1"), ("-0.0", "0")):
            self.assert_output("sign_real", expected + "\n", value + "\n")

    def test_missing_reaction_skips_without_fallthrough(self):
        self.assert_output("partial", "2\n", "0\n")
        self.assert_output("partial", "2\n", "-1\n")
        self.assert_output("partial", "1\n2\n", "1\n")
        self.assert_output("nested_sign", "2\n3\n")

    def test_countdown_and_zero_count(self):
        self.assert_output("countdown", "3\n2\n1\n")
        self.assert_output("count_input", "", "0\n")
        self.assert_output("counter_math", "4\n2\n")

    def test_count_is_evaluated_once(self):
        self.assert_output("snapshot", "3\n2\n1\n0\n")
        self.assert_output("count_once", "2\n1\n7\n", "2\n7\n")

    def test_negative_count_is_a_source_located_runtime_error(self):
        for value in ("-1", "-9223372036854775808"):
            result = self.run_program("count_input", value + "\n")
            self.assertEqual(result.returncode, 2)
            self.assertIn("negative repetition count", result.stderr)
            self.assertIn("제어문 테스트.usagi:", result.stderr)

    def test_remaining_tracks_innermost_count_and_restores_outer(self):
        self.assert_output("nested", "2\n2\n1\n2\n1\n1\n1\n")
        self.assert_output("mixed_remaining", "2\n1\n")

    def test_repeat_executes_once_and_rechecks_tail(self):
        self.assert_output("repeat_once", "1\n")
        self.assert_output("repeat_input", "2\n1\n0\n", "2\n1\n0\n")
        self.assert_output("repeat_input", "-1\n", "-1\n")
        self.assert_output("repeat_retest", "1\n1\n1\n", "2\n1\n0\n")

    def test_continue_in_repeat_still_evaluates_tail_condition(self):
        self.assert_output("repeat_continue", "2\n1\n0\n")

    def test_break_skips_tail_evaluation(self):
        self.assert_output("repeat_break", "1\n")

    def test_break_and_continue_apply_to_innermost_loop(self):
        self.assert_output("skip_and_stop", "5\n4\n2\n")
        self.assert_output("inner_break", "3\n2\n3\n1\n")
        self.assert_output("mixed_continue", "1\n0\n1\n0\n")

    def test_branch_and_iteration_scopes(self):
        self.assert_output("scope", "1\n1\n2\n5\n")
        self.assert_output("repeat_shadow", "1\n")

    def test_function_can_use_control_flow_and_return_afterward(self):
        self.assert_output("function_control", "6\n")

    def test_sign_expression_is_evaluated_once(self):
        self.assert_output("sign_once", "1\n7\n", "1\n7\n")


if __name__ == "__main__":
    unittest.main()
