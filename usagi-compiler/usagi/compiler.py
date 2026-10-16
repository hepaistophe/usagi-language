"""Lexer -> AST -> scope/type checking -> portable C11 generation."""

from dataclasses import dataclass, field
from pathlib import Path
import re

from .numbers import decode_number
from . import __version__


KEYWORDS = {
    "우사기!": "MAIN", "!우사기": "MAIN_END",
    "우나!": "FUNCTION", "우~나!": "RETURN", "야하!": "END",
    "우랏!": "OPEN", "우라랏!": "CLOSE",
    "우라!": "LPAREN", "우라라!": "RPAREN",
    "얏!": "INT", "핫!": "REAL", "얏핫!": "CHAR", "하치와레!": "STRING",
    "얏하핫!": "OLD_STRING", "하치와레:": "NAME_PREFIX",
    "하치!": "STRING_OPEN", "와레!": "STRING_CLOSE",
    "야~하!": "ASSIGN", "하!": "ADD", "하아!": "SUB",
    "하핫!": "MUL", "푸루!": "DIV", "푸루루!": "MOD",
    "하아?": "INPUT", "우~라~": "OUTPUT",
    "갸웃?": "SIGN", "갸웃!": "SIGN_END",
    "야호!": "POSITIVE", "하아...": "ZERO", "우우...": "NEGATIVE",
    "우쨔?": "COUNT", "우쨔!": "COUNT_END", "뿌야!": "REMAINING",
    "푸루룻!": "REPEAT", "푸루룻?": "REPEAT_TEST",
    "삐익!": "BREAK", "휙!": "CONTINUE",
    "냠!": "FEED", "꿀꺽!": "SWALLOW",
}

REACTIONS = {"POSITIVE", "ZERO", "NEGATIVE"}
CLOSERS = {"MAIN_END", "RETURN", "CLOSE", "SIGN_END", "COUNT_END", "REPEAT_TEST"}


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line: int
    column: int


class CompileError(Exception):
    def __init__(self, token: Token, message: str):
        self.token = token
        self.message = message
        super().__init__(message)

    def format(self, path: str, source: str) -> str:
        lines = source.splitlines()
        line = lines[self.token.line - 1] if self.token.line <= len(lines) else ""
        # Preserve tabs so the caret tracks the source in terminals.
        padding = "".join("\t" if c == "\t" else " " for c in line[:self.token.column - 1])
        return f"{path}:{self.token.line}:{self.token.column}: 오류: {self.message}\n  {line}\n  {padding}^"


