"""Bounded browser interpreter for the canonical Usagi v1.0 AST.

No user Python or generated native code is executed. The shared compiler owns
lexing, parsing, scopes and type checking; this module evaluates its typed AST.
"""
import json
import math
import re
import asyncio
from array import array
from decimal import Decimal, InvalidOperation
from usagi.compiler import Parser, lex, analyze, CompileError

MIN_INT, MAX_INT = -(2 ** 63), 2 ** 63 - 1
MAX_SOURCE, MAX_INPUT, MAX_OUTPUT = 262144, 1048576, 65536
MAX_ARRAY_ITEMS, MAX_STEPS = 1000000, 20000000
SPACE = " \t\r\n\v\f"


class RuntimeFailure(Exception):
    def __init__(self, token, message):
        self.token, self.message = token, message


class LoopBreak(Exception):
    pass


class LoopContinue(Exception):
    pass


class Input:
    def __init__(self, text, provider=None):
        self.text, self.position, self.pending = text, 0, ""
        self.provider = provider
        self.total_bytes = len(text.encode("utf-8"))

    async def line(self, token):
        if self.position == len(self.text):
            if self.provider is None:
                raise RuntimeFailure(token, "입력이 부족합니다.")
            value = await self.provider()
            if value is None:
                raise RuntimeFailure(token, "입력이 종료되었습니다 (EOF).")
            value = str(value)
            self.total_bytes += len(value.encode("utf-8")) + 1
            if self.total_bytes > MAX_INPUT:
                raise RuntimeFailure(token, "입력이 웹 실행기의 1 MiB 한도를 초과했습니다.")
        else:
            end = self.text.find("\n", self.position)
            if end < 0:
                end = len(self.text)
            value = self.text[self.position:end]
            self.position = min(end + 1, len(self.text))
        if "\0" in value or len(value.encode("utf-8")) > 4095:
            raise RuntimeFailure(token, "입력 한 줄은 NUL 없이 UTF-8 4095바이트까지 가능합니다.")
        return value

    async def string(self, token):
        if self.pending:
            raise RuntimeFailure(token, "같은 줄에 아직 읽지 않은 숫자가 있습니다. 숫자를 모두 읽은 뒤 다음 줄에서 문자열을 입력하세요.")
        return await self.line(token)

    async def number(self, kind, token):
        while not self.pending:
            self.pending = (await self.line(token)).strip(SPACE)
        match = re.match(r"[^ \t\r\n\v\f]+", self.pending)
        value = match.group()
        self.pending = self.pending[match.end():].lstrip(SPACE)
        pattern = r"[+-]?[0-9]+" if kind == "int" else r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
        if not re.fullmatch(pattern, value):
            raise RuntimeFailure(token, "올바른 정수를 입력하세요." if kind == "int" else "올바른 실수를 입력하세요.")
        if kind == "int":
            # Bound conversion work even on runtimes with relaxed int digit limits.
            digits = value.lstrip("+-").lstrip("0")
            if len(digits) > 19:
                raise RuntimeFailure(token, "정수 입력이 64비트 범위를 벗어났습니다.")
            result = int(value)
            if not MIN_INT <= result <= MAX_INT:
                raise RuntimeFailure(token, "정수 입력이 64비트 범위를 벗어났습니다.")
            return result
        result = float(value)
        # strtod reports ERANGE for underflow, including inexact subnormals.
        exact = Decimal(value)
        if (not math.isfinite(result) or
                (exact != 0 and (result == 0 or
                 (abs(result) < float.fromhex("0x1p-1022") and Decimal.from_float(result) != exact)))):
            raise RuntimeFailure(token, "실수 입력이 표현 가능한 범위를 벗어났습니다.")
        return result


