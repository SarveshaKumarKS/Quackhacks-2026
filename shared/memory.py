"""
Local-first agent memory with an optional BigQuery write-through mirror.

Why local-first: the previous implementation only wrote to BigQuery, which
silently no-ops without GCP credentials — so in the common case there was no
memory at all and nothing was ever recalled. This store always persists to a
local JSONL file (durable, offline, fast) and best-effort mirrors to BigQuery
when GCP_PROJECT_ID is set. Recall reads from the local store so it works
everywhere and is cheap to feed back into the model on every task.

Record shape: {id, session_id, memory_type, content, created_at}.
"""
import os
import re
import json
import datetime
from typing import List, Dict, Any, Optional

DEFAULT_SESSION = "doppelganger_session"

_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "is", "it",
    "this", "that", "my", "me", "i", "please", "with", "about", "you", "your",
}


def _default_local_path() -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, "doppelganger_memory.jsonl")


def _tokenize(text: str) -> set:
    return {
        w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
        if w not in _STOPWORDS and len(w) > 1
    }


class MemoryStore:
    def __init__(self, project_id: Optional[str] = None,
                 local_path: Optional[str] = None,
                 session_id: str = DEFAULT_SESSION):
        self.project_id = project_id if project_id is not None else os.getenv("GCP_PROJECT_ID")
        self.local_path = local_path or _default_local_path()
        self.session_id = session_id

    # --- write ---------------------------------------------------------
    def save(self, memory_type: str, content: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        rec = {
            "id": int(datetime.datetime.now().timestamp() * 1000),
            "session_id": session_id or self.session_id,
            "memory_type": memory_type,
            "content": content,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._save_local(rec)
        self._save_bigquery(rec)  # best effort, never raises
        return rec

    def _save_local(self, rec: Dict[str, Any]) -> None:
        try:
            with open(self.local_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception as e:
            print(f"[Memory] Local save failed: {e}")

    def _save_bigquery(self, rec: Dict[str, Any]) -> None:
        if not self.project_id:
            return
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=self.project_id)
            table_ref = f"{self.project_id}.doppelganger_dataset.agent_memory"
            errors = client.insert_rows_json(table_ref, [rec])
            if errors:
                print(f"[Memory] BQ insert errors: {errors}")
        except Exception as e:
            print(f"[Memory] BQ mirror skipped: {e}")

    # --- read ----------------------------------------------------------
    def _load_local(self) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []
        try:
            if os.path.exists(self.local_path):
                with open(self.local_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            recs.append(json.loads(line))
                        except Exception:
                            continue
        except Exception as e:
            print(f"[Memory] Local load failed: {e}")
        return recs

    def recall(self, memory_type: Optional[str] = None,
               query: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Return up to `limit` records. With a query, rank by keyword overlap then
        recency; without one, return most-recent-first."""
        recs = self._load_local()  # file/append order == chronological (oldest first)
        if memory_type:
            recs = [r for r in recs if r.get("memory_type") == memory_type]
        # Rank by append position (higher index == more recent) so same-millisecond
        # saves still order correctly; with a query, keyword overlap takes precedence.
        indexed = list(enumerate(recs))
        if query:
            terms = _tokenize(query)
            indexed.sort(
                key=lambda t: (len(terms & _tokenize(t[1].get("content", ""))), t[0]),
                reverse=True,
            )
        else:
            indexed.sort(key=lambda t: t[0], reverse=True)
        return [t[1] for t in indexed[:limit]]

    def recall_contents(self, memory_type: Optional[str] = None,
                        query: Optional[str] = None, limit: int = 5) -> List[str]:
        return [r.get("content", "") for r in self.recall(memory_type, query, limit)]

    def recall_context(self, goal: str, limit: int = 5) -> str:
        """Formatted block of relevant past memories to inject into a prompt."""
        recs = self.recall(query=goal, limit=limit)
        # Drop zero-overlap noise: only include memories that share a term with the goal.
        terms = _tokenize(goal)
        recs = [r for r in recs if terms & _tokenize(r.get("content", ""))]
        if not recs:
            return ""
        lines = ["Relevant memory from past interactions (use if helpful):"]
        for r in recs:
            lines.append(f"- ({r.get('memory_type', 'note')}) {r.get('content', '')}")
        return "\n".join(lines)
