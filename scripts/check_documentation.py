#!/usr/bin/env python3
"""Read-only documentation contracts. No project imports or code execution."""
from __future__ import annotations

import sys

# Match the project source syntax before importing version-specific stdlib modules.
if sys.version_info < (3, 12):
    raise SystemExit(
        "Documentation checks require Python 3.12 or newer. "
        "Use the project's Python 3.12 interpreter."
    )

import argparse
import ast
from collections import Counter, defaultdict
import html
import json
import re
import subprocess
from pathlib import Path
import tomllib
import unicodedata
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = re.compile(r"bridge://schemas/[a-z0-9-]+/v\d+\.\d+")
LINK = re.compile(r"!?\[([^\]]*)\]\((<[^>]+>|[^\s)]+)(?:\s+[\x22\x27][^)]*)?\)")
LEGACY_RESULT = "Not separately declared by the v0.1 package spec"
ROLE_MAP = re.compile(r"(?:^|_)ROLE_(?:MODELS|SCHEMAS|CONTRACTS)$")


class Unsupported(ValueError):
    pass


class PythonText:
    """Resolve the finite literal declarations used by these checks, never eval."""
    def __init__(self, root: Path):
        self.root = root
        self.trees = {}

    def tree(self, path: Path):
        if path not in self.trees:
            self.trees[path] = ast.parse((self.root / path).read_text(encoding="utf-8"))
        return self.trees[path]

    def symbol(self, path: Path, name: str, seen=()):
        key = (path, name)
        if key in seen:
            raise Unsupported(f"cyclic declaration: {path}:{name}")
        base, _, member = name.partition(".")
        for node in self.tree(path).body:
            if not member and isinstance(node, ast.ClassDef) and node.name == name:
                return path, node
            if member and isinstance(node, ast.ClassDef) and node.name == base:
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == member:
                        return path, item.value
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                    return path, node.value
            if isinstance(node, ast.ImportFrom):
                for item in node.names:
                    if (item.asname or item.name) != name:
                        continue
                    if node.level:
                        directory = path.parent
                        for _ in range(node.level - 1):
                            directory = directory.parent
                        target = directory / (node.module or "").replace(".", "/")
                    else:
                        target = Path("src") / (node.module or "").replace(".", "/")
                    target = target.with_suffix(".py") if (self.root / target.with_suffix(".py")).is_file() else target / "__init__.py"
                    if not (self.root / target).is_file():
                        raise Unsupported(f"nonlocal declaration: {path}:{name}")
                    return self.symbol(target, item.name, (*seen, key))
        raise Unsupported(f"missing declaration: {path}:{name}")

    def value(self, path, node, env=None, depth=0):
        if depth > 40:
            raise Unsupported(f"declaration depth exceeded: {path}")
        env = env or {}
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            target, source = self.symbol(path, node.id)
            return self.value(target, source, env, depth + 1)
        if isinstance(node, ast.Subscript):
            target, value = path, node.value
            if isinstance(value, ast.Name):
                target, value = self.symbol(path, value.id)
            index = self.value(path, node.slice, env, depth + 1)
            if isinstance(value, (ast.Tuple, ast.List)) and isinstance(index, int):
                return self.value(target, value.elts[index], env, depth + 1)
            raise Unsupported(f"unsupported subscript: {path}:{node.lineno}")
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return [self.value(path, item, env, depth + 1) for item in node.elts]
        if isinstance(node, ast.JoinedStr):
            return "".join(str(self.value(path, item.value if isinstance(item, ast.FormattedValue) else item, env, depth + 1)) for item in node.values)
        if isinstance(node, ast.IfExp):
            condition = self.value(path, node.test, env, depth + 1)
            return self.value(path, node.body if condition else node.orelse, env, depth + 1)
        if isinstance(node, ast.BinOp):
            left, right = self.value(path, node.left, env, depth + 1), self.value(path, node.right, env, depth + 1)
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Pow):
                return left ** right
        raise Unsupported(f"unsupported literal declaration: {path}:{getattr(node, 'lineno', '?')}")

    def named(self, path, name):
        target, node = self.symbol(Path(path), name)
        return self.value(target, node)

    def mapping_entries(self, path, node, seen=()):
        if isinstance(node, ast.Name):
            target, source = self.symbol(path, node.id)
            key = (target, node.id)
            if key in seen:
                raise Unsupported(f"cyclic role map: {target}:{node.id}")
            yield from self.mapping_entries(target, source, (*seen, key))
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is None:
                    yield from self.mapping_entries(path, value, seen)
                else:
                    yield self.value(path, key), path, value
        else:
            raise Unsupported(f"unsupported role map: {path}:{node.lineno}")


