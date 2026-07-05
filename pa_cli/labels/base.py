"""pa_cli.labels.base — Abstract base class for label generators.

Import from pa_cli.labels, not from here directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LabelGenerator(ABC):
    """Abstract base class for topic label generators.

    To implement a custom generator (e.g. PIEClass, RL policy, LLM):
    1. Subclass this ABC
    2. Implement `name()` and `generate()`
    3. Register via `register_label_generator()` or entry_points
    """

    @abstractmethod
    def name(self) -> str:
        """Return unique short method name."""
        ...

    @abstractmethod
    def generate(
        self,
        papers: List[Dict[str, Any]],
        clusters: List[int],
        tfidf_mat: Any = None,
        filenames: Optional[List[str]] = None,
        concept_data: Optional[Dict[str, Dict]] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Generate topic labels. Returns list of topic dicts matching topics.json schema."""
        ...

    def is_available(self) -> bool:
        return True