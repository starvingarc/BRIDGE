"""Static policy checks work without scientific dependencies."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_static_repository_checks_need_no_scientific_imports(self):
        result = subprocess.run(
            [sys.executable, "-S", str(ROOT / "scripts/check_repository.py"), "--static"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Static repository checks passed", result.stdout)


    def test_old_python_gets_actionable_error_before_toml_import(self):
        for script in ("check_documentation.py", "check_repository.py"):
            for version in ((3, 8, 10), (3, 11, 0)):
                with self.subTest(script=script, version=version):
                    code = f"""
import builtins, runpy, sys
sys.path.insert(0, {str(ROOT / 'scripts')!r})
sys.version_info = {version!r}
original_import = builtins.__import__
def reject_toml(name, *args, **kwargs):
    if name == 'tomllib':
        raise ModuleNotFoundError('tomllib must not be imported on unsupported Python')
    return original_import(name, *args, **kwargs)
builtins.__import__ = reject_toml
sys.argv = [{script!r}, '--static'] if {script!r} == 'check_repository.py' else [{script!r}]
runpy.run_path({str(ROOT / 'scripts' / script)!r}, run_name='__main__')
"""
                    result = subprocess.run([sys.executable, "-S", "-c", code],
                        cwd=ROOT, capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("Python 3.12", result.stderr)
                    self.assertIn("project", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertNotIn("tomllib", result.stderr)