def without_fences(text):
    lines, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(\x60{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            lines.append("")
        else:
            lines.append("" if fence else line)
    return "\n".join(lines)


def anchors(text):
    text = without_fences(text)
    found = set(re.findall(r"<a\b[^>]*\b(?:id|name)\s*=\s*[\x22\x27]([^\x22\x27]+)", text, flags=re.I))
    used = set()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)(?:\s+#+\s*)?$", line)
        title = heading[1] if heading else None
        if title is None and index + 1 < len(lines) and line.strip() and re.fullmatch(r"\s{0,3}(?:=+|-+)\s*", lines[index + 1]):
            title = line
        if title is None:
            continue
        title = LINK.sub(lambda match: match[1], title)
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).lower()
        slug = "".join(char for char in title if char in "-_ " or unicodedata.category(char)[0] not in "PS")
        slug = slug.replace(" ", "-")
        candidate, suffix = slug, 0
        while candidate in used:
            suffix += 1
            candidate = f"{slug}-{suffix}"
        used.add(candidate)
        found.add(candidate)
    return found


def local_links(path, text):
    for match in LINK.finditer(without_fences(text)):
        target = html.unescape(match[2].strip("<>"))
        url = urlsplit(target)
        if url.scheme or url.netloc:
            continue
        destination = Path(unquote(url.path))
        if not url.path:
            destination = path
        elif not destination.is_absolute():
            destination = path.parent / destination
        yield destination, unquote(url.fragment), match[0]


def spec_scalars(path):
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([a-z_]+):\s*(.*?)\s*", line)
        if match:
            key, value = match.groups()
            if key in fields:
                raise Unsupported(f"duplicate spec field: {path.name}:{key}")
            fields[key] = value.strip("\x22\x27")
    return fields


def table_rows(text):
    for line in without_fences(text).splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) >= 2:
                yield cells[0], cells[1]


def _helper_roles(source, path, statements, env, stack, bindings):
    """Follow local role collections, conditions and the actual return value."""
    for node in statements:
        if isinstance(node, ast.If):
            branch = node.body if source.value(path, node.test, env) else node.orelse
            result = _helper_roles(source, path, branch, env, stack, bindings)
            if result is not None:
                return result
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if len(targets) != 1 or not isinstance(targets[0], ast.Name):
                raise Unsupported(f"unsupported role assignment: {path}:{node.lineno}")
            bindings[targets[0].id] = list(_roles(source, path, node.value, env, stack, bindings))
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (not isinstance(call.func, ast.Attribute) or call.func.attr != "extend"
                    or not isinstance(call.func.value, ast.Name) or len(call.args) != 1
                    or call.keywords or call.func.value.id not in bindings):
                raise Unsupported(f"unsupported role mutation: {path}:{node.lineno}")
            bindings[call.func.value.id].extend(_roles(source, path, call.args[0], env, stack, bindings))
        elif isinstance(node, ast.Return):
            return list(_roles(source, path, node.value, env, stack, bindings))
        else:
            raise Unsupported(f"unsupported role statement: {path}:{node.lineno}")
    return None


