from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import tempfile
import unittest

from usagi.compiler import CompileError, compile_source, Parser, lex, analyze
from usagi.toolchain import build

def program(body):
    return f'우사기!\n{body}\n!우사기\n'

class StringFrontendTests(unittest.TestCase):
    def test_reject_wrong_types_and_missing_delimiters(self):
        for expression in ['하치! a 와레! 시사! 뿌르', '뿌르 시사! 뿌르',
                           '모몽가! 우라! 하치! a 와레! 우라라!',
                           '모몽가! 뿌르', '모몽가! 우라! 뿌르',
                           '하치! a 와레! 하! 하치! b 와레!']:
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                compile_source(program(f'우~라~ {expression} 야하!'))
        with self.assertRaises(CompileError):
            compile_source(program('야얏! 뿌르 야 야하! 우~라! 모몽가! 우라! 야 우라라! 야하!'))

    def test_concat_is_left_associative(self):
        parsed=Parser(lex(program('우~라~ 하치! a 와레! 시사! 하치! b 와레! 시사! 하치! c 와레! 야하!'))).parse()
        analyze(parsed)
        expression=parsed.main.body[0].expr
        self.assertEqual(expression.left.value, 'CONCAT')
        self.assertEqual(expression.right.value, 'c')

class StringNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory(prefix='usagi-strings-')

    @classmethod
    def tearDownClass(cls): cls.folder.cleanup()

    def run_source(self, source, stdin=''):
        binary=Path(self.folder.name)/'program.exe'
        build(compile_source(source),binary)
        result=subprocess.run([str(binary)],input=stdin.encode(),capture_output=True,timeout=10)
        return result.returncode,result.stdout.decode().replace('\r\n','\n'),result.stderr.decode()

    def test_conversion_concat_copy_and_no_newline(self):
        code=program('얏! 야 뿌 야하! 핫! 야야 뿌 야하! 냠? 야, 야야 야하!\n'
                     '하치와레! 야야야 모몽가! 우라! 야 우라라! 시사! 하치! / 와레! 시사! 모몽가! 우라! 야야 우라라! 야하!\n'
                     '하치와레! 야야야야 야야야 야하! 야야야 야~하! 하치! 바뀜 와레! 야하!\n'
                     '우~라! 야야야야 야하! 우~라! 하치! 우이!끝 와레! 야하!')
        status,out,err=self.run_source(code,'9223372036854775807 -2.75')
        self.assertEqual((status,out),(0,'9223372036854775807/-2.75\n끝'),err)

    def test_real_and_integer_format_matches_output(self):
        code=program('얏! 야 뿌 야하! 핫! 야야 뿌 야하! 냠? 야, 야야 야하! 우~라~ 야 야하! 우~라~ 모몽가! 우라! 야 우라라! 야하! 우~라~ 야야 야하! 우~라~ 모몽가! 우라! 야야 우라라! 야하! 우~라! 야야 야하!')
        for data in ['-9223372036854775808 -0.0','9007199254740993 1e20','0 1e-8']:
            status,out,err=self.run_source(code,data)
            self.assertEqual(status,0,err)
            rows=out.split('\n'); self.assertEqual(rows[0],rows[1]); self.assertEqual(rows[2],rows[3]); self.assertEqual(rows[3],rows[4])

    def test_calls_evaluate_left_to_right_and_return_strings(self):
        source='우나! 하치와레: 읽기 얏! 야 뿌 야하! 냠? 야 야하! 우~라! 야 야하! 우~나! 모몽가! 우라! 야 우라라!\n'+program('우~라~ 하치와레: 읽기 우라! 우라라! 시사! 하치와레: 읽기 우라! 우라라! 야하!')
        status,out,err=self.run_source(source,'1 2')
        self.assertEqual((status,out),(0,'1212\n'),err)

    def test_utf8_boundary_and_overflow(self):
        code=program('하치와레! 야 하치! 와레! 야하! 하아? 야 야하! 우~라! 야 시사! 하치! 가 와레! 야하!')
        status,out,err=self.run_source(code,'가'*1364)
        self.assertEqual((status,len(out.encode())),(0,4095),err)
        status,out,err=self.run_source(code,'가'*1365)
        self.assertEqual(status,2); self.assertIn('4095',err); self.assertEqual(out,'')

    def test_prompt_is_flushed_before_input(self):
        binary=Path(self.folder.name)/'prompt.exe'
        build(compile_source(program('우~라! 하치! 입력: 와레! 야하! 얏! 야 뿌 야하! 냠? 야 야하! 우~라~ 야 야하!')),binary)
        process=subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        pool=ThreadPoolExecutor(max_workers=1)
        try:
            future=pool.submit(process.stdout.read,len('입력:'.encode()))
            self.assertEqual(future.result(timeout=5),'입력:'.encode())
            out,err=process.communicate(b'42\n',timeout=5)
            self.assertEqual(process.returncode,0,err); self.assertEqual(out.replace(b'\r\n',b'\n'),b'42\n')
        finally:
            if process.poll() is None: process.kill(); process.communicate()
            pool.shutdown()

    def test_99_bottles_complete_output(self):
        source=(Path(__file__).resolve().parents[1]/'examples/99_bottles.usagi').read_text(encoding='utf-8')
        expected=''
        for n in range(99,0,-1):
            expected+=f'{n}병의 맥주가 벽에 있네!\n{n}병의 맥주!\n한 병 내려서 돌려 마시자!\n'
            expected+=f'{n-1}병의 맥주가 벽에 남았네!\n\n' if n>1 else '이제 벽에는 맥주가 없네!\n\n'
        expected+='맥주가 한 병도 없네!\n가게에 가서 99병을 더 사 오자!\n'
        status,out,err=self.run_source(source)
        self.assertEqual((status,out),(0,expected),err)
