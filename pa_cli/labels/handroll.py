"""HandrollLabelGenerator — TF-IDF + Jaccard + Agglomerative clustering.

Wraps the existing hand-roll fallback from pa_cli.topics. Used when n<5
or BERTopic is unavailable. Like CTFIDFLabelGenerator, the actual labeling
happens inside topics.cluster_topics() — this is a thin post-processor.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import LabelGenerator

log = logging.getLogger(__name__)


class HandrollLabelGenerator(LabelGenerator):
    """TF-IDF + Jaccard + Agglomerative clustering (hand-roll fallback).

    Like CTFIDFLabelGenerator, this is a post-processor. The actual clustering
    happens inside topics.cluster_topics() (handroll branch). This class exists
    for plugin consistency and to expose custom label overrides.
    """

    def __init__(
        self,
        custom_labels: Optional[Dict[int, str]] = None,
    ) -> None:
        self.custom_labels = custom_labels or {}

    def name(self) -> str:
        return "handroll"

    def generate(
        self,
        papers: List[Dict[str, Any]],
        clusters: List[int],
        tfidf_mat: Any = None,
        filenames: Optional[List[str]] = None,
        concept_data: Optional[Dict[str, Dict]] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "HandrollLabelGenerator.generate() is not a standalone labeler. "
            "Use pa_cli.topics.cluster_topics() with --label-method handroll instead."
        )