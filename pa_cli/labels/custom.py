"""CustomLabelGenerator — User-supplied label override.

This is the highest-priority label generator. When users provide a
{topic_id: label_str} dict, this generator overrides the c-TF-IDF auto-label.

Usage:
    pa review-topics <corpus> --custom-labels '{"0": "PPT 设计文档", "1": "PPT 内容来源"}'

The label override is applied as a post-processing step on the topics list
returned by cluster_topics() — it does NOT affect clustering.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import LabelGenerator

log = logging.getLogger(__name__)


class CustomLabelGenerator(LabelGenerator):
    """Apply user-supplied label overrides to existing topics.

    This is a post-processor — call after cluster_topics() has produced
    the topics list. Replaces `label` field for each topic whose topic_id
    appears in custom_labels dict.

    Args:
        custom_labels: Dict {topic_id: label_str}.
                       topic_id is the 1-based index from topics.json
                       (matches topic["topic_id"] in cluster output).
                       Outlier topic (-1) is not assignable; topic_id=0
                       is reserved for the "all outliers" sentinel.
        strict: If True, raise ValueError when a custom_label topic_id
                doesn't match any cluster. If False (default), warn + skip.
    """

    def __init__(
        self,
        custom_labels: Optional[Dict[int, str]] = None,
        strict: bool = False,
    ) -> None:
        if not custom_labels:
            raise ValueError(
                "CustomLabelGenerator requires non-empty custom_labels. "
                "Use get_label_generator('ctfidf') instead."
            )
        # Normalize keys to int
        self.custom_labels: Dict[int, str] = {
            int(k): str(v) for k, v in custom_labels.items()
        }
        self.strict = strict

    def name(self) -> str:
        return "custom"

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
        """Apply custom label overrides to existing topics.

        Args:
            topics: List of topic dicts from cluster_topics() output.
                    Must be passed via kwargs when calling standalone.

        Returns:
            Updated topics list with overridden labels.
        """
        if topics is None:
            raise ValueError(
                "CustomLabelGenerator.generate() requires `topics` kwarg. "
                "It is a post-processor; pass cluster_topics() output."
            )

        result = []
        for topic in topics:
            tid = topic.get("topic_id")
            new_topic = dict(topic)  # shallow copy
            if tid in self.custom_labels:
                new_topic["label"] = self.custom_labels[tid]
                log.info(
                    f"CustomLabelGenerator: overrode topic {tid} label: "
                    f"'{topic.get('label')}' → '{self.custom_labels[tid]}'"
                )
            elif self.strict and self.custom_labels:
                # user supplied labels but this topic isn't covered
                log.warning(
                    f"CustomLabelGenerator: topic_id {tid} has no custom label; "
                    f"keeping auto label '{topic.get('label')}'"
                )
            result.append(new_topic)

        return result

    def is_available(self) -> bool:
        return bool(self.custom_labels)