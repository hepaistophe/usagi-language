import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from usagi.cli import main
from usagi.compiler import CompileError, compile_source
from usagi.toolchain import ToolchainError, build, find_clang


ROOT = Path(__file__).resolve().parents[1]


def program(body):
    return f"우사기!\n{body}\n!우사기\n"


ADD = "우나! 하치와레: 더하기 냠! 얏! 야 냠! 얏! 야야 우~나! 야 하! 야야\n"


class ArgumentFrontendTests(unittest.TestCase):
    def test_zero_argument_calls_keep_old_parentheses(self):
        compile_source("우나! 하치와레: 값 우~나! 뿌\n" + program("우~라~ 하치와레: 값 우라! 우라라! 야하! 하치와레: 값 우라! 우라라! 야하!"))

    def test_typed_parameters_and_multiword_names(self):
        compile_source("우나! 하치와레: 값 돌려주기 냠! 핫! 하치와레: 받은 값 우~나! 하치와레: 받은 값\n" + program("우~라~ 하치와레: 값 돌려주기 냠! 뿌르 꿀꺽! 야하!"))

    def test_argument_count_mismatches(self):
        for call in ("하치와레: 더하기 우라! 우라라!", "하치와레: 더하기 냠! 뿌 꿀꺽!", "하치와레: 더하기 냠! 뿌 냠! 뿌 냠! 뿌 꿀꺽!"):
            with self.subTest(call=call), self.assertRaisesRegex(CompileError, "인자 2개"):
                compile_source(ADD + program("우~라~ " + call + " 야하!"))

    def test_duplicate_parameters_and_redeclaration(self):
        for definition in ("우나! 하치와레: 값 냠! 얏! 야 냠! 핫! 하치와레: 야 우~나! 야",
                           "우나! 하치와레: 값 냠! 얏! 야 얏! 야 뿌 야하! 우~나! 야"):
            with self.subTest(definition=definition), self.assertRaisesRegex(CompileError, "중복 선언"):
                compile_source(definition + "\n" + program(""))

    def test_missing_type_name_value_and_closing_marker(self):
        for source in ("우나! 하치와레: 값 냠! 야 우~나! 뿌", "우나! 하치와레: 값 냠! 얏! 우~나! 뿌",
                       ADD + program("우~라~ 하치와레: 더하기 냠! 꿀꺽! 야하!"),
                       ADD + program("우~라~ 하치와레: 더하기 냠! 뿌 냠! 뿌 야하!")):
            with self.subTest(source=source), self.assertRaises(CompileError):
                compile_source(source)

    def test_string_numeric_argument_conversion_is_rejected(self):
        with self.assertRaisesRegex(CompileError, "문자열과 숫자"):
            compile_source(ADD + program("우~라~ 하치와레: 더하기 냠! 하치! a 와레! 냠! 뿌 꿀꺽! 야하!"))

    def test_parameters_are_local_and_forward_calls_work(self):
        compile_source(program("우~라~ 하치와레: 더하기 냠! 뿌르 냠! 뿌르르 꿀꺽! 야하!") + ADD)
        with self.assertRaisesRegex(CompileError, "선언되지 않은 변수"):
            compile_source(ADD + program("우~라~ 야 야하!"))

    def test_recursive_feeding_remains_diagnosed(self):
        source = "우나! 하치와레: 재귀 냠! 얏! 야 우~나! 하치와레: 재귀 냠! 야 꿀꺽!\n" + program("")
        with self.assertRaisesRegex(CompileError, "순환"):
            compile_source(source)


class JsonDiagnosticTests(unittest.TestCase):
    def check(self, source):
        with patch('sys.stdin', io.StringIO(source)), contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            status = main(['check', 'unsaved.usagi', '--stdin', '--json'])
        self.assertEqual(stderr.getvalue(), '')
        return status, json.loads(stdout.getvalue())

    def test_successful_unsaved_document(self):
        status, result = self.check(program('우~라~ 하치! 😀 와레! 야하!'))
        self.assertEqual((status, result), (0, {'ok': True, 'diagnostics': []}))

    def test_error_reports_original_position(self):
        status, result = self.check(program('우~라~ 야 야하!'))
        self.assertEqual(status, 1)
        self.assertEqual((result['diagnostics'][0]['line'], result['diagnostics'][0]['column']), (2, 6))
        self.assertIn('선언되지 않은 변수', result['diagnostics'][0]['message'])


class ArgumentNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.cc = find_clang()
        except ToolchainError as error:
            raise unittest.SkipTest(str(error))
        cls.temporary = tempfile.TemporaryDirectory(prefix='usagi-arguments-')
        cls.root = Path(cls.temporary.name)
        fixtures = {'example': (ROOT / 'examples/feeding_arguments.usagi').read_text(encoding='utf-8')}
        fixtures['nested'] = ADD + program('우~라~ 하치와레: 더하기 냠! 하치와레: 더하기 냠! 뿌르 냠! 뿌르르 꿀꺽! 냠! 뿌르르르 꿀꺽! 야하!')
        reader = '우나! 하치와레: 읽기 얏! 야 뿌 야하! 냠? 야 야하! 우~나! 야\n'
        fixtures['order'] = reader + '우나! 하치와레: 빼기 냠! 얏! 야 냠! 얏! 야야 우~나! 야 하아! 야야\n' + program('우~라~ 하치와레: 빼기 냠! 하치와레: 읽기 우라! 우라라! 냠! 하치와레: 읽기 우라! 우라라! 꿀꺽! 야하!')
        fixtures['convert'] = '우나! 하치와레: 변환 냠! 얏! 야 냠! 핫! 야야 우~나! 야 하! 야야\n' + program('우~라~ 하치와레: 변환 냠! 릇뿌뿌르르르.뿌릇 냠! 뿌르 꿀꺽! 야하!')
        fixtures['copy'] = '우나! 하치와레: 바꾸기 냠! 하치와레! 야 야 야~하! 하치! 새 값 와레! 야하! 우~나! 야\n' + program('하치와레! 야 하치! 원래 값 와레! 야하! 우~라~ 하치와레: 바꾸기 냠! 야 꿀꺽! 야하! 우~라~ 야 야하!')
        fixtures['local'] = '우나! 하치와레: 바꾸기 냠! 얏! 야 우랏! 얏! 야 뿌릇 야하! 우~라~ 야 야하! 우라랏! 야 야~하! 야 하! 뿌르 야하! 우~나! 야\n' + program('얏! 야 뿌르 야하! 우~라~ 하치와레: 바꾸기 냠! 야 꿀꺽! 야하! 우~라~ 야 야하!')
        fixtures['loop'] = '우나! 하치와레: 합계 냠! 얏! 야 얏! 야야 뿌 야하! 우쨔? 야 야야 야~하! 야야 하! 뿌야! 야하! 우쨔! 우~나! 야야\n' + program('우~라~ 하치와레: 합계 냠! 뿌르르르 꿀꺽! 야하!')
        fixtures['overflow'] = '우나! 하치와레: 정수 냠! 얏! 야 우~나! 야\n' + program('핫! 야 뿌 야하! 냠? 야 야하! 우~라~ 하치와레: 정수 냠! 야 꿀꺽! 야하!')
        cls.binaries = {}
        try:
            for name, source in fixtures.items():
                cls.binaries[name] = build(compile_source(source, '인자 테스트.usagi'), cls.root / (name + ('.exe' if os.name == 'nt' else '')), cls.cc)
        except Exception:
            cls.temporary.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_program(self, name, text=''):
        return subprocess.run([str(self.binaries[name])], input=text, capture_output=True, encoding='utf-8', timeout=5)

    def assert_output(self, name, expected, text=''):
        result = self.run_program(name, text)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ''))

    def test_feeding_example_and_nested_calls(self):
        self.assert_output('example', '5\n우사기!\n')
        self.assert_output('nested', '6\n')

    def test_arguments_evaluate_left_to_right(self):
        self.assert_output('order', '7\n', '10\n3\n')

    def test_argument_conversion_uses_parameter_type(self):
        self.assert_output('convert', '-2\n')
        result = self.run_program('overflow', '1e308\n')
        self.assertEqual(result.returncode, 2)
        self.assertIn('conversion out of range', result.stderr)

    def test_string_and_numeric_parameters_are_copied(self):
        self.assert_output('copy', '새 값\n원래 값\n')
        self.assert_output('local', '5\n2\n1\n')

    def test_parameter_can_control_repetition(self):
        self.assert_output('loop', '6\n')


if __name__ == '__main__':
    unittest.main()
