import ast
from pathlib import Path

root = Path(__file__).parent
for path in root.rglob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
print("OK: Python AST validation passed")
