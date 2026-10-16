import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from usagi.compiler import CompileError, compile_source, lex
from usagi.toolchain import ToolchainError, build, find_clang


def program(body):
    return f'우사기!\n{body}\n!우사기\n'


class NewFrontendTests(unittest.TestCase):
    def test_commas_delimit_multiword_and_short_names_without_spaces(self):
        tokens = lex('냠? 하치와레: 사람 수,하치와레: 평균 점수,야 야하!')
        self.assertEqual([t.text for t in tokens if t.kind in ('NAME', 'SHORT_NAME')], ['사람 수', '평균 점수', '야'])
        self.assertEqual(sum(t.kind == 'COMMA' for t in tokens), 2)

    def test_input_target_types_are_checked(self):
        for body, message in (
            ('얏! 야 뿌 야하! 하아? 야 야하!', '하아?는 문자열'),
            ('핫! 야 뿌 야하! 하아? 야 야하!', '하아?는 문자열'),
            ('하치와레! 야 하치! 와레! 야하! 냠? 야 야하!', '냠?는 숫자'),
            ('냠? 뿌 야하!', '입력·대입 대상'),
            ('얏! 야 뿌 야하! 냠? 야, 야 하! 뿌르 야하!', '입력·대입 대상'),
        ):
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, message.replace('?', r'\?')):
                compile_source(program(body))

    def test_input_list_requires_a_target_on_both_sides_of_each_comma(self):
        for body in ('냠? 야하!', '냠? ,야 야하!', '얏! 야 뿌 야하! 냠? 야, 야하!', '얏! 야 뿌 야하! 냠? 야,,야 야하!'):
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_source(program(body))

    def test_array_size_and_index_must_be_integer(self):
        for body, message in (
            ('야얏! 뿌.뿌릇 야 야하!', '배열 크기는 정수'),
            ('야얏! 하치! a 와레! 야 야하!', '배열 크기는 정수'),
            ('야얏! 뿌릇 야 야하! 우~라~ 뿌.뿌릇 야 야하!', '배열 인덱스는 정수'),
            ('얏! 야 뿌 야하! 우~라~ 뿌 야 야하!', '정수 배열이어야'),
        ):
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, message):
                compile_source(program(body))

    def test_whole_array_operations_are_rejected(self):
        for body in ('우~라~ 야 야하!', '야 야~하! 뿌 야하!', '냠? 야 야하!',
                     '얏! 야야 야 야하!', '우~라~ 야 하! 뿌르 야하!', '갸웃? 야 야호! 갸웃!'):
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_source(program('야얏! 뿌릇 야 야하! ' + body))
        with self.assertRaisesRegex(CompileError, '반환할 수 없습니다'):
            compile_source('우나! 하치와레: 배열 야얏! 뿌릇 야 야하! 우~나! 야\n' + program(''))

    def test_array_scope_is_lexical(self):
        with self.assertRaisesRegex(CompileError, '선언되지 않은 변수'):
            compile_source(program('우랏! 야얏! 뿌릇 야 야하! 우라랏! 우~라~ 뿌 야 야하!'))

    def test_newline_only_works_inside_a_literal(self):
        self.assertEqual(lex('하치! 가우이!나 와레!')[0].text, '가\n나')
        self.assertEqual(lex('하치! 우이! 와레!')[0].text, '\n')
        with self.assertRaisesRegex(CompileError, '문자열 안의 개행'):
            compile_source(program('우이! 야하!'))

    def test_newline_length_limit_uses_the_decoded_string(self):
        compile_source(program('우~라~ 하치! ' + '우이!' * 4095 + ' 와레! 야하!'))
        with self.assertRaisesRegex(CompileError, '4095바이트'):
            compile_source(program('우~라~ 하치! ' + '우이!' * 4096 + ' 와레! 야하!'))


class NewNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cc = find_clang()
        except ToolchainError as error:
            raise unittest.SkipTest(str(error))
        cls.temporary = tempfile.TemporaryDirectory(prefix='usagi-v06-')
        cls.binaries = {}
        fixtures = {
            'numeric': program('얏! 하치와레: 사람 수 뿌 야하! 핫! 하치와레: 평균 점수 뿌 야하! 냠? 하치와레: 사람 수,하치와레: 평균 점수 야하! 우~라~ 하치와레: 사람 수 야하! 우~라~ 하치와레: 평균 점수 야하!'),
            'switch': program('얏! 야 뿌 야하! 냠? 야 야하! 하치와레! 야야 하치! 와레! 야하! 하아? 야야 야하! 우~라~ 야 야하! 우~라~ 야야 야하!'),
            'array': program('얏! 야 뿌 야하! 냠? 야 야하! 야얏! 야 하치와레: 점수 야하! 우~라~ 뿌 하치와레: 점수 야하! 뿌르 하치와레: 점수 야~하! 뿌릇 야하! 우라! 뿌르 하! 뿌르 우라라! 하치와레: 점수 야~하! 뿌릇뿌르 야하! 우~라~ 뿌르 하! 뿌르 하치와레: 점수 야하! 우~라~ 우라! 뿌르 하! 뿌르 우라라! 하치와레: 점수 야하!'),
            'array_input': program('얏! 야 뿌 야하! 야얏! 뿌릇 하치와레: 점수 야하! 냠? 야,야 하치와레: 점수 야하! 우~라~ 야 하치와레: 점수 야하!'),
            'size': program('얏! 야 뿌 야하! 냠? 야 야하! 야얏! 야 야야 야하! 우~라~ 뿌 야야 야하!'),
            'bounds': program('야얏! 뿌르 야 야하! 얏! 야야 뿌 야하! 냠? 야야 야하! 야야 야 야~하! 뿌릇 야하! 우~라~ 야야 야 야하!'),
            'newline': program('우~라~ 하치! 안녕우이!우사기! 와레! 야하!'),
            'lifetime': '우나! 하치와레: 값 야얏! 뿌르 야 야하! 뿌 야 야~하! 뿌릇 야하! 우~나! 뿌 야\n' + program('우쨔? 뿌르르 우랏! 야얏! 뿌르 야 야하! 휙! 야하! 우라랏! 우쨔! 푸루룻! 야얏! 뿌르 야 야하! 삐익! 야하! 푸루룻? 뿌르 우~라~ 하치와레: 값 우라! 우라라! 야하!'),
            'repeat_continue': program('얏! 야 뿌르르 야하! 푸루룻! 야얏! 뿌르 야야 야하! 야 야~하! 야 하아! 뿌르 야하! 휙! 야하! 푸루룻? 야 우~라~ 야 야하!'),
            'size_expression': program('야얏! 뿌르 하! 뿌르 야 야하! 야얏! 우라! 뿌 야 하! 뿌르 우라라! 야야 야하! 우~라~ 뿌 야야 야하!'),
            'remaining_index': program('야얏! 뿌르르르르 야 야하! 우쨔? 뿌르르르 뿌야! 야 야~하! 뿌야! 야하! 우쨔! 우~라~ 뿌르르르 야 야하!'),
        }
        try:
            for name, source in fixtures.items():
                output = Path(cls.temporary.name) / (name + ('.exe' if os.name == 'nt' else ''))
                cls.binaries[name] = build(compile_source(source, '새 문법.usagi'), output, cc)
        except Exception:
            cls.temporary.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_program(self, name, text=''):
        return subprocess.run([str(self.binaries[name])], input=text, capture_output=True, encoding='utf-8', timeout=5)

    def output(self, name, text, expected):
        result = self.run_program(name, text)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ''))

    def error(self, name, text, expected):
        result = self.run_program(name, text)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(expected, result.stderr)

    def test_numeric_inputs_share_a_whitespace_cursor(self):
        for text in ('5 82.5\n', '\n5\t\n\n82.5', '+5\r\n8.25e1\r\n'):
            self.output('numeric', text, '5\n82.5\n')

    def test_invalid_fields_do_not_parse_partially_or_convert_to_integer(self):
        for text in ('3.5 1', '1e2 1', '1x 1', '5,3 1'):
            self.error('numeric', text, 'expected a decimal integer')
        self.error('numeric', '5', 'unexpected end of input')
        self.error('numeric', '5 nan', 'expected a decimal real')

    def test_string_after_number_preserves_spaces_and_blank_lines(self):
        self.output('switch', '5   \n  안녕 😀  \n', '5\n  안녕 😀  \n')
        self.output('switch', '5\n\n', '5\n\n')
        self.output('switch', '5\n우이!\n', '5\n우이!\n')
        self.error('switch', '5 6\n안녕\n', 'unread numeric fields')

    def test_array_initialization_access_and_operator_precedence(self):
        self.output('array', '3', '0\n6\n6\n')
        self.output('size_expression', '', '0\n')

    def test_multi_input_evaluates_array_targets_in_order(self):
        self.output('array_input', '2 17', '17\n')

    def test_remaining_counter_can_index_a_writable_array_element(self):
        self.output('remaining_index', '', '3\n')

    def test_size_and_index_errors(self):
        self.error('size', '-1', 'negative array size')
        self.error('size', '0', 'out of bounds')
        self.error('size', '9223372036854775807', 'array size out of range')
        self.error('bounds', '-1', 'out of bounds')
        self.error('bounds', '1', 'out of bounds')
        self.output('bounds', '0', '5\n')

    def test_newline_output_is_an_actual_line_break(self):
        self.output('newline', '', '안녕\n우사기!\n')

    def test_arrays_survive_until_return_and_cleanup_on_loop_exits(self):
        self.output('lifetime', '', '5\n')
        self.output('repeat_continue', '', '0\n')


if __name__ == '__main__':
    unittest.main()
