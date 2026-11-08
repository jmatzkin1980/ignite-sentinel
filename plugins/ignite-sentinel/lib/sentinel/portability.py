from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


OPTIONAL_THIRD_PARTY_IMPORTS = {
    "lancedb",
    "mcp",
    "model2vec",
    "sentence_transformers",
}


@dataclass(frozen=True)
class ImportViolation:
    path: str
    line: int
    module: str
    reason: str

    def format(self) -> str:
        return f"{self.path}:{self.line} imports {self.module} ({self.reason})"


def stdlib_purity_violations(package_dir: Path) -> list[ImportViolation]:
    package_dir = package_dir.resolve()
    violations: list[ImportViolation] = []
    stdlib_names = set(sys.stdlib_module_names)
    for source in sorted(package_dir.rglob("*.py")):
        relative = source.relative_to(package_dir.parent).as_posix()
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for imported in _iter_imports(tree):
            if imported.level:
                continue
            module = imported.module
            top = module.split(".", 1)[0]
            if top in stdlib_names or _is_local_module(module, source, package_dir):
                continue
            if top in OPTIONAL_THIRD_PARTY_IMPORTS and imported.guarded:
                continue
            if top in OPTIONAL_THIRD_PARTY_IMPORTS:
                reason = "optional third-party import is not guarded by try/except"
            else:
                reason = "third-party import is not in the optional allowlist"
            violations.append(ImportViolation(relative, imported.line, module, reason))
    return violations


@dataclass(frozen=True)
class _ImportedModule:
    module: str
    line: int
    level: int
    guarded: bool


def _iter_imports(node: ast.AST, guarded: bool = False) -> list[_ImportedModule]:
    imports: list[_ImportedModule] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.append(_ImportedModule(alias.name, node.lineno, 0, guarded))
        return imports
    if isinstance(node, ast.ImportFrom):
        if node.module:
            imports.append(_ImportedModule(node.module, node.lineno, node.level, guarded))
        return imports
    if isinstance(node, ast.Try):
        body_guarded = guarded or _catches_optional_import(node.handlers)
        for child in node.body:
            imports.extend(_iter_imports(child, body_guarded))
        for child in node.orelse:
            imports.extend(_iter_imports(child, guarded))
        for child in node.finalbody:
            imports.extend(_iter_imports(child, guarded))
        for handler in node.handlers:
            for child in handler.body:
                imports.extend(_iter_imports(child, guarded))
        return imports
    for child in ast.iter_child_nodes(node):
        imports.extend(_iter_imports(child, guarded))
    return imports


def _catches_optional_import(handlers: list[ast.excepthandler]) -> bool:
    return any(_handler_catches(handler.type) for handler in handlers)


def _handler_catches(exc_type: ast.expr | None) -> bool:
    if exc_type is None:
        return True
    if isinstance(exc_type, ast.Name):
        return exc_type.id in {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}
    if isinstance(exc_type, ast.Tuple):
        return any(_handler_catches(item) for item in exc_type.elts)
    return False


def _is_local_module(module: str, current_file: Path, package_dir: Path) -> bool:
    parts = module.split(".")
    package_name = package_dir.name
    if parts[0] == package_name:
        parts = parts[1:]
        if not parts:
            return True
    search_roots = []
    parent = current_file.parent
    while package_dir in (parent, *parent.parents):
        search_roots.append(parent)
        if parent == package_dir:
            break
        parent = parent.parent
    if package_dir not in search_roots:
        search_roots.append(package_dir)
    return any(_module_exists_under(root, parts) for root in search_roots)


def _module_exists_under(root: Path, parts: list[str]) -> bool:
    current = root
    for index, part in enumerate(parts):
        is_last = index == len(parts) - 1
        module_file = current / f"{part}.py"
        package_init = current / part / "__init__.py"
        if is_last:
            return module_file.exists() or package_init.exists()
        if package_init.exists():
            current = current / part
            continue
        return False
    return False
