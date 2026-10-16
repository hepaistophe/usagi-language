import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from . import __version__
from .compiler import CompileError, compile_source
from .toolchain import ToolchainError, build


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="usagic", description="우사기 소스를 검사하고 C11 및 실행 파일로 컴파일합니다.")
    parser.add_argument("--version", action="version", version=f"usagic {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("check", "문법과 타입 검사"), ("emit-c", "독립적으로 컴파일 가능한 C 소스 생성"),
        ("build", "네이티브 실행 파일 생성"), ("run", "임시 실행 파일로 컴파일한 뒤 실행"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("source", type=Path, help="UTF-8 .usagi 파일")
        if name == "check":
            command.add_argument("--json", action="store_true", help="에디터용 JSON 진단 출력")
            command.add_argument("--stdin", action="store_true", help="파일 대신 표준 입력의 소스를 검사")
        if name in ("emit-c", "build"):
            command.add_argument("-o", "--output", type=Path, help="출력 경로")
        if name in ("build", "run"):
            command.add_argument("--cc", help="Clang 실행 파일 경로")
    args = parser.parse_args(argv)
    source = ""
    source_path = args.source.resolve()
    machine_readable = getattr(args, "json", False)

    def report(message: str, token=None) -> None:
        if machine_readable:
            diagnostic = {"message": message, "line": token.line if token else 1,
                          "column": token.column if token else 1, "length": max(1, len(token.text)) if token else 1}
            print(json.dumps({"ok": False, "diagnostics": [diagnostic]}, ensure_ascii=False))
        else:
            print(message, file=sys.stderr)

    try:
        source = sys.stdin.read().removeprefix("\ufeff") if getattr(args, "stdin", False) else source_path.read_text(encoding="utf-8-sig")
        generated = compile_source(source, str(source_path))
        if args.command == "check":
            if machine_readable:
                print(json.dumps({"ok": True, "diagnostics": []}))
            else:
                print(f"검사 통과: {source_path}")
            return 0
        if args.command in ("emit-c", "build"):
            suffix = ".c" if args.command == "emit-c" else (".exe" if os.name == "nt" else ".out")
            output = (args.output or source_path.with_suffix(suffix)).resolve()
            if output == source_path or (output.exists() and output.samefile(source_path)):
                raise ToolchainError("출력 경로로 입력 소스 파일을 덮어쓸 수 없습니다.")
            if args.command == "emit-c":
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(generated, encoding="utf-8")
            else:
                build(generated, output, args.cc)
            print(f"생성 완료: {output}")
            return 0
        with tempfile.TemporaryDirectory(prefix="usagi-run-") as directory:
            executable = Path(directory) / ("program.exe" if os.name == "nt" else "program")
            build(generated, executable, args.cc)
            # Inherit the console, including interactive stdin; no shell is used.
            process = subprocess.Popen([str(executable)])
            try:
                return process.wait()
            except KeyboardInterrupt:
                # A program may now loop forever. Reap it before cleaning its .exe.
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                raise
    except CompileError as error:
        report(error.message if machine_readable else error.format(str(source_path), source), error.token)
    except (OSError, UnicodeError, ToolchainError) as error:
        report(f"오류: {error}")
    except KeyboardInterrupt:
        print("\n실행을 중단했습니다.", file=sys.stderr)
        return 130
    return 1
