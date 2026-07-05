"""pa_cli.labels — Pluggable topic label generation.

This subpackage provides the interface for swapping out the default c-TF-IDF
label generator with custom implementations (e.g. PIEClass, RL-trained policy,
LLM-based labeler).

## Quick start

Use the default generator (c-TF-IDF + handroll fallback):

    from pa_cli.labels import get_label_generator
    gen = get_label_generator("auto")
    topics = gen.generate(...)

## Adding a custom label generator

Two ways to plug in:

### Option 1 — Drop-in subclass (no install, fastest)

1. Create a Python file anywhere importable, e.g.
   `pa_cli/labels/plugins/pieclass.py`:

       from pa_cli.labels import LabelGenerator

       class PieClassLabelGenerator(LabelGenerator):
           def name(self) -> str:
               return "pieclass"
           def generate(self, papers, clusters, **kwargs):
               # your label logic here
               return [...]

2. Register it (one of):
   - Add to `_REGISTRY` in `pa_cli/labels/__init__.py`, OR
   - Call `register_label_generator("pieclass", PieClassLabelGenerator)`

3. Run:
       pa review-topics <corpus> --label-method pieclass

### Option 2 — pip install (cleanest, future)

Create a PyPI package with:

    # setup.py
    setup(
        name="pa-cli-labels-pieclass",
        entry_points={
            "pa_cli.labels": [
                "pieclass = my_pkg:PieClassLabelGenerator",
            ],
        },
    )

After `pip install pa-cli-labels-pieclass`, it auto-loads.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from .domain_stopwords import (
    extract_domain_stopwords,
    load_domain_stopwords_file,
    save_domain_stopwords,
)


class LabelGenerator(ABC):
    """Abstract base class for topic label generators.

    All label generators must produce a list of topic dicts matching the
    topics.json schema (topic_id, label, keywords, paper_count, filenames, ...).

    To implement a custom generator:
    1. Subclass this ABC
    2. Implement `name()` and `generate()`
    3. Optionally override `is_available()` to check deps/config
    """

    @abstractmethod
    def name(self) -> str:
        """Return unique short method name.

        Must be lowercase, no spaces. Used in:
        - --label-method CLI flag
        - topics.json "label_method" field
        """
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
        """Generate topic labels for the given clusters.

        Args:
            papers: corpus metadata list. Each dict has
                    {path, filename, title, text, doi?, ...}
            clusters: cluster id per paper (-1 = outlier).
            tfidf_mat: pre-computed TF-IDF matrix (may be None).
            filenames: paper filenames parallel to `clusters`.
            concept_data: {filename: {doi, title, concepts: [...]}}
                          from OpenAlex. May be empty dict.

        Returns:
            List of topic dicts:
                [{
                    "topic_id": int,         # 1-based for non-outliers
                    "label": str,            # human-readable label
                    "keywords": [str, ...],  # top-N keywords
                    "top_concepts": [...],   # optional OpenAlex concepts
                    "paper_count": int,
                    "filenames": [str, ...],
                    "is_outlier_cluster": bool,
                    "cohesion_score": float, # optional
                }, ...]
        """
        ...

    def is_available(self) -> bool:
        """Check if this generator can run (deps installed, config valid).

        Override this to short-circuit expensive imports. Return False to
        signal the caller to fall back to a default generator.
        """
        return True


# Registry of built-in label generators.
# Subclasses can be added via register_label_generator().
_REGISTRY: Dict[str, Type[LabelGenerator]] = {}


def register_label_generator(name: str, cls: Type[LabelGenerator]) -> None:
    """Register a label generator class by name.

    Allows plugins to be added at runtime:
        from pa_cli.labels import register_label_generator
        register_label_generator("pieclass", PieClassLabelGenerator)

    Or by entry_points (set up in plugin's setup.py):
        [pa_cli.labels]
        pieclass = my_pkg:PieClassLabelGenerator
    """
    if not issubclass(cls, LabelGenerator):
        raise TypeError(f"{cls.__name__} must subclass LabelGenerator")
    _REGISTRY[name] = cls


def get_label_generator(method: str, **kwargs: Any) -> LabelGenerator:
    """Factory: get a label generator by name.

    Args:
        method: One of {"auto", "ctfidf", "handroll", "custom",
                        or any registered custom name}.
        **kwargs: Passed to the generator's constructor.

    Returns:
        LabelGenerator instance.

    Raises:
        ValueError: if method is unknown.
    """
    # Lazy-load built-in generators to avoid circular imports
    if not _REGISTRY:
        _load_builtin_generators()

    # Auto = same as ctfidf (kept as alias for backwards compat)
    if method == "auto":
        method = "ctfidf"

    if method not in _REGISTRY:
        available = sorted(set(list(_REGISTRY.keys()) + ["auto"]))
        raise ValueError(
            f"Unknown label method '{method}'. "
            f"Available: {available}. "
            f"To add a custom method, see pa_cli/labels/__init__.py docstring."
        )

    return _REGISTRY[method](**kwargs)


def _load_builtin_generators() -> None:
    """Lazy-load built-in label generators."""
    from .ctfidf import CTFIDFLabelGenerator
    from .custom import CustomLabelGenerator
    from .handroll import HandrollLabelGenerator

    _REGISTRY["ctfidf"] = CTFIDFLabelGenerator
    _REGISTRY["handroll"] = HandrollLabelGenerator
    _REGISTRY["custom"] = CustomLabelGenerator


def available_methods() -> List[str]:
    """Return all available label method names (built-in + registered)."""
    if not _REGISTRY:
        _load_builtin_generators()
    return sorted(_REGISTRY.keys())


def __getattr__(name: str):
    """Lazy attribute access for label generator classes.

    Allows `from pa_cli.labels import CustomLabelGenerator` without
    paying import cost until the class is actually used.
    """
    _GENERATORS = {
        "CTFIDFLabelGenerator": ".ctfidf",
        "HandrollLabelGenerator": ".handroll",
        "CustomLabelGenerator": ".custom",
    }
    if name in _GENERATORS:
        from importlib import import_module
        module = import_module(_GENERATORS[name], __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "LabelGenerator",
    "CTFIDFLabelGenerator",
    "HandrollLabelGenerator",
    "CustomLabelGenerator",
    "register_label_generator",
    "get_label_generator",
    "available_methods",
    "extract_domain_stopwords",
    "load_domain_stopwords_file",
    "save_domain_stopwords",
]