def lex(source: str) -> list[Token]:
    tokens: list[Token] = []
    lines = source.splitlines()
    for line_number, line in enumerate(lines, 1):
        position = 0
        while position < len(line):
            if line[position].isspace():
                position += 1
                continue
            start = position
            if line.startswith("하치!", position):
                end = line.find("와레!", position + 3)
                token = Token("TEXT", "", line_number, start + 1)
                if end < 0:
                    raise CompileError(token, "문자열을 닫는 와레!가 같은 줄에 필요합니다.")
                text = line[position + 3:end]
                # One adjacent ASCII space on each side is syntax padding.
                text = text.removeprefix(" ").removesuffix(" ")
                if "\0" in text or len(text.encode("utf-8")) > 4095:
                    raise CompileError(token, "문자열은 NUL 없이 UTF-8 4095바이트까지 지원합니다.")
                position = end + 3
                if position < len(line) and not line[position].isspace():
                    raise CompileError(token, "와레! 뒤의 문법 토큰은 공백으로 구분하세요.")
                tokens.append(Token("TEXT", text, line_number, start + 1))
                continue
            match = re.match(r"\S+", line[position:])
            text = match.group()
            position += len(text)
            if text == "하치와레:":
                words = []
                while position < len(line):
                    next_match = re.match(r"\s*(\S+)", line[position:])
                    if next_match is None:
                        break
                    word = next_match.group(1)
                    if (word in KEYWORDS or re.fullmatch(r"[뿌르릇~.]+", word) or word.startswith("하치!")
                            or (words and re.fullmatch(r"야+", word))):
                        break
                    pattern = r"[A-Za-z가-힣_][A-Za-z가-힣_0-9]*" if not words else r"[A-Za-z가-힣_0-9]+"
                    if not re.fullmatch(pattern, word):
                        raise CompileError(Token("INVALID", word, line_number, position + 1),
                                           "이름에는 한글·영문·숫자·밑줄과 단어 사이 공백을 사용하세요. 숫자로 시작할 수 없습니다.")
                    words.append(word)
                    position += next_match.end()
                if not words:
                    raise CompileError(Token("NAME", "", line_number, start + 1),
                                       "하치와레: 뒤 같은 줄에 사용자 이름이 필요합니다.")
                tokens.append(Token("NAME", " ".join(words), line_number, start + 1))
                continue
            kind = KEYWORDS.get(text)
            if kind is None:
                if re.fullmatch(r"야+", text):
                    kind = "SHORT_NAME"
                elif re.fullmatch(r"[뿌르릇~.]+", text):
                    kind = "NUMBER"
                else:
                    token = Token("INVALID", text, line_number, start + 1)
                    raise CompileError(token, f"알 수 없는 토큰 {text!r}. 야 반복 변수명 외의 사용자 이름 앞에는 하치와레:를 붙이고 토큰은 공백으로 구분하세요.")
            if kind == "OLD_STRING":
                raise CompileError(Token(kind, text, line_number, start + 1), "문자열형 얏하핫!은 하치와레!로 바뀌었습니다.")
            if kind == "STRING_CLOSE":
                raise CompileError(Token(kind, text, line_number, start + 1), "문자열 시작 하치! 없이 와레!를 사용할 수 없습니다.")
            tokens.append(Token(kind, text, line_number, start + 1))
    eof_line = len(lines) + 1 if source.endswith(("\n", "\r")) else max(1, len(lines))
    eof_column = 1 if not lines or source.endswith(("\n", "\r")) else len(lines[-1]) + 1
    tokens.append(Token("EOF", "", eof_line, eof_column))
    return tokens


@dataclass
class Expr:
    token: Token
    kind: str
    value: str = ""
    left: "Expr | None" = None
    right: "Expr | None" = None
    type: str = ""
    binding: str = ""
    args: list["Expr"] = field(default_factory=list)
    arg_types: list[str] = field(default_factory=list)


@dataclass
class Statement:
    token: Token
    kind: str
    name: Token | None = None
    expr: Expr | None = None
    body: list["Statement"] = field(default_factory=list)
    type: str = ""
    binding: str = ""
    branches: list["Branch"] = field(default_factory=list)
    needs_continue: bool = False


@dataclass
class Branch:
    token: Token
    body: list[Statement]


@dataclass
class Function:
    token: Token
    name: str
    body: list[Statement]
    result: Expr | None = None
    type: str = ""
    binding: str = ""
    params: list["Parameter"] = field(default_factory=list)


@dataclass
class Parameter:
    name: Token
    type: str
    binding: str = ""


