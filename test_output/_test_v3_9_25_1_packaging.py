"""v3.9.25.1 packaging regression tests.

Catches the 4 packaging issues the user reported in v3.9.25.0:
1. SKILL.md frontmatter version != git tag
2. SKILL.md frontmatter pa_cli_version != pa_cli/__init__.py
3. SKILL.md description has leftover v3.9.23.0 text (7 engines)
4. scripts/version.py skill_version mismatch
5. Mojibake em-dash (鈥?) in skill files
6. UTF-8 BOM in skill .py files

These are NOT covered by behavior tests (which only check --help, --json,
exit codes, etc.) — they validate the release artifact metadata.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = ROOT / ".agents" / "skills" / "paper-agent"

# Bytes that indicate mojibake em-dash
MOJIBAKE_DASH = b'\xe9\x88\xa5'
UTF8_BOM = b'\xef\xbb\xbf'


def get_pa_cli_version() -> str:
    """Read pa_cli version from __init__.py."""
    init = ROOT / "pa_cli" / "__init__.py"
    content = init.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    assert m, f"Could not find __version__ in {init}"
    return m.group(1)


def get_skill_md_version() -> dict:
    """Extract version and pa_cli_version from SKILL.md frontmatter."""
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    # Get just the frontmatter
    m = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
    assert m, f"No YAML frontmatter in SKILL.md"
    fm = m.group(1)
    version_m = re.search(r'^\s*version:\s*(\S+)', fm, re.MULTILINE)
    pa_cli_m = re.search(r'^\s*pa_cli_version:\s*(\S+)', fm, re.MULTILINE)
    return {
        "version": version_m.group(1) if version_m else None,
        "pa_cli_version": pa_cli_m.group(1) if pa_cli_m else None,
    }


def get_version_py_skill_version() -> str:
    """Read skill_version from scripts/version.py."""
    content = (SKILL_ROOT / "scripts" / "version.py").read_text(encoding="utf-8")
    m = re.search(r'"skill_version":\s*"([^"]+)"', content)
    assert m, "Could not find skill_version in version.py"
    return m.group(1)


class TestSkillMdVersion(unittest.TestCase):
    """SKILL.md frontmatter version must match git tag (v3.9.25.1)."""

    def test_skill_md_version_is_3_9_25_1(self):
        v = get_skill_md_version()["version"]
        self.assertEqual(v, "3.9.25.1",
                         f"SKILL.md version is '{v}', expected '3.9.25.1'")
        print(f"  [PASS] SKILL.md frontmatter version: {v}")

    def test_skill_md_pa_cli_version_matches_pa_cli(self):
        skill_v = get_skill_md_version()["pa_cli_version"]
        cli_v = get_pa_cli_version()
        self.assertEqual(skill_v, cli_v,
                         f"SKILL.md pa_cli_version '{skill_v}' != pa_cli '{cli_v}'")
        print(f"  [PASS] SKILL.md pa_cli_version ({skill_v}) matches pa_cli")


class TestSkillMdDescription(unittest.TestCase):
    """SKILL.md description must not have leftover 7-engines text from v3.9.23.0."""

    def test_no_7_engines_text(self):
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        # Look for the v3.9.23.0 leftover text "7 engines" (case-sensitive)
        self.assertNotIn("7 engines", content,
                         "SKILL.md should not have '7 engines' (we have 8 now)")
        # Also check for the broken ").rch for" text from the v3.9.24.0 bad concat
        # (the actual broken text was ").rch for academic papers by")
        self.assertNotIn(").rch for", content,
                         "SKILL.md should not have ').rch for' (broken concat text)")
        print("  [PASS] SKILL.md description has no '7 engines' or ').rch for' text")

    def test_description_has_8_engines(self):
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        # Count 'engines' in the description block (between --- markers)
        m = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
        assert m
        fm = m.group(1)
        self.assertIn("8 engines", fm, "SKILL.md description should mention '8 engines'")
        print("  [PASS] SKILL.md description mentions 8 engines")

    def test_no_duplicate_description(self):
        # Check for the duplicated "7. Do NOT use this skill for:" pattern
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        count = content.count("Do NOT use this skill for")
        self.assertEqual(count, 1, f"'Do NOT use this skill for' should appear once, found {count} times")
        print(f"  [PASS] No duplicate 'Do NOT use this skill for' (count: {count})")


class TestVersionPy(unittest.TestCase):
    """version.py skill_version must match SKILL.md frontmatter."""

    def test_version_py_skill_version(self):
        v = get_version_py_skill_version()
        self.assertEqual(v, "3.9.25.1",
                         f"version.py skill_version is '{v}', expected '3.9.25.1'")
        print(f"  [PASS] version.py skill_version: {v}")


class TestMojibake(unittest.TestCase):
    """Skill files must not have mojibake em-dash (鈥?)."""

    def test_no_mojibake_in_skill_files(self):
        skill_files = list(SKILL_ROOT.rglob("*.md")) + list(SKILL_ROOT.rglob("*.py")) + list(SKILL_ROOT.rglob("*.yaml"))
        bad_files = []
        for f in skill_files:
            try:
                data = f.read_bytes()
            except Exception:
                continue
            if MOJIBAKE_DASH in data:
                # Skip already-corrected — no "鈥" anywhere
                bad_files.append(f.name)
        self.assertEqual(bad_files, [],
                         f"Found mojibake em-dash in: {bad_files}")
        print(f"  [PASS] No mojibake in {len(skill_files)} skill files")

    def test_no_bom_in_skill_files(self):
        skill_py = list(SKILL_ROOT.rglob("*.py"))
        bad_files = []
        for f in skill_py:
            data = f.read_bytes()
            if data.startswith(UTF8_BOM):
                bad_files.append(f.name)
        self.assertEqual(bad_files, [],
                         f"Found UTF-8 BOM in: {bad_files}")
        print(f"  [PASS] No UTF-8 BOM in {len(skill_py)} .py skill files")


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    print("=" * 60)
    print("v3.9.25.1 packaging regression tests")
    print("=" * 60)
    unittest.main(verbosity=2)
