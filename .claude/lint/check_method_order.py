#!/usr/bin/env python3
"""
Check method ordering in Python classes.
Method order should follow this sequence:
1. __new__ (static method)
2. __init__
3. __post_init__
4. Other dunder methods (__str__, __repr__, etc.)
5. @property
6. @staticmethod
7. @classmethod
8. Public methods
9. Protected methods (_x)
10. Private methods (__x)
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple


def get_method_category(item: ast.FunctionDef) -> int:
    name = item.name
    decorators = [d.__class__.__name__ for d in item.decorator_list]

    if name == "__new__":
        return 0
    if name == "__init__":
        return 1
    if name == "__post_init__":
        return 2
    if name.startswith("__") and name.endswith("__"):
        return 3
    if "property" in decorators:
        return 4
    if "staticmethod" in decorators:
        return 5
    if "classmethod" in decorators:
        return 6
    if name.startswith("__"):
        return 9
    if name.startswith("_"):
        return 8
    return 7


class MethodOrderVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.violations: List[Tuple[int, str, str, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append((item.lineno, item.name, get_method_category(item)))

        if not methods:
            self.generic_visit(node)
            return

        categories = [m[2] for m in methods]
        expected_order = sorted(categories)

        if categories != expected_order:
            for i, cat in enumerate(categories):
                if cat != expected_order[i]:
                    self.violations.append((methods[i][0], methods[i][1], self.filepath, node.name))
                    break

        self.generic_visit(node)


def check_file(filepath: Path) -> List[Tuple[int, str, str, str]]:
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(filepath))
        visitor = MethodOrderVisitor(str(filepath))
        visitor.visit(tree)
        return visitor.violations
    except SyntaxError:
        return []


def main() -> int:
    staged = sys.argv[1:]
    py_files = [Path(f) for f in staged if f.endswith(".py")]

    if not py_files:
        return 0

    all_violations = []
    for f in py_files:
        violations = check_file(f)
        all_violations.extend(violations)

    if all_violations:
        print(
            "CLASS-003: Method order should follow: __new__ -> __init__ -> __post_init__ -> __xxx__ -> @property -> @staticmethod -> @classmethod -> public -> _protected -> __private"
        )
        print()
        for lineno, name, filepath, classname in all_violations:
            print(f"  {filepath}:{lineno} - {classname}.{name}()")
        print()
        print(f"Found {len(all_violations)} violation(s)")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
