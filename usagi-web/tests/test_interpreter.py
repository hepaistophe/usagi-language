from pathlib import Path
import json
import asyncio
import random
import sys
import unittest
from collections import deque
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dist/runtime"))
import interpreter as runtime
from interpreter import execute, Interpreter
from usagi.compiler import Parser, lex, analyze
from usagi.numbers import encode_integer


def program(body):
    return f"우사기!\n{body}\n!우사기\n"


class InterpreterTests(unittest.TestCase):
    def test_string_features(self):
        self.check(program('얏! 야 뿌 야하! 냠? 야 야하! 우~라! 모몽가! 우라! 야 우라라! 시사! 하치! 병 와레! 야하! 우~라! 하치! 우이!끝 와레! 야하!'), '9223372036854775807병\n끝', '9223372036854775807')
        self.check(program('우~라! 하치! 와레! 야하! 우~라~ 모몽가! 우라! 릇뿌뿌.뿌 우라라! 야하!'), '-0\n')
        self.fails(program('우~라~ 하치! a 와레! 시사! 뿌르 야하!'), '시사!')
        self.fails(program('우~라~ 모몽가! 우라! 하치! a 와레! 우라라! 야하!'), '모몽가!')

    def test_concat_utf8_boundary(self):
        code=program('하치와레! 야 하치! 와레! 야하! 하아? 야 야하! 우~라! 야 시사! 하치! 가 와레! 야하!')
        self.check(code, '가'*1365, '가'*1364)
        self.fails(code, '4095바이트', '가'*1365)

    def test_no_newline_prompt_and_partial_output(self):
        events=[]
        async def read():
            self.assertEqual(events, ['입력:'])
            return '42'
        result=asyncio.run(runtime.execute_async(program('우~라! 하치! 입력: 와레! 야하! 얏! 야 뿌 야하! 냠? 야 야하! 우~라~ 모몽가! 우라! 야 우라라! 야하!'),emit=events.append,provider=read))
        self.assertEqual(result['stdout'],'입력:42\n')
        result=self.fails(program('우~라! 하치! 앞 와레! 야하! 우~라~ 뿌르 푸루! 뿌 야하!'), '0으로')
        self.assertEqual(result['stdout'],'앞')

    def test_browser_bundle_matches_tested_runtime(self):
        directory = ROOT / "dist/runtime"
        sources = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))
        self.assertEqual(set(sources), {"usagi/__init__.py", "usagi/numbers.py", "usagi/compiler.py", "interpreter.py"})
        for name, text in sources.items():
            self.assertEqual(text, (directory / name).read_text(encoding="utf-8"), name)

    def check(self, source, expected, stdin=""):
        result = execute(source, stdin)
        self.assertEqual(result["exitCode"], 0, result)
        self.assertEqual(result["stdout"], expected)
        return result

    def fails(self, source, fragment, stdin=""):
        result = execute(source, stdin)
        self.assertEqual(result["exitCode"], 2, result)
        self.assertIn(fragment, result["stderr"])
        return result

    def test_bundled_examples(self):
        samples = json.loads((ROOT / "dist/samples.json").read_text(encoding="utf-8"))
        for key, expected in {"hello":"야하! 우사기 랭귀지에 온 걸 환영해!\n", "sum":"42\n", "function":"뿌르르, 더해 볼게!\n7\n", "count":"0\n1\n4\n9\n16\n", "kevin":"3\n"}.items():
            with self.subTest(example=key):
                self.check(samples[key]["code"], expected, samples[key]["stdin"])

    def test_all_literal_integers(self):
        body = "\n".join(f"우~라~ {encode_integer(i)} 야하!" for i in range(-999, 1000))
        self.check(program(body), "".join(f"{i}\n" for i in range(-999, 1000)))

    def test_int64_exact_input_and_overflow(self):
        source = program("얏! 야 뿌 야하!\n냠? 야 야하!\n우~라~ 야 야하!")
        for value in [-(2**63),2**63-1,9007199254740993]:
            self.check(source, f"{value}\n", str(value))
        self.fails(source, "64비트", str(2**63))
        self.fails(program("얏! 야 뿌 야하! 냠? 야 야하! 우~라~ 야 하! 뿌르 야하!"), "64비트", str(2**63-1))

    def test_division_and_modulo_truncate_toward_zero(self):
        self.check(program("우~라~ 릇뿌뿌릇 푸루! 뿌르르 야하!\n우~라~ 릇뿌뿌릇 푸루루! 뿌르르 야하!"), "-2\n-1\n")
        for op in ("푸루!", "푸루루!"):
            self.fails(program(f"얏! 야 뿌 야하! 냠? 야 야하! 우~라~ 야 {op} 릇뿌뿌르 야하!"), "64비트", str(-(2**63)))
        self.fails(program("우~라~ 뿌르 푸루! 뿌 야하!"), "0으로")

    def test_real_input_cast_and_format(self):
        self.check(program("핫! 야 뿌 야하! 냠? 야 야하! 얏! 야야 야 야하! 우~라~ 야 야하! 우~라~ 야야 야하!"), "-2.75\n-2\n", "-2.75")
        self.check(program("핫! 야 뿌 야하! 냠? 야 야하! 우~라~ 야 야하!"), "1250\n", "1.25e3")
        for invalid in ["nan", "inf", "0x1p2", "1e999", "1e-999"]:
            self.fails(program("핫! 야 뿌 야하! 냠? 야 야하!"), "실수", invalid)

    def test_number_input_strict_integer(self):
        for invalid in ["1.2", "3e2", "2x", "１２"]:
            self.fails(program("얏! 야 뿌 야하! 냠? 야 야하!"), "정수", invalid)

    def test_string_input_and_newline(self):
        self.check(program("하치와레! 야 하치! 와레! 야하! 하아? 야 야하! 우~라~ 야 야하! 우~라~ 하치! a우이!b 와레! 야하!"), "  안녕  \na\nb\n", "  안녕  \n")
        self.check(program("하치와레! 야 하치! x 와레! 야하! 하아? 야 야하! 우~라~ 야 야하!"), "\n", "\n")

    def test_mixed_input_boundaries(self):
        source = program("얏! 야 뿌 야하! 하치와레! 야야 하치! 와레! 야하! 냠? 야 야하! 하아? 야야 야하! 우~라~ 야야 야하!")
        self.check(source, "  글자  \n", "42   \n  글자  \n")
        self.check(source, "\n", "42\n\n")
        self.fails(source, "읽지 않은 숫자", "42 43\n글자\n")
        self.fails(source, "입력이 부족", "42\n")

    def test_input_addresses_are_sequential(self):
        self.check(program("얏! 야 뿌 야하! 야얏! 뿌르르 야야 야하! 냠? 야, 야 야야 야하! 우~라~ 뿌르 야야 야하!"), "9\n", "1 9")

    def test_arrays_bounds_and_negative_size(self):
        self.check(program("야얏! 뿌르 야 야하! 우~라~ 뿌 야 야하!"), "0\n")
        self.fails(program("야얏! 뿌 야 야하! 우~라~ 뿌 야 야하!"), "인덱스")
        self.fails(program("야얏! 릇뿌뿌르 야 야하!"), "음수")
        self.fails(program("야얏! 뿌르 야 야하! 우~라~ 릇뿌뿌르 야 야하!"), "인덱스")

    def test_shadow_and_scope_cleanup_on_continue_break(self):
        source = program("얏! 야 뿌릇 야하! 우쨔? 뿌르르 우랏! 얏! 야 뿌르 야하! 야얏! 뿌릇 야야 야하! 휙! 야하! 우라랏! 우쨔! 우쨔? 뿌르 야얏! 뿌릇 야야 야하! 삐익! 야하! 우쨔! 우~라~ 야 야하!")
        parsed = Parser(lex(source)).parse(); analyze(parsed)
        engine = Interpreter(parsed, ""); asyncio.run(engine.function(parsed.main))
        self.assertEqual("".join(engine.output), "5\n")
        self.assertEqual(engine.array_items, 0)

    def test_repeat_continue_evaluates_condition(self):
        self.check(program("얏! 야 뿌르르르 야하! 푸루룻! 야 야~하! 야 하아! 뿌르 야하! 휙! 야하! 푸루룻? 야 우~라~ 야 야하!"), "0\n")

    def test_frozen_count_remaining_and_sign(self):
        self.check(program("얏! 야 뿌르르르 야하! 우쨔? 야 우~라~ 뿌야! 야하! 야 야~하! 뿌 야하! 우쨔! 갸웃? 야 하아... 우~라~ 하치! zero 와레! 야하! 갸웃!"), "3\n2\n1\nzero\n")

    def test_call_order_and_value_strings(self):
        source = "우나! 하치와레: 읽기 얏! 야 뿌 야하! 냠? 야 야하! 우~나! 야\n" + program("우~라~ 하치와레: 읽기 우라! 우라라! 하아! 하치와레: 읽기 우라! 우라라! 야하!")
        self.check(source, "7\n", "10 3")
        source = "우나! 하치와레: 바꾸기 냠! 하치와레! 야 야 야~하! 하치! 변경 와레! 야하! 우~나! 야\n" + program("하치와레! 야 하치! 원본 와레! 야하! 우~라~ 하치와레: 바꾸기 냠! 야 꿀꺽! 야하! 우~라~ 야 야하!")
        self.check(source, "변경\n원본\n")

    def test_diagnostics_and_partial_output(self):
        self.fails(program("우~라~ 1 야하!"), "main.usagi:2:")
        result = self.fails(program("우~라~ 뿌르 야하! 우~라~ 뿌르 푸루! 뿌 야하!"), "0으로")
        self.assertEqual(result["stdout"], "1\n")
        self.fails(program("얏! 야 뿌 야하! 하아? 야 야하!"), "냠?")

    def test_web_resource_limits(self):
        with patch.object(runtime, "MAX_ARRAY_ITEMS", 3):
            self.fails(program("야얏! 뿌르르 야 야하! 야얏! 뿌르르 야야 야하!"), "1,000,000")
        with patch.object(runtime, "MAX_STEPS", 50):
            self.fails(program("푸루룻! 푸루룻? 뿌르"), "연산 한도")
        with patch.object(runtime, "MAX_OUTPUT", 3):
            self.fails(program("우~라~ 하치! abcd 와레! 야하!"), "64 KiB")

    def test_interactive_provider_and_output_order(self):
        events = []
        values = iter(["  우사기  ", "20"])
        async def read():
            await asyncio.sleep(0)
            value = next(values)
            events.append(("input", value))
            return value
        source = program("하치와레! 야 하치! 와레! 야하! 얏! 야야 뿌 야하! 우~라~ 하치! 이름? 와레! 야하! 하아? 야 야하! 우~라~ 야 야하! 냠? 야야 야하! 우~라~ 야야 야하!")
        result = asyncio.run(runtime.execute_async(source, emit=lambda s: events.append(("output", s)), provider=read))
        self.assertEqual(result["exitCode"], 0, result)
        self.assertEqual(events, [("output", "이름?\n"), ("input", "  우사기  "), ("output", "  우사기  \n"), ("input", "20"), ("output", "20\n")])

    def test_interactive_eof_and_blank_line(self):
        async def eof(): return None
        result = asyncio.run(runtime.execute_async(program("얏! 야 뿌 야하! 냠? 야 야하!"), provider=eof))
        self.assertIn("EOF", result["stderr"])
        async def blank(): return ""
        result = asyncio.run(runtime.execute_async(program("하치와레! 야 하치! 와레! 야하! 하아? 야 야하! 우~라~ 야 야하!"), provider=blank))
        self.assertEqual(result["stdout"], "\n")

    def test_kevin_random_connected_graphs(self):
        source = json.loads((ROOT / "dist/samples.json").read_text(encoding="utf-8"))["kevin"]["code"]
        rng = random.Random(1316)
        for _ in range(12):
            n = rng.randrange(2, 14)
            edges = {(i, i+1) for i in range(1,n)}
            edges.update((a,b) for a in range(1,n) for b in range(a+1,n+1) if rng.random() < .25)
            adjacency = [[] for _ in range(n+1)]
            for a,b in edges: adjacency[a].append(b); adjacency[b].append(a)
            scores = []
            for start in range(1,n+1):
                # Independent distance BFS, separate from the Usagi adjacency representation.
                dist=[-1]*(n+1); dist[start]=0; queue=deque([start])
                while queue:
                    node=queue.popleft()
                    for other in adjacency[node]:
                        if dist[other]<0: dist[other]=dist[node]+1; queue.append(other)
                scores.append(sum(dist[1:]))
            stdin=f"{n} {len(edges)}\n"+"".join(f"{a} {b}\n" for a,b in sorted(edges))
            self.check(source, f"{scores.index(min(scores))+1}\n", stdin)


if __name__ == "__main__":
    unittest.main()
