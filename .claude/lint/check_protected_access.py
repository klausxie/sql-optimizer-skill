#!/usr/bin/env python3
"""
Check for access to protected members from outside the class hierarchy.
Protected members (_x) should only be accessed within the class or its subclasses.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple, Dict


class ProtectedAccessVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.violations: List[Tuple[int, str, str, str]] = []
        self.classes: Dict[str, List[str]] = {}
        self.current_class = None

    def visit_ClassDef(self, node: ast.ClassDef):
        self.classes[node.name] = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for stmt in ast.walk(item):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name):
                                if target.id.startswith("_") and not (target.id.startswith("__") and target.id.endswith("__")):
                                    if target.id not in self.classes[node.name]:
                                        self.classes[node.name].append(target.id)

        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_class = self.current_class
        self.generic_visit(node)
        self.current_class = old_class

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr.startswith("_") and not (node.attr.startswith("__") and node.attr.endswith("__")):
            if isinstance(node.value, ast.Name):
                name = node.value.id
                if name not in ("self", "cls", "super"):
                    if self.current_class and self.current_class in self.classes:
                        if node.attr in self.classes[self.current_class]:
                            self.violations.append((node.lineno, node.attr, self.filepath, "external"))

        self.generic_visit(node)


def check_file(filepath: Path) -> List[Tuple[int, str, str, str]]:
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(filepath))
        visitor = ProtectedAccessVisitor(str(filepath))
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
        print("CLASS-004: Avoid accessing protected members from outside class hierarchy")
        print()
        for lineno, attr, filepath, reason in all_violations:
            print(f"  {filepath}:{lineno} - accessed `{attr}`")
        print()
        print(f"Found {len(all_violations)} violation(s)")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
