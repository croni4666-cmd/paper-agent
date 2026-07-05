"""CTFIDFLabelGenerator — Default c-TF-IDF based label generator.

Acts as a pass-through: the actual c-TF-IDF computation happens inside
topics.cluster_topics() (because clustering depends on c-TF-IDF too).
This generator's role is to optionally apply custom label overrides +
domain stopwords filtering to the topics list produced by cluster_topics().

Architecture note: The actual clustering + c-TF-IDF labeling is done in
topics._cluster_with_bertopic() and topics._cluster_with_handroll().
This generator is a thin post-processor, but **does implement** the ABC
for plugin consistency (so users can swap ctfidf ↔ handroll ↔ custom ↔
future PIEClass without changing call sites).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import LabelGenerator

log = logging.getLogger(__name__)


class CTFIDFLabelGenerator(LabelGenerator):
    """Default c-TF-IDF based label generator (pass-through with custom overlay).

    Args:
        custom_labels: Optional dict {topic_id: label_str} to override
                       auto-generated labels.
        domain_stopwords: Optional list of extra stopwords (currently logged
                          for visibility; actual application happens in
                          topics.cluster_topics() before this generator is
                          called).
        filter_domain_stopwords: Currently informational only — see
                                 topics.cluster_topics() for actual stopword
                                 application.

    Behavior:
        - If `topics` kwarg is passed (post-cluster_topics() output):
          applies custom_labels overlay, returns updated topics list.
        - If `topics` kwarg is missing: returns [] with a warning. Use
          topics.cluster_topics() with label_method="ctfidf" to do the
          full pipeline.
    """

    def __init__(
        self,
        custom_labels: Optional[Dict[int, str]] = None,
        domain_stopwords: Optional[List[str]] = None,
        filter_domain_stopwords: bool = True,
    ) -> None:
        self.custom_labels = {int(k): str(v) for k, v in (custom_labels or {}).items()}
        self.domain_stopwords = list(domain_stopwords or [])
        self.filter_domain_stopwords = filter_domain_stopwords

    def name(self) -> str:
        return "ctfidf"

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
        """Apply custom label overrides to existing topics (post-cluster_topics pass-through).

        For standalone use without a prior cluster_topics() call, this
        returns [] + warning. The full pipeline is `topics.cluster_topics(
        label_method="ctfidf", custom_labels=..., domain_stopwords=...)`.
        """
        if topics is None:
            log.warning(
                "CTFIDFLabelGenerator.generate() called without `topics` kwarg. "
                "Use topics.cluster_topics(label_method='ctfidf', ...) for the full pipeline. "
                "Returning empty list."
            )
            return []

        if not self.custom_labels:
            return topics

        # Apply custom label overlay (same logic as CustomLabelGenerator)
        result = []
        for topic in topics:
            tid = topic.get("topic_id")
            new_topic = dict(topic)
            if tid in self.custom_labels:
                new_topic["label"] = self.custom_labels[tid]
                log.info(
                    f"CTFIDFLabelGenerator: overrode topic {tid} label: "
                    f"'{topic.get('label')}' → '{self.custom_labels[tid]}'"
                )
            result.append(new_topic)
        return result