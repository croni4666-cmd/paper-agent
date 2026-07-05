"""HandrollLabelGenerator — TF-IDF + Jaccard + Agglomerative clustering.

Pass-through implementation. The actual hand-roll clustering happens
inside topics.cluster_topics() (used when n<5 or BERTopic unavailable).
This generator's role is to apply custom label overrides + return
the topics list, same as CTFIDFLabelGenerator.

Architecturally, "handroll" vs "ctfidf" label generators behave identically
post-clustering — both are pass-through with optional custom overlay.
The difference is in which clustering algorithm topics.cluster_topics()
uses internally (BERTopic c-TF-IDF vs hand-roll TF-IDF + Jaccard +
Agglomerative), which is selected by `force_method` not by the label
generator.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import LabelGenerator

log = logging.getLogger(__name__)


class HandrollLabelGenerator(LabelGenerator):
    """Hand-roll TF-IDF + Jaccard + Agglomerative (pass-through with custom overlay).

    Args:
        custom_labels: Optional dict {topic_id: label_str} to override.

    Behavior:
        - If `topics` kwarg is passed: applies custom_labels overlay,
          returns updated topics list.
        - If `topics` kwarg is missing: returns [] + warning.
    """

    def __init__(
        self,
        custom_labels: Optional[Dict[int, str]] = None,
    ) -> None:
        self.custom_labels = {int(k): str(v) for k, v in (custom_labels or {}).items()}

    def name(self) -> str:
        return "handroll"

    def generate(
        self,
        papers: List[Dict[str, Any]],
        clusters: List[int],
        tfidf_mat: Any = None,
        filenames: Optional[List[str]] = None,
        concept_data: Optional[Dict[str, Dict]] = None,
        topics: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        if topics is None:
            log.warning(
                "HandrollLabelGenerator.generate() called without `topics` kwarg. "
                "Use topics.cluster_topics(label_method='handroll', ...) for the full pipeline. "
                "Returning empty list."
            )
            return []

        if not self.custom_labels:
            return topics

        # Apply custom label overlay
        result = []
        for topic in topics:
            tid = topic.get("topic_id")
            new_topic = dict(topic)
            if tid in self.custom_labels:
                new_topic["label"] = self.custom_labels[tid]
                log.info(
                    f"HandrollLabelGenerator: overrode topic {tid} label: "
                    f"'{topic.get('label')}' → '{self.custom_labels[tid]}'"
                )
            result.append(new_topic)
        return result