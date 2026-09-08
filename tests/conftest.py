import pytest
import tempfile


@pytest.fixture(autouse=True)
def isolate_pdf_cache(monkeypatch):
    """Formal tests must never populate or remove the user's PDF cache."""
    with tempfile.TemporaryDirectory(prefix='paper-agent-cache-test-') as directory:
        monkeypatch.setenv('PA_CACHE_DIR', directory)
        yield
