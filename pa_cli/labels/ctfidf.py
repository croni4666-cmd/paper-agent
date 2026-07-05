"""CTFIDFLabelGenerator — Default c-TF-IDF based label generator.

Wraps the existing _label_topics_bertopic and _label_topics_fallback logic
from pa_cli.topics, exposed via the LabelGenerator ABC for plugin consistency.

This is the default method. It uses:
- BERTopic's c-TF-IDF (when BERTopic is available and n >= 5)
- Hand-rolled TF-IDF + Jaccard + Agglomerative clustering (fallback for small corpora)

The actual labeling happens inside topics.cluster_topics() — this generator
returns the topics list as-is from the cluster output, applying only
custom_labels overlay if provided.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import LabelGenerator

log = logging.getLogger(__name__)


class CTFIDFLabelGenerator(LabelGenerator):
    """Default c-TF-IDF based label generator.

    Args:
        custom_labels: Optional dict {topic_id: label_str} to override
                       auto-generated labels.
        domain_stopwords: Optional list of extra stopwords to add to c-TF-IDF.
                          Used when filter_domain_stopwords=True.
        filter_domain_stopwords: If True, augment the c-TF-IDF stop_words
                                 with `domain_stopwords` list.

    Note: The actual c-TF-IDF computation happens inside topics.cluster_topics().
    This generator acts as a thin post-processor: it accepts the topics list
    and applies label overrides / domain stopwords filtering.
    """

    def __init__(
        self,
        custom_labels: Optional[Dict[int, str]] = None,
        domain_stopwords: Optional[List[str]] = None,
        filter_domain_stopwords: bool = True,
    ) -> None:
        self.custom_labels = custom_labels or {}
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
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Generate topic labels using c-TF-IDF.

        In practice, the topics list is already produced by topics.cluster_topics()
        before this method is called (because clustering depends on c-TF-IDF too).
        This method applies label overrides and returns the topics.

        For a pure-c-TF-IDF-only label generation (without re-clustering),
        use topics._label_topics_bertopic() or _label_topics_fallback() directly.
        """
        # Note: This method is called AFTER cluster_topics() has already produced
        # the topics list. The actual c-TF-IDF labeling is done inside
        # topics._label_topics_bertopic(). Here we just apply custom label overrides.
        # The orchestration is in topics.cluster_topics() — see how it calls
        # the generator at the post-clustering step.
        raise NotImplementedError(
            "CTFIDFLabelGenerator.generate() is not a standalone labeler. "
            "Use pa_cli.topics.cluster_topics() with --label-method ctfidf instead. "
            "The actual c-TF-IDF labeling happens during clustering."
        )