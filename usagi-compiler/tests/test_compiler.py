import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from usagi.cli import main
from usagi.compiler import CompileError, compile_source, lex
from usagi.numbers import INTEGERS, decode_number, encode_integer
from usagi.toolchain import ToolchainError, build, find_clang


ROOT = Path(__file__).resolve().parents[1]
MIN = -(2**63)
MAX = 2**63 - 1


def program(body: str) -> str:
    return f"우사기!\n{body}\n!우사기\n"


class NumberTests(unittest.TestCase):
    def test_known_integer_literals(self):
        fixtures = {
            "뿌": 0, "뿌르": 1, "뿌르르르르": 4, "뿌릇": 5,
            "뿌릇뿌르": 6, "뿌릇뿌르르르르": 9,
            "뿌릇뿌릇": 10, "뿌르뿌릇뿌릇~뿌르": 11,
            "뿌르르뿌릇뿌릇": 20, "뿌릇뿌릇뿌릇": 50,
            "뿌릇뿌릇뿌릇~뿌릇": 55, "뿌르뿌르릇": 100,
            "뿌르뿌르릇~뿌르뿌릇뿌릇": 110,
            "뿌르뿌르릇~뿌르르뿌릇뿌릇~뿌르르르": 123,
            "뿌르르뿌르릇": 200,
            "뿌릇뿌르르르르뿌르릇~뿌릇뿌르르르르뿌릇뿌릇~뿌릇뿌르르르르": 999,
        }
        for token, expected in fixtures.items():
            with self.subTest(token=token):
                self.assertEqual(decode_number(token), ("int", str(expected)))
                self.assertEqual(decode_number("릇뿌" + token), ("int", "-" + str(expected)))

    def test_all_place_boundary_combinations(self):
        spellings = (
            "뿌르뿌르릇~뿌르르뿌릇뿌릇~뿌르르르",
            "뿌르뿌르릇뿌르르뿌릇뿌릇~뿌르르르",
            "뿌르뿌르릇~뿌르르뿌릇뿌릇뿌르르르",
            "뿌르뿌르릇뿌르르뿌릇뿌릇뿌르르르",
        )
        for text in spellings:
            self.assertEqual(decode_number(text), ("int", "123"))

    def test_entire_finite_vocabulary_is_unambiguous(self):
        self.assertEqual(len(INTEGERS), 3430)
        self.assertEqual(set(INTEGERS.values()), set(range(1000)))
        for text, value in INTEGERS.items():
            self.assertEqual(decode_number(text.replace("~", "")), ("int", str(value)))
        for value in range(-999, 1000):
            self.assertEqual(decode_number(encode_integer(value)), ("int", str(value)))

    def test_decimal_and_negative_zero(self):
        for text, expected in (
            ("뿌.뿌릇", "0.5"), ("뿌르르르.뿌르르", "3.2"),
            ("뿌르르뿌릇뿌릇.뿌릇", "20.5"),
            ("릇뿌뿌.뿌릇", "-0.5"), ("릇뿌뿌.뿌", "-0.0"),
        ):
            self.assertEqual(decode_number(text), ("real", expected))

    def test_malformed_number_rejected(self):
        for text in (
            "~뿌르", "뿌르~", "뿌르~~뿌르", "뿌르~뿌르릇", "뿌르르르르르",
            "뿌릇뿌릇뿌르", "릇뿌~뿌르", "릇뿌릇뿌뿌르", "뿌르릇",
            "뿌.뿌뿌릇", "뿌..뿌릇", "뿌.", ".뿌", "뿌.뿌릇뿌릇",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                decode_number(text)


class FrontendTests(unittest.TestCase):
    def assert_error(self, body: str, message: str):
        with self.assertRaisesRegex(CompileError, message):
            compile_source(program(body))

    def test_distinct_keywords(self):
        tokens = lex("하아? 하아! 핫! 하핫! 야하! 야~하! 우랏! 우라! 우라랏! 우라라!")
        self.assertEqual([x.kind for x in tokens[:-1]],
                         ["INPUT", "SUB", "REAL", "MUL", "END", "ASSIGN", "OPEN", "LPAREN", "CLOSE", "RPAREN"])

    def test_minimal_program_and_legacy_rejection(self):
        self.assertIn("return 0;", compile_source("우사기!\n!우사기"))
        with self.assertRaisesRegex(CompileError, "메인은 우사기!"):
            compile_source("우나!\n우~나! 야하!")

    def test_statement_terminator_required(self):
        self.assert_error("우~라~ 뿌", "야하!")

    def test_braces_and_parentheses_distinct(self):
        self.assert_error("우~라~ 우랏! 뿌 우라랏! 야하!", "식이 필요")
        with self.assertRaisesRegex(CompileError, "우라랏!"):
            compile_source("우사기! 우랏! !우사기")
        self.assert_error("우~라~ 우라! 뿌 야하!", "우라라!")

    def test_undefined_and_out_of_scope_variables(self):
        self.assert_error("하아? 하치와레: 야 야하!", "선언되지")
        self.assert_error("하치와레: 야 야~하! 뿌 야하!", "선언되지")
        self.assert_error("우랏! 얏! 하치와레: 야 뿌 야하! 우라랏! 우~라~ 하치와레: 야 야하!", "선언되지")
        self.assert_error("얏! 하치와레: 야 하치와레: 야 하! 뿌르 야하!", "선언되지")

    def test_duplicate_declaration(self):
        self.assert_error("얏! 하치와레: 야 뿌 야하! 얏! 하치와레: 야 뿌르 야하!", "중복 선언")

    def test_invalid_types(self):
        self.assert_error("우~라~ 뿌.뿌릇 푸루루! 뿌르 야하!", "정수끼리")

    def test_unsupported_types(self):
        self.assert_error("얏핫! 하치와레: 야 뿌 야하!", "문자형")
        self.assert_error("얏하핫! 하치와레: 야 뿌 야하!", "하치와레!로 바뀌")

    def test_missing_entry_return_and_extra_code(self):
        for source, expected in (
            ("", "우사기!"), ("우사기!", "!우사기"),
            (program("") + "우~라~ 뿌 야하!", "최상위"),
        ):
            with self.assertRaisesRegex(CompileError, expected):
                compile_source(source)

    def test_diagnostic_location(self):
        source = "우사기!\n\n    우~라~ 하치와레: 야 야하!\n!우사기"
        try:
            compile_source(source, "example.usagi")
        except CompileError as error:
            self.assertEqual((error.token.line, error.token.column), (3, 10))
            self.assertIn("example.usagi:3:10", error.format("example.usagi", source))
        else:
            self.fail("expected undeclared variable diagnostic")

    def test_unknown_or_joined_token(self):
        self.assert_error("우~라~ 1 야하!", "알 수 없는 토큰")
        self.assert_error("우~라~ 뿌야하!", "공백")

    def test_truncated_expression(self):
        with self.assertRaises(CompileError):
            compile_source("우사기! 우~라~")

    def test_deep_expression_is_clean_error(self):
        self.assert_error("우~라~ " + "우라! " * 1500 + "뿌 " + "우라라! " * 1500 + "야하!", "너무 깊게")


class FunctionTests(unittest.TestCase):
    def test_function_delimiters_and_inferred_return_types(self):
        source = "우나! 하치와레: 정수 우~나! 뿌르\n우나! 하치와레: real 우~나! 뿌.뿌릇 야하!\n" + program("")
        generated = compile_source(source)
        self.assertIn("int64_t us_f1(void)", generated)
        self.assertIn("double us_f2(void)", generated)

    def test_forward_call_and_variable_based_return_type(self):
        source = program("우~라~ 하치와레: 첫함수 우라! 우라라! 야하!")
        source += "우나! 하치와레: 첫함수 우~나! 하치와레: 나중함수 우라! 우라라!\n"
        source += "우나! 하치와레: 나중함수 얏! 하치와레: 야 뿌.뿌릇 야하! 우~나! 하치와레: 야"
        generated = compile_source(source)
        self.assertIn("int64_t us_f1(void)", generated)
        self.assertIn("int64_t us_f2(void)", generated)

    def test_duplicate_main_and_function(self):
        for source, message in (
            (program("") + program(""), "하나만"),
            ("우나! 하치와레: 같은이름 우~나! 뿌 우나! 하치와레: 같은이름 우~나! 뿌 " + program(""), "중복 선언"),
        ):
            with self.assertRaisesRegex(CompileError, message):
                compile_source(source)

    def test_undefined_function_and_missing_call_parentheses(self):
        for body, message in (("우~라~ 하치와레: missing 우라! 우라라! 야하!", "선언되지 않은 함수"),
                              ("우~라~ 하치와레: missing 야하!", "선언되지 않은 변수")):
            with self.assertRaisesRegex(CompileError, message):
                compile_source(program(body))

    def test_recursion_and_mutual_recursion_are_diagnosed(self):
        for functions in ("우나! 하치와레: 재귀 우~나! 하치와레: 재귀 우라! 우라라!",
                          "우나! 하치와레: 첫째 우~나! 하치와레: 둘째 우라! 우라라! 우나! 하치와레: 둘째 우~나! 하치와레: 첫째 우라! 우라라!"):
            with self.assertRaisesRegex(CompileError, "순환"):
                compile_source(functions + "\n" + program(""))

    def test_functions_have_independent_scopes(self):
        source = "우나! 하치와레: 바깥참조 우~나! 하치와레: 야\n" + program("얏! 하치와레: 야 뿌르 야하!")
        with self.assertRaisesRegex(CompileError, "선언되지 않은 변수"):
            compile_source(source)
        source = "우나! 하치와레: 첫째 얏! 하치와레: 야 뿌르 야하! 우~나! 하치와레: 야\n우나! 하치와레: 둘째 우~나! 하치와레: 야\n" + program("")
        with self.assertRaisesRegex(CompileError, "선언되지 않은 변수"):
            compile_source(source)

    def test_missing_mismatched_and_nested_function_endings(self):
        fixtures = (
            "우나! 하치와레: 함수 우사기! !우사기",
            "우나! 하치와레: 함수 우~나! 우사기! !우사기",
            "우사기! 우~나! 뿌",
            "우사기! 우나! 하치와레: 내부 우~나! 뿌 !우사기",
            "우나! 하치와레: 함수 우랏! 우~나! 뿌 우라랏! 우사기! !우사기",
        )
        for source in fixtures:
            with self.subTest(source=source), self.assertRaises(CompileError):
                compile_source(source)

    def test_function_arguments_and_numeric_names_rejected(self):
        with self.assertRaisesRegex(CompileError, "냠!"):
            compile_source("우나! 하치와레: 함수 우~나! 뿌\n" + program("하치와레: 함수 우라! 뿌 우라라! 야하!"))
        with self.assertRaisesRegex(CompileError, "함수명"):
            compile_source("우나! 뿌 우~나! 뿌\n" + program(""))

    def test_conversion_generated_for_declaration_and_assignment(self):
        source = program("얏! 하치와레: 야 뿌.뿌릇 야하! 하치와레: 야 야~하! 뿌르.뿌릇 야하!")
        generated = compile_source(source)
        self.assertEqual(generated.count("= us_real_to_int("), 2)


class NameAndStringTests(unittest.TestCase):
    def test_multiword_name_and_whitespace_normalization(self):
        tokens = lex("하치와레: 숫자   만들기 우라! 우라라!")
        self.assertEqual((tokens[0].kind, tokens[0].text), ("NAME", "숫자 만들기"))
        source = "우나! 하치와레: 숫자\t만들기 우~나! 뿌르\n" + program(
            "얏! 하치와레: 내 결과 하치와레: 숫자 만들기 우라! 우라라! 야하!\n우~라~ 하치와레: 내  결과 야하!")
        compile_source(source)

    def test_missing_prefix_rejected_at_every_use(self):
        for source in ("우나! 만들기 우~나! 뿌\n" + program(""),
                       program("얏! 결과 뿌 야하!"),
                       program("얏! 하치와레: 값 뿌 야하! 우~라~ 값 야하!"),
                       "우나! 하치와레: 만들기 우~나! 뿌\n" + program("만들기 우라! 우라라! 야하!")):
            with self.subTest(source=source), self.assertRaisesRegex(CompileError, "하치와레:"):
                compile_source(source)

    def test_empty_reserved_or_invalid_name(self):
        for text in ("하치와레:", "하치와레: \n이름", "하치와레: 뿌", "하치와레: 123", "하치와레: a-b"):
            with self.subTest(text=text), self.assertRaises(CompileError):
                lex(text)

    def test_short_variable_names_are_exact_ya_repetitions(self):
        tokens = lex("야 야야 야야야 야야야야")
        self.assertEqual([t.kind for t in tokens[:-1]], ["SHORT_NAME"] * 4)
        for name in ("야값", "야야2", "야_", "야아"):
            with self.subTest(name=name), self.assertRaisesRegex(CompileError, "하치와레:"):
                compile_source(program(f"얏! {name} 뿌 야하!"))

    def test_short_variable_and_prefixed_form_are_the_same_binding(self):
        compile_source(program("얏! 야 뿌 야하! 하치와레: 야 야~하! 뿌르 야하! 우~라~ 야 야하!"))
        for body in ("얏! 야 뿌 야하! 얏! 하치와레: 야 뿌 야하!",
                     "얏! 하치와레: 야 뿌 야하! 얏! 야 뿌 야하!"):
            with self.assertRaisesRegex(CompileError, "중복 선언"):
                compile_source(program(body))

    def test_short_name_exception_does_not_apply_to_functions(self):
        for source in ("우나! 야 우~나! 뿌\n" + program(""),
                       "우나! 하치와레: 야 우~나! 뿌\n" + program("우~라~ 야 우라! 우라라! 야하!"),
                       program("야 우라! 우라라! 야하!")):
            with self.subTest(source=source), self.assertRaisesRegex(CompileError, "하치와레:"):
                compile_source(source)

    def test_short_name_delimits_a_custom_name(self):
        tokens = lex("하치와레: 결과 값 야 하! 야야")
        self.assertEqual([(t.kind, t.text) for t in tokens[:-1]],
                         [("NAME", "결과 값"), ("SHORT_NAME", "야"), ("ADD", "하!"), ("SHORT_NAME", "야야")])
        compile_source(program("얏! 야 뿌르 야하! 얏! 하치와레: 결과 값 야 하! 뿌르 야하!"))

    def test_name_boundaries_and_collisions(self):
        tokens = lex("하치와레: 첫 이름 하치와레: 둘 이름 뿌르 하! 하치와레: 셋 이름\n하치와레: 넷 이름")
        self.assertEqual([t.text for t in tokens if t.kind == "NAME"], ["첫 이름", "둘 이름", "셋 이름", "넷 이름"])
        with self.assertRaisesRegex(CompileError, "중복 선언"):
            compile_source(program("얏! 하치와레: 내 값 뿌 야하! 얏! 하치와레: 내  값 뿌 야하!"))

    def test_string_padding_empty_and_embedded_language_tokens(self):
        fixtures = {"하치! 안녕 😀 와레!": "안녕 😀", "하치!와레!": "", "하치! 와레!": "",
                    "하치!  앞뒤  와레!": " 앞뒤 ", "하치!야하! !우사기 하치와레: 와레!": "야하! !우사기 하치와레:"}
        for text, expected in fixtures.items():
            self.assertEqual(lex(text)[0].text, expected)

    def test_unclosed_stray_multiline_and_joined_strings(self):
        for text in ("하치! 닫힘 없음", "와레!", "하치! 첫줄\n둘째 와레!", "하치! 글 와레!야하!"):
            with self.subTest(text=text), self.assertRaises(CompileError):
                lex(text)

    def test_string_limits_and_nul(self):
        self.assertEqual(len(lex("하치!" + "a" * 4095 + "와레!")[0].text), 4095)
        for content in ("a" * 4096, "가" * 1366, "a\0b"):
            with self.assertRaisesRegex(CompileError, "4095바이트"):
                lex("하치!" + content + "와레!")

    def test_string_numeric_assignment_and_operators_rejected(self):
        for body in ("얏! 하치와레: 값 하치! 12 와레! 야하!", "하치와레! 하치와레: 값 뿌 야하!",
                     "하치와레! 하치와레: 값 하치! 안녕 와레! 야하! 하치와레: 값 야~하! 뿌 야하!",
                     "우~라~ 하치! a 와레! 하! 하치! b 와레! 야하!"):
            with self.assertRaisesRegex(CompileError, "문자열"):
                compile_source(program(body))

    def test_string_return_type_is_inferred(self):
        generated = compile_source("우나! 하치와레: 인사 만들기 우~나! 하치! 안녕 와레!\n" + program(""))
        self.assertIn("us_string us_f1(void)", generated)


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.cc = find_clang()
        except ToolchainError as error:
            raise unittest.SkipTest(str(error))
        cls.temporary = tempfile.TemporaryDirectory(prefix="usagi-native-tests-")
        cls.root = Path(cls.temporary.name)
        cls.binaries = {}
        fixtures = {
            "arithmetic": (ROOT / "examples/arithmetic.usagi").read_text(encoding="utf-8"),
            "scopes": (ROOT / "examples/places_and_scopes.usagi").read_text(encoding="utf-8"),
            "input": (ROOT / "examples/input_plus_one.usagi").read_text(encoding="utf-8"),
            "real": (ROOT / "examples/real_input.usagi").read_text(encoding="utf-8"),
            "echo_int": program("얏! 하치와레: 야 뿌 야하! 냠? 하치와레: 야 야하! 우~라~ 하치와레: 야 야하!"),
            "echo_real": program("핫! 하치와레: 야 뿌 야하! 냠? 하치와레: 야 야하! 우~라~ 하치와레: 야 야하!"),
            "mixed": program("핫! 하치와레: 야 뿌르 야하! 우~라~ 하치와레: 야 하! 뿌.뿌릇 야하! 우~라~ 릇뿌뿌.뿌릇 야하!"),
            "functions": (ROOT / "examples/functions.usagi").read_text(encoding="utf-8"),
            "left_assoc": program("우~라~ 뿌릇뿌릇 하아! 뿌르르르 하아! 뿌르르 야하!"),
        }
        for kind, token in (("add", "하!"), ("sub", "하아!"), ("mul", "하핫!"), ("div", "푸루!"), ("mod", "푸루루!")):
            fixtures[kind] = program(f"얏! 하치와레: 야 뿌 야하! 얏! 하치와레: 야야 뿌 야하! 냠? 하치와레: 야 야하! 냠? 하치와레: 야야 야하! 우~라~ 하치와레: 야 {token} 하치와레: 야야 야하!")
        fixtures["real_mul"] = program("핫! 하치와레: 야 뿌 야하! 냠? 하치와레: 야 야하! 우~라~ 하치와레: 야 하핫! 뿌르르 야하!")
        fixtures["real_div"] = program("우~라~ 뿌르.뿌 푸루! 뿌 야하!")
        fixtures["convert"] = program("핫! 하치와레: 야 뿌 야하! 냠? 하치와레: 야 야하! 얏! 하치와레: 야야 뿌 야하! 하치와레: 야야 야~하! 하치와레: 야 야하! 우~라~ 하치와레: 야야 야하!")
        fixtures["call_order"] = ("우나! 하치와레: 읽기 얏! 하치와레: 야 뿌 야하! 냠? 하치와레: 야 야하! 우~나! 하치와레: 야\n"
                                  + program("우~라~ 하치와레: 읽기 우라! 우라라! 하아! 하치와레: 읽기 우라! 우라라! 야하!"))
        fixtures["standalone_call"] = (program("하치와레: 소리 우라! 우라라! 야하! 우~라~ 뿌르 야하!")
                                       + "우나! 하치와레: 소리 우~라~ 뿌릇 야하! 우~나! 뿌\n")
        fixtures["chain"] = (program("우~라~ 하치와레: 첫째 우라! 우라라! 야하!")
                             + "우나! 하치와레: 첫째 우~나! 하치와레: 둘째 우라! 우라라! 하! 뿌르\n"
                             + "우나! 하치와레: 둘째 얏! 하치와레: 야 뿌르르르.뿌르르 야하! 우~나! 하치와레: 야\n")
        fixtures["strings"] = (ROOT / "examples/strings.usagi").read_text(encoding="utf-8")
        fixtures["short_variables"] = (ROOT / "examples/short_variables.usagi").read_text(encoding="utf-8")
        fixtures["echo_string"] = program("하치와레! 하치와레: 입력 내용 하치! 와레! 야하! 하아? 하치와레: 입력 내용 야하! 우~라~ 하치와레: 입력 내용 야하!")
        fixtures["string_copy"] = ("우나! 하치와레: 읽어 주기 하치와레! 하치와레: 값 하치! 와레! 야하! 하아? 하치와레: 값 야하! 우~나! 하치와레: 값\n"
                                   + program("하치와레! 하치와레: 첫 값 하치와레: 읽어 주기 우라! 우라라! 야하! 하치와레! 하치와레: 복사 값 하치와레: 첫 값 야하! 하치와레: 첫 값 야~하! 하치와레: 읽어 주기 우라! 우라라! 야하! 우~라~ 하치와레: 복사 값 야하! 우~라~ 하치와레: 첫 값 야하!"))
        cls.payload = '한글 😀 "quote" \\n %s ??/ ); /* 우사기! !우사기 하치와레: 야하!'
        fixtures["string_literal"] = program("우~라~ 하치! " + cls.payload + " 와레! 야하! 우~라~ 하치! 와레! 야하! 우~라~ 하치!  앞뒤  와레! 야하!")
        try:
            for name, source in fixtures.items():
                output = cls.root / (name + (".exe" if os.name == "nt" else ""))
                cls.binaries[name] = build(compile_source(source, "테스트 😀 파일.usagi"), output, cls.cc)
        except Exception:
            cls.temporary.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_program(self, name, input_text=""):
        return subprocess.run([str(self.binaries[name])], input=input_text, text=True,
                              encoding="utf-8", capture_output=True, timeout=5)

    def assert_output(self, name, input_text, output):
        result = self.run_program(name, input_text)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, output, ""))

    def assert_runtime_error(self, name, input_text, message):
        result = self.run_program(name, input_text)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(message, result.stderr)
        self.assertIn("테스트 😀 파일.usagi:", result.stderr)

    def test_input_plus_one(self):
        self.assert_output("input", "4\n", "5\n")

    def test_short_variables_support_input_assignment_return_and_all_types(self):
        self.assert_output("short_variables", "4\n", "5\n3.2\n안녕!\n5\n")

    def test_string_example_and_literal_bytes(self):
        self.assert_output("strings", "", "안녕, 우사기!\n반가워!\n")
        self.assert_output("string_literal", "", self.payload + "\n\n 앞뒤 \n")

    def test_string_input_preserves_spaces_and_empty_line(self):
        for text in ("  안녕 😀  ", "", "하치와레: 이름", "123", "a" * 4095, "가" * 1365):
            with self.subTest(length=len(text)):
                self.assert_output("echo_string", text + "\n", text + "\n")
        self.assert_output("echo_string", "마지막 줄", "마지막 줄\n")
        self.assert_runtime_error("echo_string", "", "unexpected end of input")
        self.assert_runtime_error("echo_string", "a" * 4096 + "\n", "input line too long")
        self.assert_runtime_error("echo_string", "a\0b\n", "NUL byte")

    def test_string_values_survive_function_return_and_reassignment(self):
        self.assert_output("string_copy", "첫 번째\n두 번째\n", "첫 번째\n두 번째\n")

    def test_precedence_parentheses_assignment_modulo(self):
        self.assert_output("arithmetic", "", "14\n4\n1\n")
        self.assert_output("left_assoc", "", "5\n")

    def test_place_values_and_shadowing(self):
        self.assert_output("scopes", "", "123\n-5\n123\n")

    def test_real_input_and_promotion(self):
        self.assert_output("real", "3.2\n", "3.7\n")
        self.assert_output("mixed", "", "1.5\n-0.5\n")
        self.assert_output("echo_real", "0.05\n", "0.05\n")
        self.assert_output("echo_real", "  +1.25e2  \n", "125\n")

    def test_functions_infer_types_and_convert_at_destination(self):
        self.assert_output("functions", "", "3\n3.2\n")
        self.assert_output("chain", "", "4\n")

    def test_calls_execute_left_to_right_and_return_to_caller(self):
        self.assert_output("call_order", "10\n3\n", "7\n")
        self.assert_output("standalone_call", "", "5\n1\n")

    def test_real_to_int_conversion_boundaries(self):
        for text, expected in (("3.9", "3"), ("-3.9", "-3"), ("-0.5", "0"),
                               ("9223372036854774784", "9223372036854774784"),
                               (str(MIN), str(MIN)), ("1e-300", "0")):
            with self.subTest(text=text):
                self.assert_output("convert", text + "\n", expected + "\n")
        for text in ("9223372036854775808", "-9223372036854777856", "1e308"):
            with self.subTest(text=text):
                self.assert_runtime_error("convert", text + "\n", "conversion out of range")

    def test_signed_division_and_remainder(self):
        for a, b, quotient, remainder in ((-7, 3, -2, -1), (7, -3, -2, 1), (-7, -3, 2, -1), (7, 3, 2, 1)):
            self.assert_output("div", f"{a}\n{b}\n", f"{quotient}\n")
            self.assert_output("mod", f"{a}\n{b}\n", f"{remainder}\n")

    def test_integer_boundary_arithmetic(self):
        operations = {"add": lambda a, b: a + b, "sub": lambda a, b: a - b, "mul": lambda a, b: a * b}
        pairs = [(MAX, 1), (MIN, -1), (MAX, -1), (MIN, 1), (MIN, 0), (MAX, 0),
                 (MIN, MIN), (MAX, MAX), (MIN, MAX), (MAX, MIN), (-1, MIN),
                 (MIN, 2), (MAX, 2), (-2, -3), (-2, 3), (0, MIN)]
        for name, operation in operations.items():
            for a, b in pairs:
                with self.subTest(operation=name, a=a, b=b):
                    expected = operation(a, b)
                    if MIN <= expected <= MAX:
                        self.assert_output(name, f"{a}\n{b}\n", f"{expected}\n")
                    else:
                        self.assert_runtime_error(name, f"{a}\n{b}\n", "integer overflow")

    def test_division_errors(self):
        for name in ("div", "mod"):
            self.assert_runtime_error(name, "5\n0\n", "division by zero")
            self.assert_runtime_error(name, f"{MIN}\n-1\n", "integer overflow")
            self.assert_output(name, f"{MIN}\n1\n", f"{MIN if name == 'div' else 0}\n")
        self.assert_runtime_error("real_div", "", "division by zero")

    def test_real_nonfinite_result(self):
        self.assert_runtime_error("real_mul", "1e308\n", "non-finite real result")

    def test_integer_input_boundaries(self):
        self.assert_output("echo_int", str(MAX) + "\n", str(MAX) + "\n")
        self.assert_output("echo_int", str(MIN) + "\n", str(MIN) + "\n")
        self.assert_runtime_error("echo_int", str(MAX + 1) + "\n", "out of range")
        self.assert_runtime_error("echo_int", str(MIN - 1) + "\n", "out of range")

    def test_invalid_input_and_eof(self):
        for text in ("abc\n", "3.2\n", "0x10\n", "뿌르\n", "1e2\n"):
            with self.subTest(text=text):
                self.assert_runtime_error("echo_int", text, "expected a decimal integer")
        self.assert_runtime_error("echo_int", "", "unexpected end of input")
        self.assert_runtime_error("echo_int", "\n", "unexpected end of input")
        self.assert_output("echo_int", "1 2\n", "1\n")
        self.assert_runtime_error("echo_int", "1\0\n", "NUL byte")
        self.assert_runtime_error("echo_int", "1" * 4096 + "\n", "input line too long")
        self.assert_output("echo_int", "  +42  ", "42\n")

    def test_real_input_validation(self):
        for text in ("nan\n", "inf\n", "0x1p2\n", "1e\n", ".\n", "1.2x\n"):
            self.assert_runtime_error("echo_real", text, "expected a decimal real number")
        for text in ("1e999\n", "1e-999\n"):
            self.assert_runtime_error("echo_real", text, "out of range")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="usagi-cli-tests-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "source with spaces.usagi"
        self.source.write_text(program("우~라~ 뿌릇 야하!"), encoding="utf-8-sig")

    def tearDown(self):
        self.temporary.cleanup()

    def call(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as errors:
            status = main(list(args))
        return status, output.getvalue(), errors.getvalue()

    def test_check_and_utf8_bom(self):
        status, _, errors = self.call("check", str(self.source))
        self.assertEqual((status, errors), (0, ""))

    def test_emit_self_contained_c(self):
        output = self.root / "generated.c"
        status, _, errors = self.call("emit-c", str(self.source), "-o", str(output))
        self.assertEqual((status, errors), (0, ""))
        generated = output.read_text(encoding="utf-8")
        self.assertIn("int main(void)", generated)
        self.assertIn("int64_t us_i_add", generated)
        self.assertNotIn('#include "', generated)

    def test_source_overwrite_prevented(self):
        original = self.source.read_bytes()
        status, _, errors = self.call("emit-c", str(self.source), "-o", str(self.source))
        self.assertEqual(status, 1)
        self.assertIn("덮어쓸 수 없습니다", errors)
        self.assertEqual(self.source.read_bytes(), original)

    def test_missing_file_and_invalid_source(self):
        self.assertEqual(self.call("check", str(self.root / "missing.usagi"))[0], 1)
        self.source.write_text(program("하아? 하치와레: 야 야하!"), encoding="utf-8")
        status, _, errors = self.call("check", str(self.source))
        self.assertEqual(status, 1)
        self.assertIn(":2:5:", errors)

    def test_failed_build_preserves_existing_output(self):
        existing = self.root / "existing.exe"
        existing.write_bytes(b"preserve this file")
        status, _, _ = self.call("build", str(self.source), "-o", str(existing), "--cc", str(self.root / "missing-clang"))
        self.assertEqual(status, 1)
        self.assertEqual(existing.read_bytes(), b"preserve this file")

    def test_module_run(self):
        try:
            find_clang()
        except ToolchainError as error:
            self.skipTest(str(error))
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run([sys.executable, "-m", "usagi", "run", str(self.source)],
                                cwd=ROOT, env=env, capture_output=True, encoding="utf-8", timeout=90)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "5\n", ""))

    def test_run_interrupt_reaps_infinite_program_and_removes_temporary_executable(self):
        try:
            find_clang()
        except ToolchainError as error:
            self.skipTest(str(error))
        self.source.write_text(program("푸루룻! 푸루룻? 뿌르"), encoding="utf-8")
        real_popen = subprocess.Popen
        children = []
        executable_paths = []

        def spawn(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            command = args[0] if args else kwargs["args"]
            if Path(command[0]).name in ("program.exe", "program"):
                children.append(child)
                executable_paths.append(Path(command[0]))
                real_wait = child.wait
                interrupted = False

                def wait(timeout=None):
                    nonlocal interrupted
                    if not interrupted:
                        interrupted = True
                        raise KeyboardInterrupt
                    return real_wait(timeout=timeout)

                child.wait = wait
            return child

        try:
            with patch("usagi.cli.subprocess.Popen", side_effect=spawn):
                status, _, _ = self.call("run", str(self.source))
            self.assertEqual(status, 130)
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll())
            self.assertFalse(executable_paths[0].parent.exists())
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