class Interpreter:
    def __init__(self, program, stdin, emit=None, provider=None):
        self.program = program
        self.functions = {f.binding: f for f in program.functions}
        self.input = Input(stdin, provider)
        self.output, self.output_size = [], 0
        self.steps, self.array_items = 0, 0
        self.emit = emit

    def tick(self, token):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise RuntimeFailure(token, "웹 실행기의 연산 한도를 초과했습니다.")

    def convert(self, value, kind, token):
        if kind == "real":
            return float(value)
        if kind == "int" and isinstance(value, float):
            if not math.isfinite(value) or value < MIN_INT or value >= 2 ** 63:
                raise RuntimeFailure(token, "실수를 정수로 변환할 수 있는 범위를 벗어났습니다.")
            return int(value)
        return value

    async def address(self, expr, env):
        if expr.kind == "variable":
            return env, expr.binding
        index = await self.expression(expr.left, env)
        data = env[expr.binding]
        if index < 0 or index >= len(data):
            raise RuntimeFailure(expr.token, "배열 인덱스가 범위를 벗어났습니다.")
        return data, index

    async def expression(self, expr, env):
        self.tick(expr.token)
        kind = expr.kind
        if kind == "literal":
            return expr.value if expr.type == "string" else (int(expr.value) if expr.type == "int" else float(expr.value))
        if kind in ("variable", "remaining"):
            return env[expr.binding]
        if kind == "index":
            container, key = await self.address(expr, env)
            return container[key]
        if kind == "call":
            values = [self.convert(await self.expression(a, env), t, a.token) for a, t in zip(expr.args, expr.arg_types)]
            return await self.function(self.functions[expr.binding], values)
        if kind == "stringify":
            value = await self.expression(expr.left, env)
            return format(value, ".15g") if expr.left.type == "real" else str(value)
        left = await self.expression(expr.left, env)
        right = await self.expression(expr.right, env)
        if expr.value == "CONCAT":
            value = left + right
            if len(value.encode("utf-8")) > 4095:
                raise RuntimeFailure(expr.token, "문자열은 UTF-8 4095바이트까지 지원합니다.")
            return value
        if expr.type == "real":
            left, right = float(left), float(right)
        if expr.value in ("DIV", "MOD"):
            if right == 0:
                raise RuntimeFailure(expr.token, "0으로 나눌 수 없습니다.")
            if expr.type == "int" and left == MIN_INT and right == -1:
                raise RuntimeFailure(expr.token, "정수 계산이 64비트 범위를 벗어났습니다.")
        if expr.value == "ADD":
            value = left + right
        elif expr.value == "SUB":
            value = left - right
        elif expr.value == "MUL":
            value = left * right
        elif expr.type == "real":
            value = left / right
        else:
            quotient = (abs(left) // abs(right)) * (-1 if (left < 0) != (right < 0) else 1)
            value = quotient if expr.value == "DIV" else left - quotient * right
        if expr.type == "int" and not MIN_INT <= value <= MAX_INT:
            raise RuntimeFailure(expr.token, "정수 계산이 64비트 범위를 벗어났습니다.")
        if expr.type == "real" and not math.isfinite(value):
            raise RuntimeFailure(expr.token, "실수 계산 결과가 유한한 범위를 벗어났습니다.")
        return value

    async def scoped(self, statements, env):
        # Binding IDs are unique. Remove only this scope's declarations; outer
        # variable/array assignments survive, including break/continue paths.
        bindings = [s.binding for s in statements if s.kind in ("declare", "array_declare")]
        try:
            await self.statements(statements, env)
        finally:
            for binding in bindings:
                value = env.pop(binding, None)
                if isinstance(value, array):
                    self.array_items -= len(value)

    async def statements(self, statements, env):
        for s in statements:
            self.tick(s.token)
            kind = s.kind
            if kind == "declare":
                env[s.binding] = self.convert(await self.expression(s.expr, env), s.type, s.expr.token)
            elif kind == "array_declare":
                size = await self.expression(s.expr, env)
                if size < 0:
                    raise RuntimeFailure(s.token, "배열 크기는 음수일 수 없습니다.")
                if size > MAX_ARRAY_ITEMS - self.array_items:
                    raise RuntimeFailure(s.token, "웹 실행기는 동시에 총 1,000,000개의 배열 원소까지 지원합니다.")
                env[s.binding] = array("q", [0]) * size
                self.array_items += size
            elif kind == "assign":
                container, key = await self.address(s.target, env)
                container[key] = self.convert(await self.expression(s.expr, env), s.type, s.expr.token)
            elif kind == "input":
                container, key = await self.address(s.target, env)
                container[key] = await self.input.string(s.token)
            elif kind == "number_input":
                for target in s.targets:
                    container, key = await self.address(target, env)
                    container[key] = await self.input.number(target.type, s.token)
            elif kind == "output":
                value = await self.expression(s.expr, env)
                text = (format(value, ".15g") if s.expr.type == "real" else str(value)) + ("\n" if s.newline else "")
                self.output_size += len(text.encode("utf-8"))
                if self.output_size > MAX_OUTPUT:
                    raise RuntimeFailure(s.token, "출력이 웹 실행기의 64 KiB 한도를 초과했습니다.")
                self.output.append(text)
                if self.emit:
                    self.emit(text)
            elif kind == "call":
                await self.expression(s.expr, env)
            elif kind == "block":
                await self.scoped(s.body, env)
            elif kind == "sign":
                value = await self.expression(s.expr, env)
                reaction = "POSITIVE" if value > 0 else "NEGATIVE" if value < 0 else "ZERO"
                for branch in s.branches:
                    if branch.token.kind == reaction:
                        await self.scoped(branch.body, env)
                        break
            elif kind == "count":
                count = await self.expression(s.expr, env)
                if count < 0:
                    raise RuntimeFailure(s.token, "반복 횟수는 음수일 수 없습니다.")
                try:
                    while count > 0:
                        self.tick(s.token)
                        env[s.binding] = count
                        try:
                            await self.scoped(s.body, env)
                        except LoopContinue:
                            pass
                        except LoopBreak:
                            break
                        count -= 1
                finally:
                    env.pop(s.binding, None)
            elif kind == "repeat":
                while True:
                    self.tick(s.token)
                    try:
                        await self.scoped(s.body, env)
                    except LoopContinue:
                        pass
                    except LoopBreak:
                        break
                    if await self.expression(s.expr, env) <= 0:
                        break
            elif kind == "break":
                raise LoopBreak()
            elif kind == "continue":
                raise LoopContinue()

    async def function(self, function, values=()):
        env = {p.binding: v for p, v in zip(function.params, values)}
        try:
            await self.statements(function.body, env)
            return await self.expression(function.result, env) if function.result else 0
        finally:
            for value in env.values():
                if isinstance(value, array):
                    self.array_items -= len(value)


async def execute_async(source, stdin="", emit=None, provider=None):
    engine = None
    try:
        if len(source.encode("utf-8")) > MAX_SOURCE or len(stdin.encode("utf-8")) > MAX_INPUT:
            return {"stdout": "", "stderr": "웹 실행기 한도: 코드 256 KiB, 입력 1 MiB입니다.", "exitCode": 2}
        source = source.removeprefix("\ufeff")
        program = Parser(lex(source)).parse()
        analyze(program)
        engine = Interpreter(program, stdin, emit, provider)
        await engine.function(program.main)
        return {"stdout": "".join(engine.output), "stderr": "", "exitCode": 0}
    except CompileError as error:
        message = error.format("main.usagi", source)
    except RuntimeFailure as error:
        message = f"main.usagi:{error.token.line}:{error.token.column}: 실행 오류: {error.message}"
    except (RecursionError, MemoryError):
        message = "프로그램이 웹 실행기의 메모리 또는 식 중첩 한도를 초과했습니다."
    except (ValueError, InvalidOperation, OverflowError):
        message = "표현할 수 없는 숫자 입력 또는 계산 결과입니다."
    return {"stdout": "".join(engine.output) if engine else "", "stderr": message, "exitCode": 2}


def execute(source, stdin="", emit=None):
    """Synchronous entry point for native conformance/unit tests."""
    return asyncio.run(execute_async(source, stdin, emit))


async def run_json_async(source, stdin="", emit=None, provider=None):
    return json.dumps(await execute_async(source, stdin, emit, provider), ensure_ascii=False)
