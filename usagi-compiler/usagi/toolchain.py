"""Discover Clang without changing the user's PATH or compiler installation."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


class ToolchainError(Exception):
    pass


def find_clang(explicit: str | None = None) -> str:
    requested = explicit or os.environ.get("USAGI_CC")
    if requested:
        found = shutil.which(requested)
        if found:
            return found
        if Path(requested).is_file():
            return str(Path(requested).resolve())
        raise ToolchainError(f"지정한 Clang 실행 파일을 찾을 수 없습니다: {requested}")
    found = shutil.which("clang")
    if found:
        return found
    if os.name == "nt":
        program_files = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        vswhere = program_files / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        if vswhere.is_file():
            try:
                result = subprocess.run(
                    [str(vswhere), "-all", "-products", "*", "-format", "json", "-utf8"],
                    capture_output=True, encoding="utf-8-sig", errors="replace", timeout=15,
                )
                instances = json.loads(result.stdout) if result.returncode == 0 else []
                for instance in instances:
                    if not instance.get("isComplete", True):
                        continue
                    root = Path(instance["installationPath"]) / "VC" / "Tools" / "Llvm"
                    for relative in ("x64/bin/clang.exe", "bin/clang.exe"):
                        candidate = root / relative
                        if candidate.is_file():
                            return str(candidate)
            except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
                pass
    raise ToolchainError(
        "Clang을 찾을 수 없습니다. Visual Studio Installer의 'Windows용 C++ Clang 도구'를 설치하거나 "
        "--cc에 clang.exe 전체 경로를 지정하세요. check와 emit-c는 Clang 없이 사용할 수 있습니다."
    )


def build(c_source: str, output: Path, cc: str | None = None) -> Path:
    compiler = find_clang(cc)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Compile beside the destination, then replace only after successful linking.
    # Failed builds never destroy an existing executable.
    with tempfile.TemporaryDirectory(prefix=".usagi-build-", dir=output.parent) as directory:
        temporary = Path(directory)
        c_path = temporary / "program.c"
        exe_path = temporary / ("program.exe" if os.name == "nt" else "program")
        c_path.write_text(c_source, encoding="utf-8")
        command = [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", str(c_path), "-o", str(exe_path)]
        if os.name != "nt":
            command.append("-lm")
        try:
            result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
        except subprocess.TimeoutExpired as error:
            raise ToolchainError("C 컴파일이 제한 시간 60초를 초과했습니다.") from error
        except OSError as error:
            raise ToolchainError(f"Clang을 실행하지 못했습니다: {error}") from error
        if result.returncode:
            raise ToolchainError(f"C 컴파일 또는 링크 실패 (종료 코드 {result.returncode}):\n{result.stderr.strip()}")
        if not exe_path.is_file():
            raise ToolchainError("Clang이 실행 파일을 생성하지 않았습니다.")
        os.replace(exe_path, output)
    return output
