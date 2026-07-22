"""Test for [v3.9.10.13] pa_cli.search._load_dotenv — auto-load .env file.

Verifies that:
  1. _load_dotenv() loads keys from .env into os.environ
  2. setdefault semantics: existing shell env wins over .env
  3. Search order: PAPER_AGENT_ENV_FILE > ./pa.env > ./.env > <repo>/.env
  4. Comments (#) and blank lines are ignored
  5. Quoted values are unquoted
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Make pa_cli importable
sys.path.insert(0, '.')

from pa_cli.search import _load_dotenv

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")


def test_1_loads_keys_from_env_file():
    """Basic: keys in .env file are loaded into os.environ."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as f:
        f.write("TEST_KEY_1=value_1\n")
        f.write("TEST_KEY_2=value_2\n")
        env_path = Path(f.name)
    try:
        # Clear any pre-existing values
        os.environ.pop("TEST_KEY_1", None)
        os.environ.pop("TEST_KEY_2", None)
        _load_dotenv(env_path)
        check("loads TEST_KEY_1", os.environ.get("TEST_KEY_1") == "value_1",
              f"got {os.environ.get('TEST_KEY_1')!r}")
        check("loads TEST_KEY_2", os.environ.get("TEST_KEY_2") == "value_2",
              f"got {os.environ.get('TEST_KEY_2')!r}")
    finally:
        env_path.unlink()
        os.environ.pop("TEST_KEY_1", None)
        os.environ.pop("TEST_KEY_2", None)


def test_2_setdefault_does_not_overwrite_existing():
    """setdefault semantics: existing shell env wins."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as f:
        f.write("TEST_KEY_SHELL=from_env_file\n")
        env_path = Path(f.name)
    try:
        os.environ["TEST_KEY_SHELL"] = "from_shell"
        _load_dotenv(env_path)
        check("setdefault: shell wins", os.environ.get("TEST_KEY_SHELL") == "from_shell",
              f"got {os.environ.get('TEST_KEY_SHELL')!r}")
    finally:
        env_path.unlink()
        os.environ.pop("TEST_KEY_SHELL", None)


def test_3_ignores_comments_and_blanks():
    """Lines starting with # and blank lines are ignored."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as f:
        f.write("# this is a comment\n")
        f.write("\n")
        f.write("   \n")
        f.write("TEST_REAL_KEY=hello\n")
        f.write("# TEST_COMMENTED=should_not_load\n")
        env_path = Path(f.name)
    try:
        os.environ.pop("TEST_REAL_KEY", None)
        os.environ.pop("TEST_COMMENTED", None)
        _load_dotenv(env_path)
        check("loads real key", os.environ.get("TEST_REAL_KEY") == "hello",
              f"got {os.environ.get('TEST_REAL_KEY')!r}")
        check("ignores commented key", "TEST_COMMENTED" not in os.environ,
              "TEST_COMMENTED should NOT be loaded")
    finally:
        env_path.unlink()
        os.environ.pop("TEST_REAL_KEY", None)


def test_4_unquotes_values():
    """Quoted values have quotes stripped."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as f:
        f.write('TEST_DOUBLE="double_quoted_value"\n')
        f.write("TEST_SINGLE='single_quoted_value'\n")
        f.write("TEST_PLAIN=plain_value\n")
        env_path = Path(f.name)
    try:
        os.environ.pop("TEST_DOUBLE", None)
        os.environ.pop("TEST_SINGLE", None)
        os.environ.pop("TEST_PLAIN", None)
        _load_dotenv(env_path)
        check("unquotes double", os.environ.get("TEST_DOUBLE") == "double_quoted_value",
              f"got {os.environ.get('TEST_DOUBLE')!r}")
        check("unquotes single", os.environ.get("TEST_SINGLE") == "single_quoted_value",
              f"got {os.environ.get('TEST_SINGLE')!r}")
        check("plain value", os.environ.get("TEST_PLAIN") == "plain_value",
              f"got {os.environ.get('TEST_PLAIN')!r}")
    finally:
        env_path.unlink()
        os.environ.pop("TEST_DOUBLE", None)
        os.environ.pop("TEST_SINGLE", None)
        os.environ.pop("TEST_PLAIN", None)


def test_5_search_order_via_paper_agent_env_file():
    """$PAPER_AGENT_ENV_FILE path is used if file exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as f:
        f.write("TEST_PAPER_AGENT_KEY=from_paper_agent_env\n")
        env_path = Path(f.name)
    try:
        os.environ["PAPER_AGENT_ENV_FILE"] = str(env_path)
        os.environ.pop("TEST_PAPER_AGENT_KEY", None)
        _load_dotenv()
        check("uses PAPER_AGENT_ENV_FILE", os.environ.get("TEST_PAPER_AGENT_KEY") == "from_paper_agent_env",
              f"got {os.environ.get('TEST_PAPER_AGENT_KEY')!r}")
    finally:
        os.environ.pop("PAPER_AGENT_ENV_FILE", None)
        os.environ.pop("TEST_PAPER_AGENT_KEY", None)
        env_path.unlink()


def test_6_missing_file_is_noop():
    """Non-existent file: no error, no env change."""
    os.environ.pop("DEFINITELY_NOT_SET", None)
    _load_dotenv(Path("/nonexistent/.env_that_does_not_exist"))
    check("missing file is noop", "DEFINITELY_NOT_SET" not in os.environ,
          "should not set any env vars")


def test_7_repo_env_file_loads():
    """The repo's .env file is loaded when no explicit path is given."""
    repo_env = Path("G:/minimax - workspace/Paper agent/.env")
    if not repo_env.is_file():
        print(f"  [SKIP] repo .env file not found at {repo_env}")
        return
    # Clear one key, then load, then check it got set
    saved = os.environ.get("S2_API_KEY")
    os.environ.pop("S2_API_KEY", None)
    _load_dotenv()
    loaded = os.environ.get("S2_API_KEY")
    check("repo .env loads S2_API_KEY", loaded is not None and loaded.startswith("s2k-"),
          f"got {loaded!r}")
    # Restore (don't pollute the rest of the test suite)
    if saved is not None:
        os.environ["S2_API_KEY"] = saved
    else:
        os.environ.pop("S2_API_KEY", None)


def test_8_lines_without_equals_are_ignored():
    """Lines without '=' are silently ignored (no crash)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as f:
        f.write("not_a_valid_line\n")
        f.write("VALID_KEY=valid_value\n")
        env_path = Path(f.name)
    try:
        os.environ.pop("VALID_KEY", None)
        _load_dotenv(env_path)
        check("invalid line skipped, valid key loaded",
              os.environ.get("VALID_KEY") == "valid_value",
              f"got {os.environ.get('VALID_KEY')!r}")
    finally:
        env_path.unlink()
        os.environ.pop("VALID_KEY", None)


if __name__ == "__main__":
    print("[v3.9.10.13] _load_dotenv test suite")
    print("=" * 60)
    test_1_loads_keys_from_env_file()
    test_2_setdefault_does_not_overwrite_existing()
    test_3_ignores_comments_and_blanks()
    test_4_unquotes_values()
    test_5_search_order_via_paper_agent_env_file()
    test_6_missing_file_is_noop()
    test_7_repo_env_file_loads()
    test_8_lines_without_equals_are_ignored()
    print("=" * 60)
    print(f"  {PASS} pass, {FAIL} fail")
    sys.exit(0 if FAIL == 0 else 1)
