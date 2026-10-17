"""Refresh the copied v1 front end and example bundle from the source checkout."""
from pathlib import Path
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parent
SAMPLES = {
    "hello": {"code": "우사기!\n    우~라~ 하치! 야하! 우사기 랭귀지에 온 걸 환영해! 와레! 야하!\n!우사기\n", "stdin": ""},
    "sum": {"code": "우사기!\n    얏! 야 뿌 야하!\n    얏! 야야 뿌 야하!\n    냠? 야, 야야 야하!\n    우~라~ 야 하! 야야 야하!\n!우사기\n", "stdin": "12 30\n"},
    "function": {"code": "우나! 하치와레: 더하기 냠! 얏! 야 냠! 얏! 야야\n    우~라~ 하치! 뿌르르, 더해 볼게! 와레! 야하!\n우~나! 야 하! 야야\n\n우사기!\n    우~라~ 하치와레: 더하기 냠! 뿌르르 냠! 뿌릇 꿀꺽! 야하!\n!우사기\n", "stdin": ""},
    "count": {"code": "우사기!\n    야얏! 뿌릇 하치와레: 숫자들 야하!\n    우쨔? 뿌릇\n        얏! 야 뿌릇 하아! 뿌야! 야하!\n        야 하치와레: 숫자들 야~하! 야 하핫! 야 야하!\n        우~라~ 야 하치와레: 숫자들 야하!\n    우쨔!\n!우사기\n", "stdin": ""},
}

def bundle_runtime():
    """Keep the browser payload byte-for-byte consistent with tested sources."""
    runtime = ROOT / "dist/runtime"
    paths = ("usagi/__init__.py", "usagi/numbers.py", "usagi/compiler.py", "interpreter.py")
    sources = {name: (runtime / name).read_text(encoding="utf-8") for name in paths}
    (runtime / "bundle.json").write_text(json.dumps(sources, ensure_ascii=False) + "\n", encoding="utf-8")
    specification = ROOT.parent / "USAGI_LANGUAGE_SPEC.md"
    if specification.is_file():
        shutil.copyfile(specification, ROOT / "dist/language-spec.md")


if __name__ == "__main__":
    if sys.argv[1:] == ["--runtime-only"]:
        bundle_runtime()
        raise SystemExit(0)
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python build.py <usagi-compiler directory> <kevin example>")
    compiler, kevin = map(Path, sys.argv[1:])
    for name in ("__init__.py", "numbers.py", "compiler.py"):
        shutil.copyfile(compiler / "usagi" / name, ROOT / "dist/runtime/usagi" / name)
    SAMPLES["kevin"] = {"code": kevin.read_text(encoding="utf-8-sig"), "stdin": "5 5\n1 3\n1 4\n2 3\n3 4\n4 5\n"}
    SAMPLES["beer"] = {"code": (compiler / "examples/99_bottles.usagi").read_text(encoding="utf-8"), "stdin": ""}
    (ROOT / "dist/samples.json").write_text(json.dumps(SAMPLES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bundle_runtime()
    print("Shared front end and five examples updated.")