def _roles(source, path, node, env=None, stack=(), bindings=None):
    env = env or {}
    bindings = bindings if bindings is not None else {}
    if isinstance(node, ast.Name):
        if node.id in bindings:
            yield from bindings[node.id]
        elif node.id not in env:
            raise Unsupported(f"unbound role declaration: {path}:{node.id}")
        return
    if isinstance(node, ast.IfExp):
        branch = node.body if source.value(path, node.test, env) else node.orelse
        yield from _roles(source, path, branch, env, stack, bindings)
        return
    if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
        environments = [env]
        for generator in node.generators:
            if generator.ifs or generator.is_async or not isinstance(generator.target, ast.Name):
                raise Unsupported(f"unsupported input comprehension: {path}:{node.lineno}")
            environments = [{**current, generator.target.id: value} for current in environments
                            for value in source.value(path, generator.iter, current)]
        for current in environments:
            yield from _roles(source, path, node.elt, current, stack, bindings)
        return
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        name = node.func.id
        if name == "_role":
            role, schemas, versions = [source.value(path, value, env) for value in node.args[:3]]
            yield role, {schemas} if isinstance(schemas, str) else set(schemas), (
                None if versions is None else {versions} if isinstance(versions, str) else set(versions))
            return
        if name.startswith("_p") and name not in stack:
            function = next((item for item in source.tree(path).body if isinstance(item, ast.FunctionDef) and item.name == name), None)
            if function is None:
                raise Unsupported(f"missing input helper: {name}")
            bound = {arg.arg: source.value(path, value, env) for arg, value in zip(function.args.args, node.args)}
            bound.update({item.arg: source.value(path, item.value, env) for item in node.keywords})
            result = _helper_roles(source, path, function.body, {**env, **bound}, (*stack, name), {})
            if result is None:
                raise Unsupported(f"role helper has no return: {path}:{name}")
            yield from result
            return
        if name not in {"_mode", "ToolInputContract", "AssetInputContract"}:
            raise Unsupported(f"unsupported role call: {path}:{name}")
        # These constructors expose their role containers directly. Their other
        # keyword values are scalar constraints, not role declarations.
        children = (list(node.args[1:]) if name == "_mode" else
                    [item.value for item in node.keywords if item.arg == "object_input_modes"]
                    if name == "ToolInputContract" else [])
    elif isinstance(node, (ast.List, ast.Tuple)):
        children = node.elts
    elif isinstance(node, ast.Starred):
        children = [node.value]
    elif isinstance(node, ast.Constant):
        return
    else:
        raise Unsupported(f"unsupported role expression: {path}:{getattr(node, 'lineno', '?')}")
    for child in children:
        yield from _roles(source, path, child, env, stack, bindings)


def input_roles(source):
    path = Path("src/bridge/tool_packages/_input_contracts.py")
    mapping = next(node.value for node in source.tree(path).body
                   if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Dict)
                   and any(isinstance(key, ast.Constant) and key.value == "P0-10" for key in node.value.keys))
    tools = {}
    for key, value in zip(mapping.keys, mapping.values):
        roles = defaultdict(lambda: {"schemas": set(), "versions": set(), "payload": False})
        for role, schemas, versions in _roles(source, path, value):
            roles[role]["schemas"].update(schemas)
            roles[role]["payload"] |= versions is None
            roles[role]["versions"].update(versions or ())
        tools[source.value(path, key)] = roles
    return tools


def adapter_schemas(source, path):
    roles = defaultdict(set)
    for node in source.tree(path).body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        names = node.targets if isinstance(node, ast.Assign) else [node.target]
        mapping_names = [name.id for name in names if isinstance(name, ast.Name) and ROLE_MAP.search(name.id)]
        if not mapping_names:
            continue
        schema_map = any(name.endswith("ROLE_SCHEMAS") for name in mapping_names)
        for role, location, value in source.mapping_entries(path, node.value):
            # Model-only maps have no schema literal; their paired ROLE_SCHEMAS
            # supplies it. Tuple maps declare schema first and model last.
            if not schema_map and isinstance(value, (ast.Tuple, ast.List)):
                value = value.elts[0]
            try:
                values = source.value(location, value)
            except Unsupported:
                if isinstance(value, ast.Name) and isinstance(source.symbol(location, value.id)[1], ast.ClassDef):
                    continue
                raise
            values = [values] if isinstance(values, str) else values
            if not isinstance(values, list) or not values or any(
                not isinstance(item, str) or not SCHEMA.fullmatch(item) for item in values
            ):
                raise Unsupported(f"invalid schema declaration: {location}:{role}")
            roles[role].update(values)
    # P0-10 additionally admits research versions in explicit role/schema
    # predicates. Read these declarations too, rather than pinning v0.5 here.
    for node in ast.walk(source.tree(path)):
        if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.And):
            continue
        role, schemas = None, set()
        for part in node.values:
            if (isinstance(part, ast.Compare) and len(part.ops) == 1
                    and isinstance(part.left, ast.Attribute) and part.left.attr == "role"
                    and isinstance(part.ops[0], ast.Eq) and isinstance(part.comparators[0], ast.Constant)):
                role = part.comparators[0].value
        if role is None:
            continue
        for part in node.values:
            if not isinstance(part, ast.Compare) or len(part.ops) != 1 or not isinstance(part.left, ast.Attribute):
                continue
            if part.left.attr == "role" and isinstance(part.ops[0], ast.Eq) and isinstance(part.comparators[0], ast.Constant):
                role = part.comparators[0].value
            if part.left.attr == "schema_ref" and isinstance(part.ops[0], (ast.Eq, ast.In)):
                values = source.value(path, part.comparators[0])
                schemas.update([values] if isinstance(values, str) else values)
        if role and schemas:
            roles[role].update(item for item in schemas if SCHEMA.fullmatch(item))
    return roles


