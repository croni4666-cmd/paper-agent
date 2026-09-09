import pytest
import tempfile
from pathlib import Path
from pa_cli import cache, pdf_validation  # Bind real validation supervisor before download mocks.


@pytest.fixture(autouse=True)
def isolate_pdf_cache(monkeypatch):
    """Formal tests must never populate or remove the user's PDF cache."""
    with tempfile.TemporaryDirectory(prefix='paper-agent-cache-test-') as directory:
        monkeypatch.setenv('PA_CACHE_DIR', directory)
        monkeypatch.setattr(cache, 'DEFAULT_CACHE_ROOT', Path(directory))
        yield