@dataclass
class Program:
    functions: list[Function]
    main: Function


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def take(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def expect(self, kind: str, message: str) -> Token:
        if self.current.kind != kind:
            raise CompileError(self.current, message)
        return self.take()

    def variable_name(self) -> Token:
        if self.current.kind not in ("NAME", "SHORT_NAME"):
            raise CompileError(self.current, "변수 이름은 야 반복 이름 또는 하치와레: 이름으로 작성하세요.")
        return self.take()

    def parse(self) -> Program:
        functions = []
        main = None
        while self.current.kind != "EOF":
            token = self.take()
            if token.kind == "MAIN":
                if main is not None:
                    raise CompileError(token, "우사기! 메인은 하나만 선언할 수 있습니다.")
                body = self.statements("MAIN_END")
                self.expect("MAIN_END", "메인을 닫고 0을 반환하는 !우사기가 필요합니다.")
                main = Function(token, "우사기!", body, type="int", binding="main")
            elif token.kind == "FUNCTION":
                name = self.current
                if name.kind != "NAME":
                    raise CompileError(name, "우나! 뒤에는 하치와레: 함수명이 필요합니다. 메인은 우사기!로 시작하세요.")
                self.take()
                params = []
                while self.current.kind == "FEED":
                    self.take()
                    parameter_type = self.current
                    if parameter_type.kind not in ("INT", "REAL", "STRING"):
                        raise CompileError(parameter_type, "선언의 냠! 뒤에는 얏!, 핫!, 하치와레! 자료형과 매개변수 이름이 필요합니다.")
                    self.take()
                    params.append(Parameter(self.variable_name(), {"INT": "int", "REAL": "real", "STRING": "string"}[parameter_type.kind]))
                body = self.statements("RETURN")
                self.expect("RETURN", "함수를 닫는 우~나! 반환값이 필요합니다.")
                result = self.expression()
                functions.append(Function(name, name.text, body, result, params=params))
            else:
                raise CompileError(token, "최상위에는 우사기! 메인 또는 우나! 함수 선언만 올 수 있습니다.")
            # Closing markers already delimit the function; a trailing END is optional.
            if self.current.kind == "END":
                self.take()
        if main is None:
            raise CompileError(self.current, "우사기! … !우사기 메인이 필요합니다.")
        return Program(functions, main)

    def statements(self, until: str | set[str]) -> list[Statement]:
        stops = {until} if isinstance(until, str) else until
        closing = {"MAIN_END": "!우사기", "RETURN": "우~나! 반환값", "CLOSE": "우라랏!",
                   "SIGN_END": "갸웃!", "COUNT_END": "우쨔!", "REPEAT_TEST": "푸루룻? 조건식"}
        expected = next((closing[k] for k in closing if k in stops), "닫는 표식")
        body = []
        while self.current.kind not in stops | {"EOF"}:
            if self.current.kind in CLOSERS | REACTIONS | {"FUNCTION", "MAIN"}:
                raise CompileError(self.current, f"현재 본문을 닫는 {expected}가 필요합니다. 함수는 중첩 선언할 수 없습니다.")
            body.append(self.statement())
        return body

    def optional_end(self) -> None:
        if self.current.kind == "END":
            self.take()

    def sign_statement(self, token: Token) -> Statement:
        value = self.expression()
        branches = []
        seen = set()
        while self.current.kind in REACTIONS:
            reaction = self.take()
            if reaction.kind in seen:
                raise CompileError(reaction, f"{reaction.text} 반응을 중복해서 작성할 수 없습니다.")
            seen.add(reaction.kind)
            branches.append(Branch(reaction, self.statements(REACTIONS | {"SIGN_END"})))
        if not branches:
            raise CompileError(self.current, "갸웃? 뒤에는 야호!, 하아..., 우우... 반응이 적어도 하나 필요합니다.")
        self.expect("SIGN_END", "분기를 닫는 갸웃!이 필요합니다.")
        self.optional_end()
        return Statement(token, "sign", expr=value, branches=branches)

    def block(self) -> list[Statement]:
        self.expect("OPEN", "블록은 우랏!으로 시작합니다.")
        body = self.statements("CLOSE")
        self.expect("CLOSE", "블록을 닫는 우라랏!이 필요합니다.")
        return body

    def statement(self) -> Statement:
        token = self.current
        if token.kind == "OPEN":
            return Statement(token, "block", body=self.block())
        self.take()
        if token.kind == "SIGN":
            return self.sign_statement(token)
        if token.kind == "COUNT":
            value = self.expression()
            body = self.statements("COUNT_END")
            self.expect("COUNT_END", "횟수 반복을 닫는 우쨔!가 필요합니다.")
            self.optional_end()
            return Statement(token, "count", expr=value, body=body)
        if token.kind == "REPEAT":
            body = self.statements("REPEAT_TEST")
            self.expect("REPEAT_TEST", "조건 반복을 닫는 푸루룻? 조건식이 필요합니다.")
            value = self.expression()
            self.optional_end()
            return Statement(token, "repeat", expr=value, body=body)
        if token.kind == "CHAR":
            raise CompileError(token, "문자형 리터럴 문법은 아직 미정이며 현재 버전에서는 지원하지 않습니다.")
        if token.kind in ("INT", "REAL", "STRING"):
            name = self.variable_name()
            result = Statement(token, "declare", name, self.expression(), type={"INT": "int", "REAL": "real", "STRING": "string"}[token.kind])
        elif token.kind in ("NAME", "SHORT_NAME"):
            if self.current.kind in ("LPAREN", "FEED"):
                result = Statement(token, "call", expr=self.call(token))
            else:
                self.expect("ASSIGN", "변수에 다시 대입하려면 야~하!를 사용하세요.")
                result = Statement(token, "assign", token, self.expression())
        elif token.kind == "INPUT":
            result = Statement(token, "input", self.variable_name())
        elif token.kind == "OUTPUT":
            result = Statement(token, "output", expr=self.expression())
        elif token.kind in ("BREAK", "CONTINUE"):
            result = Statement(token, token.kind.lower())
        elif token.kind == "REMAINING":
            raise CompileError(token, "뿌야!는 읽기 전용 남은 횟수이며 대입하거나 입력받을 수 없습니다.")
        else:
            raise CompileError(token, "선언, 대입, 입출력, 블록, 제어문 또는 함수 호출문이 필요합니다.")
        self.expect("END", "문장 끝에 야하!가 필요합니다.")
        return result

    def call(self, name: Token) -> Expr:
        if name.kind != "NAME":
            raise CompileError(name, "함수 이름에는 항상 하치와레:가 필요합니다. 야 반복 예외는 변수에만 적용합니다.")
        if self.current.kind == "LPAREN":
            self.take()
            self.expect("RPAREN", "괄호 호출은 인자 없을 때만 사용합니다. 값은 냠! 값 … 꿀꺽!으로 넘기세요.")
            return Expr(name, "call", name.text)
        args = []
        while self.current.kind == "FEED":
            self.take()
            args.append(self.expression())
        self.expect("SWALLOW", "먹이기 호출을 끝내는 꿀꺽!이 필요합니다.")
        return Expr(name, "call", name.text, args=args)

    def expression(self, minimum: int = 0) -> Expr:
        token = self.take()
        if token.kind == "NUMBER":
            try:
                number_type, spelling = decode_number(token.text)
            except ValueError as error:
                raise CompileError(token, str(error)) from error
            left = Expr(token, "literal", spelling, type=number_type)
        elif token.kind == "TEXT":
            left = Expr(token, "literal", token.text, type="string")
        elif token.kind == "REMAINING":
            left = Expr(token, "remaining", type="int")
        elif token.kind in ("NAME", "SHORT_NAME"):
            if self.current.kind in ("LPAREN", "FEED"):
                left = self.call(token)
            else:
                left = Expr(token, "variable", token.text)
        elif token.kind == "LPAREN":
            left = self.expression()
            self.expect("RPAREN", "괄호를 닫는 우라라!가 필요합니다.")
        else:
            raise CompileError(token, "숫자, 문자열, 하치와레: 이름 또는 우라! … 우라라! 식이 필요합니다.")
        precedence = {"ADD": 1, "SUB": 1, "MUL": 2, "DIV": 2, "MOD": 2}
        while precedence.get(self.current.kind, -1) >= minimum:
            operator = self.take()
            right = self.expression(precedence[operator.kind] + 1)
            left = Expr(operator, "binary", operator.kind, left, right)
        return left


def analyze(program: Program) -> None:
    functions: dict[str, Function] = {}
    states: dict[str, str] = {}
    counter = 0
    for index, function in enumerate(program.functions, 1):
        if function.name in functions:
            raise CompileError(function.token, f"함수 {function.name!r}를 중복 선언했습니다.")
        function.binding = f"us_f{index}"
        functions[function.name] = function

    def analyze_function(function: Function) -> None:
        if states.get(function.name) == "done":
            return
        states[function.name] = "visiting"
        scopes: list[dict[str, tuple[str, str]]] = [{}]
        loops: list[Statement] = []
        counted_loops: list[Statement] = []
        nonlocal counter
        for parameter in function.params:
            if parameter.name.text in scopes[0]:
                raise CompileError(parameter.name, "같은 이름의 매개변수를 중복 선언할 수 없습니다.")
            counter += 1
            parameter.binding = f"us_v{counter}"
            scopes[0][parameter.name.text] = (parameter.type, parameter.binding)

        def lookup(token: Token) -> tuple[str, str]:
            for scope in reversed(scopes):
                if token.text in scope:
                    return scope[token.text]
            raise CompileError(token, f"선언되지 않은 변수 {token.text!r}입니다.")

        def expression(expr: Expr) -> str:
            if expr.kind == "variable":
                expr.type, expr.binding = lookup(expr.token)
            elif expr.kind == "remaining":
                if not counted_loops:
                    raise CompileError(expr.token, "뿌야!는 같은 함수의 우쨔? 횟수 반복 안에서만 사용할 수 있습니다.")
                expr.binding = counted_loops[-1].binding
            elif expr.kind == "call":
                callee = functions.get(expr.value)
                if callee is None:
                    raise CompileError(expr.token, f"선언되지 않은 함수 {expr.value!r}입니다.")
                if len(expr.args) != len(callee.params):
                    raise CompileError(expr.token, f"함수 {expr.value!r}는 인자 {len(callee.params)}개가 필요하지만 {len(expr.args)}개를 받았습니다.")
                if states.get(callee.name) == "visiting":
                    raise CompileError(expr.token, "재귀·순환 호출은 현재 지원하지 않습니다. 반환형 추론에 순환이 있습니다.")
                analyze_function(callee)
                for argument, parameter in zip(expr.args, callee.params):
                    assignable(parameter.type, argument)
                expr.arg_types = [p.type for p in callee.params]
                expr.type, expr.binding = callee.type, callee.binding
            elif expr.kind == "binary":
                left, right = expression(expr.left), expression(expr.right)
                if "string" in (left, right):
                    raise CompileError(expr.token, "문자열 산술·연결 연산은 아직 지원하지 않습니다.")
                if expr.value == "MOD" and (left != "int" or right != "int"):
                    raise CompileError(expr.token, "푸루루! 나머지 연산은 정수끼리만 사용할 수 있습니다.")
                expr.type = "real" if "real" in (left, right) else "int"
            return expr.type

        def assignable(target: str, expr: Expr) -> None:
            actual = expression(expr)
            if (target == "string") != (actual == "string"):
                raise CompileError(expr.token, "문자열과 숫자 사이의 자동 변환은 아직 지원하지 않습니다.")

        def nested(statements: list[Statement]) -> None:
            scopes.append({})
            visit(statements)
            scopes.pop()

        def numeric(expr: Expr) -> str:
            actual = expression(expr)
            if actual == "string":
                raise CompileError(expr.token, "분기·반복 조건은 정수 또는 실수여야 합니다.")
            return actual

        def visit(statements: list[Statement]) -> None:
            nonlocal counter
            for statement in statements:
                if statement.kind == "block":
                    nested(statement.body)
                elif statement.kind == "sign":
                    numeric(statement.expr)
                    for branch in statement.branches:
                        nested(branch.body)
                elif statement.kind in ("count", "repeat"):
                    actual = numeric(statement.expr)
                    if statement.kind == "count" and actual != "int":
                        raise CompileError(statement.expr.token, "우쨔? 반복 횟수는 정수여야 합니다. 실수는 자동 변환하지 않습니다.")
                    counter += 1
                    statement.binding = f"us_loop{counter}"
                    loops.append(statement)
                    if statement.kind == "count":
                        counted_loops.append(statement)
                    nested(statement.body)
                    if statement.kind == "count":
                        counted_loops.pop()
                    loops.pop()
                elif statement.kind in ("break", "continue"):
                    if not loops:
                        raise CompileError(statement.token, f"{statement.token.text}는 같은 함수의 반복문 안에서만 사용할 수 있습니다.")
                    if statement.kind == "continue" and loops[-1].kind == "repeat":
                        loops[-1].needs_continue = True
                        statement.binding = loops[-1].binding
                elif statement.kind == "declare":
                    if statement.name.text in scopes[-1]:
                        raise CompileError(statement.name, "같은 블록에서 변수를 중복 선언할 수 없습니다.")
                    assignable(statement.type, statement.expr)
                    counter += 1
                    statement.binding = f"us_v{counter}"
                    scopes[-1][statement.name.text] = (statement.type, statement.binding)
                elif statement.kind in ("assign", "input"):
                    statement.type, statement.binding = lookup(statement.name)
                    if statement.expr is not None:
                        assignable(statement.type, statement.expr)
                elif statement.kind in ("output", "call"):
                    expression(statement.expr)

        visit(function.body)
        if function.result is not None:
            function.type = expression(function.result)
        states[function.name] = "done"

    for function in program.functions:
        analyze_function(function)
    analyze_function(program.main)


def c_string(text: str) -> str:
    # Fixed-width octal escapes prevent quote, backslash, trigraph and UTF-8 ambiguity.
    return '"' + "".join(f"\\{byte:03o}" for byte in text.encode("utf-8")) + '"'


def generate_c(program: Program, path: str) -> str:
    runtime = Path(__file__).with_name("runtime.c").read_text(encoding="utf-8")
    output = [f"/* Generated by Usagi {__version__}. Self-contained C11. */", runtime,
              f"const char *us_source = {c_string(path)};"]
    counter = 0
    depth = 1
    ctype = {"int": "int64_t", "real": "double", "string": "us_string"}
    families = {"int": "i", "real": "r", "string": "s"}
    for function in program.functions:
        parameters = ", ".join(f"{ctype[p.type]} {p.binding}" for p in function.params) or "void"
        output.append(f"{ctype[function.type]} {function.binding}({parameters});")

    def emit(line: str) -> None:
        output.append("    " * depth + line)

    def converted(target: str, expr: Expr, value: str) -> str:
        if target == "real":
            return f"((double)({value}))"
        if target == "int" and expr.type == "real":
            return f"us_real_to_int({value}, {expr.token.line}, {expr.token.column})"
        return value

    def expression(expr: Expr) -> str:
        nonlocal counter
        if expr.kind == "literal":
            if expr.type == "string":
                return f"us_string_literal({c_string(expr.value)}, {expr.token.line}, {expr.token.column})"
            return f"((int64_t)({expr.value}))" if expr.type == "int" else expr.value
        if expr.kind in ("variable", "remaining"):
            return expr.binding
        if expr.kind == "call":
            arguments = []
            for argument, target in zip(expr.args, expr.arg_types):
                value = converted(target, argument, expression(argument))
                counter += 1
                argument_name = f"us_t{counter}"
                emit(f"{ctype[target]} {argument_name} = {value};")
                arguments.append(argument_name)
            counter += 1
            name = f"us_t{counter}"
            # Materialize each call before the next one: input/output order is defined.
            emit(f"{ctype[expr.type]} {name} = {expr.binding}({', '.join(arguments)});")
            return name
        left, right = expression(expr.left), expression(expr.right)
        counter += 1
        name = f"us_t{counter}"
        family = "i" if expr.type == "int" else "r"
        if expr.type == "real":
            left, right = f"((double)({left}))", f"((double)({right}))"
        emit(f"{ctype[expr.type]} {name} = us_{family}_{expr.value.lower()}({left}, {right}, {expr.token.line}, {expr.token.column});")
        return name

    def visit(statements: list[Statement]) -> None:
        nonlocal depth, counter
        for statement in statements:
            kind = statement.kind
            if kind == "block":
                emit("{")
                depth += 1
                visit(statement.body)
                depth -= 1
                emit("}")
            elif kind == "sign":
                value = expression(statement.expr)
                counter += 1
                name = f"us_t{counter}"
                emit(f"{ctype[statement.expr.type]} {name} = {value};")
                for index, branch in enumerate(statement.branches):
                    comparison = {"POSITIVE": ">", "ZERO": "==", "NEGATIVE": "<"}[branch.token.kind]
                    emit(f"{'if' if index == 0 else 'else if'} ({name} {comparison} 0) {{")
                    depth += 1
                    visit(branch.body)
                    depth -= 1
                    emit("}")
            elif kind == "count":
                # Freeze the count before entering the loop, including any outer counter.
                value = expression(statement.expr)
                emit("{")
                depth += 1
                name = statement.binding
                emit(f"int64_t {name} = us_count({value}, {statement.token.line}, {statement.token.column});")
                emit(f"for (; {name} > 0; --{name}) {{")
                depth += 1
                visit(statement.body)
                depth -= 1
                emit("}")
                depth -= 1
                emit("}")
            elif kind == "repeat":
                emit("while (1) {")
                depth += 1
                emit("{")
                depth += 1
                visit(statement.body)
                depth -= 1
                emit("}")
                if statement.needs_continue:
                    emit(f"{statement.binding}_test: ;")
                value = expression(statement.expr)
                emit(f"if (!(({value}) > 0)) break;")
                depth -= 1
                emit("}")
            elif kind == "break":
                emit("break;")
            elif kind == "continue":
                emit(f"goto {statement.binding}_test;" if statement.binding else "continue;")
            elif kind in ("declare", "assign"):
                value = expression(statement.expr)
                value = converted(statement.type, statement.expr, value)
                prefix = ctype[statement.type] + " " if kind == "declare" else ""
                emit(f"{prefix}{statement.binding} = {value};")
                emit(f"(void){statement.binding};")
            elif kind == "input":
                family = families[statement.type]
                emit(f"{statement.binding} = us_read_{family}({statement.token.line}, {statement.token.column});")
            elif kind == "output":
                value = expression(statement.expr)
                family = families[statement.expr.type]
                emit(f"us_print_{family}({value}, {statement.token.line}, {statement.token.column});")
            elif kind == "call":
                value = expression(statement.expr)
                emit(f"(void){value};")

    for function in [*program.functions, program.main]:
        return_type = "int" if function is program.main else ctype[function.type]
        parameters = ", ".join(f"{ctype[p.type]} {p.binding}" for p in function.params) or "void"
        output.append(f"{return_type} {function.binding}({parameters}) {{")
        for parameter in function.params:
            emit(f"(void){parameter.binding};")
        visit(function.body)
        value = expression(function.result) if function.result is not None else "0"
        emit(f"return {value};")
        output.append("}")
    return "\n".join(output) + "\n"


def compile_source(source: str, path: str = "<source>") -> str:
    tokens = lex(source)
    try:
        body = Parser(tokens).parse()
        analyze(body)
        return generate_c(body, path)
    except RecursionError as error:
        raise CompileError(tokens[0], "식 또는 블록이 너무 깊게 중첩되어 있습니다. 더 작은 식으로 나누세요.") from error