def schema_versions(root, references, schema):
    filename = references.get(schema)
    if filename is None:
        raise Unsupported(f"input schema is not registered: {schema}")
    value = json.loads((root / "src/bridge/resources/schemas" / filename).read_text())
    version = value.get("properties", {}).get("object_version", {})
    if "const" in version:
        return {version["const"]}
    return set(version.get("enum", []))


def component_counts(source):
    path, value = source.symbol(Path("src/bridge/toolkit/visualization.py"), "_DEFAULT_COMPONENTS")
    counts = Counter()
    def visit(node, multiplier=1):
        if isinstance(node, (ast.GeneratorExp, ast.ListComp)):
            if any(item.ifs for item in node.generators):
                raise Unsupported("filtered figure declarations need an explicit count reader")
            for item in node.generators:
                multiplier *= len(source.value(path, item.iter))
            visit(node.elt, multiplier)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"_typed_component", "_legacy_component"}:
            counts["typed" if node.func.id == "_typed_component" else "legacy"] += multiplier
        else:
            for child in ast.iter_child_nodes(node):
                visit(child, multiplier)
    visit(value)
    return {**counts, "total": sum(counts.values())}


def assertion_value(root, source, row):
    kind = row["kind"]
    if kind == "python":
        return source.named(row["path"], row["symbol"])
    if kind == "toml":
        value = tomllib.loads((root / row["path"]).read_text())
        for key in row["keys"]:
            value = value[key]
        return value
    if kind == "figures":
        return component_counts(source)[row["key"]]
    raise Unsupported(f"unknown assertion source: {kind}")


