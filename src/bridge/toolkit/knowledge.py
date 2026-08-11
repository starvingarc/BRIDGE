from __future__ import annotations

import gzip
import json
from importlib.resources import files
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer

from bridge.toolkit.contracts import KnowledgeHit


_QUERY_EXPANSIONS = {
    "环境rna": "ambient RNA contamination SoupX CellBender",
    "环境 rna": "ambient RNA contamination SoupX CellBender",
    "校正矩阵": "corrected counts corrected matrix",
    "双细胞": "doublet Scrublet scDblFinder",
    "原始counts": "raw counts",
    "原始 counts": "raw counts",
    "细胞注释": "cell state annotation",
    "发育": "developmental stage trajectory",
    "移植": "graft transplantation",
}


class KnowledgeRegistry:
    """Read-only search over a versioned BRIDGE knowledge snapshot."""

    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot
        self.snapshot_id = str(snapshot["snapshot_id"])
        self.methods = list(snapshot["methods"])
        self.sources = list(snapshot["sources"])
        self.bindings = list(snapshot["bindings"])
        self.documents = list(snapshot["documents"])
        self._vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            lowercase=True,
            sublinear_tf=True,
        )
        texts = [str(document["retrieval_text"]) for document in self.documents]
        self._matrix = self._vectorizer.fit_transform(texts) if texts else None

    @classmethod
    def load_default(cls) -> "KnowledgeRegistry":
        resource = files("bridge.resources").joinpath("knowledge_snapshot.json.gz")
        with resource.open("rb") as raw_handle:
            with gzip.GzipFile(fileobj=raw_handle, mode="rb") as gzip_handle:
                snapshot = json.loads(gzip_handle.read().decode("utf-8"))
        return cls(snapshot)

    def validation_summary(self) -> dict[str, Any]:
        method_ids = {method["method_id"] for method in self.methods}
        source_ids = {source["source_id"] for source in self.sources}
        dangling_method_refs = sorted(
            {
                binding["method_id"]
                for binding in self.bindings
                if binding["method_id"] not in method_ids
            }
            | {
                method_id
                for document in self.documents
                for method_id in document["method_ids"]
                if method_id not in method_ids
            }
        )
        dangling_source_refs = sorted(
            {
                source_id
                for method in self.methods
                for source_id in method["source_ids"]
                if source_id not in source_ids
            }
            | {
                source_id
                for document in self.documents
                for source_id in document["source_ids"]
                if source_id not in source_ids
            }
        )
        expected = dict(self.snapshot["summary"])
        observed = {
            "binding_count": len(self.bindings),
            "method_count": len(self.methods),
            "raw_url_token_count": int(expected["raw_url_token_count"]),
            "public_url_assignment_count": int(expected["public_url_assignment_count"]),
            "canonical_url_token_count": sum(
                int(method["raw_source_token_count"]) for method in self.methods
            ),
            "canonical_public_url_assignment_count": sum(
                int(method["public_source_assignment_count"]) for method in self.methods
            ),
            "raw_distinct_public_url_count": int(expected["raw_distinct_public_url_count"]),
            "canonical_public_source_count": len(self.sources),
            "verified_public_source_count": sum(
                str(source["verification_status"]).startswith("verified")
                for source in self.sources
            ),
            "unassigned_evidence_family_count": sum(
                not binding["evidence_family_raw"] for binding in self.bindings
            ),
            "formal_eligible_method_count": sum(bool(method["formal_eligible"]) for method in self.methods),
        }
        return {
            "valid": not dangling_method_refs
            and not dangling_source_refs
            and all(observed[key] == expected[key] for key in observed),
            **observed,
            "dangling_method_refs": dangling_method_refs,
            "dangling_source_refs": dangling_source_refs,
            "snapshot_id": self.snapshot_id,
            "content_hash": self.snapshot["content_hash"],
        }

    def get_record(self, knowledge_id: str) -> dict[str, Any]:
        """Return the complete Method or Source snapshot record for an exact ID."""
        retrievable_method_ids = {
            method_id
            for document in self.documents
            for method_id in document["method_ids"]
        }
        for method in self.methods:
            if method.get("method_id") == knowledge_id and knowledge_id in retrievable_method_ids:
                return method
        for source in self.sources:
            if source.get("source_id") != knowledge_id:
                continue
            if set(source["method_ids"]).issubset(retrievable_method_ids):
                return source
        raise KeyError(knowledge_id)

    def search(
        self,
        query: str,
        *,
        module_id: str | None = None,
        method_id: str | None = None,
        source_type: str | None = None,
        scientific_status: str | None = None,
        allowed_use: str | None = None,
        limit: int = 10,
    ) -> list[KnowledgeHit]:
        if not query.strip() or limit < 1 or self._matrix is None:
            return []
        expanded_query = _expand_query(query)
        query_vector = self._vectorizer.transform([expanded_query])
        similarities = (self._matrix @ query_vector.T).toarray().ravel()
        source_lookup = {source["source_id"]: source for source in self.sources}
        method_lookup = {method["method_id"]: method for method in self.methods}
        ranked: list[tuple[float, int]] = []
        for index, (document, score) in enumerate(zip(self.documents, similarities, strict=True)):
            if module_id and module_id not in document["tool_package_ids"]:
                continue
            if method_id and method_id not in document["method_ids"]:
                continue
            if source_type and not any(
                source_lookup[source_id]["source_type"] == source_type
                for source_id in document["source_ids"]
            ):
                continue
            if scientific_status and not any(
                scientific_status in method_lookup[item]["scientific_status_raw"]
                for item in document["method_ids"]
            ):
                continue
            if allowed_use and allowed_use not in document["allowed_use"]:
                continue
            if score <= 0:
                continue
            if not document["source_ids"]:
                score *= 0.5
            ranked.append((float(score), index))
        ranked.sort(key=lambda pair: (-pair[0], self.documents[pair[1]]["document_id"]))
        return [self._to_hit(self.documents[index], score, query) for score, index in ranked[:limit]]

    def _to_hit(self, document: dict[str, Any], score: float, query: str) -> KnowledgeHit:
        return KnowledgeHit(
            document_id=document["document_id"],
            document_type=document["document_type"],
            title=document["title"],
            snippet=_snippet(document["retrieval_text"], query),
            source_ids=document["source_ids"],
            tool_package_ids=document["tool_package_ids"],
            method_ids=document["method_ids"],
            score=score,
            snapshot_id=self.snapshot_id,
        )


def _expand_query(query: str) -> str:
    normalized = query.casefold()
    additions = [terms for phrase, terms in _QUERY_EXPANSIONS.items() if phrase in normalized]
    return " ".join([query, *additions])


def _snippet(text: str, query: str, width: int = 280) -> str:
    compact = " ".join(text.split())
    terms = [term.casefold() for term in query.split() if len(term) > 1]
    lower = compact.casefold()
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    start = max(0, (min(positions) if positions else 0) - 60)
    end = min(len(compact), start + width)
    prefix = "..." if start else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end]}{suffix}"