def check_documentation(root=ROOT, tracked=None):
    root = Path(root)
    if tracked is None:
        tracked = [Path(item) for item in subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines()]
    tracked = set(map(Path, tracked))
    problems, source = [], PythonText(root)
    def fail(category, location, message):
        problems.append(f"{category}: {location}: {message}")
    try:
        package = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
        if source.named("src/bridge/__init__.py", "__version__") != package:
            fail("package version", "src/bridge/__init__.py", f"must match pyproject.toml ({package})")
        languages = (
            ("Python", "pyproject.toml", "requires-python",
             tomllib.loads((root / "pyproject.toml").read_text())["project"].get("requires-python")),
            ("Node.js", "frontend/package.json", "engines.node",
             json.loads((root / "frontend/package.json").read_text()).get("engines", {}).get("node")),
        )
        for language, filename, field, constraint in languages:
            if not isinstance(constraint, str) or not constraint.strip():
                fail("language version", filename, f"missing {field}")
            for document in ("README.md", "docs/DEVELOPMENT.md"):
                text = (root / document).read_text()
                if field not in text or not any(
                    destination.resolve() == (root / filename).resolve()
                    for destination, _, _ in local_links(root / document, text)
                ):
                    fail("language version", document, f"must reference {language} source {filename}:{field}")
        specs = {}
        for path in sorted((root / "src/bridge/tool_packages/specs").glob("*.yaml")):
            spec = spec_scalars(path)
            for field in ("tool_id", "version", "input_schema_ref"):
                if not spec.get(field):
                    raise Unsupported(f"missing spec field: {path.name}:{field}")
            tool = spec["tool_id"]
            specs[tool] = spec
            card = Path(f"src/bridge/tool_packages/cards/{tool}.md")
            rows = list(table_rows((root / card).read_text()))
            for field, expected in (("Package version", spec["version"]),
                                    ("Result schema", spec.get("result_schema_ref", LEGACY_RESULT))):
                actual = [value.strip("\x60") for label, value in rows if label == field]
                if actual != [expected]:
                    fail(field, card, f"expected one current declaration: {expected}")
        # Each task card's primary result either declares the spec URI or links
        # to its exact Tool Card. Inner and historical result rows remain distinct.
        task_index = (root / "docs/bridge_spec_v0.1/README.md").read_text()
        task_cards = re.findall(r"\[(P0-\d\d)[^\]]*\]\(([^)#]+_task_card.md)\)", task_index)
        if Counter(tool for tool, _ in task_cards) != Counter({tool: 1 for tool in specs}):
            fail("primary result", "docs/bridge_spec_v0.1/README.md",
                 "must index exactly one scientific task card per package spec")
        for tool, filename in task_cards:
            path = Path("docs/bridge_spec_v0.1") / filename
            rows = list(table_rows((root / path).read_text()))
            primary = [value for label, value in rows if label in {
                "Current result schema", "Current result", "当前结果 Schema", "ToolRun result Schema",
            } or label == "输出" and "bridge://schemas/" in value]
            if len(primary) != 1:
                fail("primary result", path, "expected one current result row or Tool Card reference")
            else:
                uris = SCHEMA.findall(primary[0])
                expected = specs[tool].get("result_schema_ref")
                if uris:
                    if uris[0] != expected:
                        fail("primary result", path, f"expected {expected}")
                elif not any(destination.resolve() == (root / f"src/bridge/tool_packages/cards/{tool}.md").resolve()
                             and fragment == "contract"
                             for destination, fragment, _ in local_links(root / path, primary[0])):
                    fail("primary result", path, f"must link to {tool} Tool Card")
        def requests(value, path, tool=None):
            if isinstance(value, dict):
                tool = value.get("tool_id", tool)
                if "tool_version" in value and value["tool_version"] != specs.get(tool, {}).get("version"):
                    fail("tool_version", path, f"{tool}: {value['tool_version']} differs from package spec")
                for child in value.values():
                    requests(child, path, tool)
            elif isinstance(value, list):
                for child in value:
                    requests(child, path, tool)
        for path in sorted(tracked):
            if path.suffix == ".json" and (path.parent == Path("examples/requests") or path.parent == Path("examples/agent-integration/profiles")):
                requests(json.loads((root / path).read_text()), path)
        contracts = input_roles(source)
        references = ast.literal_eval(source.symbol(Path("src/bridge/toolkit/schemas.py"), "SCHEMA_REFS")[1])
        for tool, spec in specs.items():
            if not spec.get("adapter_ref"):
                continue
            path = Path("src") / (spec["adapter_ref"].split(":")[0].replace(".", "/") + ".py")
            required = adapter_schemas(source, path)
            card_path = Path(f"src/bridge/tool_packages/cards/{tool}.md")
            for label, value in table_rows((root / card_path).read_text()):
                role = label.strip("\x60")
                if not re.fullmatch(r"[a-z][a-z0-9_]*", role):
                    continue
                uris = SCHEMA.findall(value)
                # Tool Cards may abbreviate further versions of the same family.
                if uris:
                    family = uris[0].rsplit("/v", 1)[0]
                    uris += [family + "/v" + version for version in re.findall(r"(?<![a-z0-9-])/v(\d+\.\d+)", value)]
                    required[role].update(uris)
            for role, schemas in required.items():
                actual = contracts[tool].get(role, {"schemas": set(), "versions": set(), "payload": False})
                for schema in sorted(schemas):
                    if schema not in actual["schemas"]:
                        fail("input schema", f"{tool}/{role}", f"contract omits {schema}")
                        continue
                    if not actual["payload"]:
                        for version in schema_versions(root, references, schema) - actual["versions"]:
                            fail("input version", f"{tool}/{role}", f"contract omits {version} for {schema}")
        assertions = json.loads((root / "scripts/documentation_assertions.json").read_text())
        ids = set()
        for row in assertions:
            if set(row) != {"id", "document", "pattern", "count", "groups"} or type(row["count"]) is not int or row["count"] < 1 or not row["groups"]:
                raise Unsupported("invalid documentation assertion")
            if row["id"] in ids:
                raise Unsupported(f"duplicate assertion: {row['id']}")
            ids.add(row["id"])
            matches = list(re.finditer(row["pattern"], (root / row["document"]).read_text(), re.M))
            if len(matches) != row["count"]:
                fail("assertion", row["id"], f"expected {row['count']} occurrences, found {len(matches)}")
            for match in matches:
                for group, definition in row["groups"].items():
                    actual = match[group]
                    expected = assertion_value(root, source, definition["source"])
                    if isinstance(expected, int):
                        actual = int(actual.replace(",", "")) * definition.get("scale", 1)
                    if actual != expected:
                        fail("assertion", row["id"], f"{group}: {actual!r} != source {expected!r}")
    except (Unsupported, OSError, ValueError, KeyError, StopIteration, SyntaxError, TypeError) as error:
        fail("documentation source", "contracts", str(error) or type(error).__name__)

    texts = {}
    for path in sorted(tracked):
        if path.suffix == ".md" and (root / path).is_file():
            texts[path] = (root / path).read_text(encoding="utf-8")
    graph = defaultdict(set)
    for path, text in texts.items():
        for destination, fragment, label in local_links(root / path, text):
            target = destination.resolve()
            try:
                relative = target.relative_to(root.resolve())
            except ValueError:
                fail("local link", path, f"outside repository: {label}")
                continue
            if not target.exists():
                fail("local link", path, f"missing target: {label}")
                continue
            if target.is_dir():
                target = target / "README.md"
                relative = relative / "README.md"
            if relative in texts:
                graph[path].add(relative)
            if fragment:
                if relative.suffix == ".md" and relative in texts:
                    if fragment not in anchors(texts[relative]):
                        fail("anchor", path, f"missing target: {label}")
                elif target.is_file():
                    target_text = target.read_text(encoding="utf-8")
                    explicit = set(re.findall(r"\bid\s*=\s*[\x22\x27]([^\x22\x27]+)", target_text))
                    line = re.fullmatch(r"L(\d+)(?:-L(\d+))?", fragment)
                    if fragment not in explicit and not (line and 1 <= int(line[1]) <= int(line[2] or line[1]) <= len(target_text.splitlines())):
                        fail("anchor", path, f"unsupported or missing target: {label}")
    reached, queue = set(), [Path("docs/README.md")]
    while queue:
        path = queue.pop()
        if path not in reached:
            reached.add(path)
            queue.extend(graph[path] - reached)
    for path in sorted(tracked):
        if path.parts and path.parts[0] == "docs" and path.suffix == ".md" and path not in reached:
            fail("documentation index", path, "not reachable from docs/README.md")
        if path.parent == Path("scripts") and path.suffix == ".py":
            if not re.search(r"\x60" + re.escape(path.name) + r"\x60|\]\(" + re.escape(path.name) + r"\)", texts.get(Path("scripts/README.md"), "")):
                fail("script index", path, "missing from scripts/README.md")
    agents = texts.get(Path("AGENTS.md"), "")
    if "不穷尽" not in agents and "non-exhaustive" not in agents:
        for path in sorted({Path(*path.parts[:3]) for path in tracked
                            if len(path.parts) > 3 and path.parts[:2] == ("src", "bridge") and (root / Path(*path.parts[:3]) / "__init__.py").is_file()}):
            if f"{path}/" not in agents:
                fail("ownership", path, "not covered by AGENTS.md ownership table")
    return sorted(set(problems))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    problems = check_documentation()
    if problems:
        print("\n".join(problems))
        return 1
    print("Documentation contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
