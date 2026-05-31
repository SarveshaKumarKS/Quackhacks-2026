#!/usr/bin/env python3
import sys
import os
import tempfile
import unittest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from memory import MemoryStore


class TestMemory(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
        self.tmp.close()
        # project_id="" disables the BigQuery mirror so tests stay offline.
        self.store = MemoryStore(project_id="", local_path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_save_and_recall_recency(self):
        self.store.save("interaction", "first goal")
        self.store.save("interaction", "second goal")
        contents = self.store.recall_contents(limit=2)
        self.assertEqual(contents[0], "second goal")  # most recent first

    def test_recall_by_type(self):
        self.store.save("preference", "client_details: sam@x.com")
        self.store.save("action_log", "sent an email")
        prefs = self.store.recall_contents(memory_type="preference")
        self.assertEqual(prefs, ["client_details: sam@x.com"])

    def test_recall_by_query_ranks_overlap(self):
        self.store.save("interaction", "researched nvidia gpu pricing")
        self.store.save("interaction", "drafted a birthday email")
        top = self.store.recall(query="what is the nvidia gpu news", limit=1)
        self.assertIn("nvidia", top[0]["content"])

    def test_recall_context_filters_noise(self):
        self.store.save("interaction", "completely unrelated topic")
        # No shared terms with the goal -> empty context, not noise.
        self.assertEqual(self.store.recall_context("nvidia gpu pricing"), "")

    def test_recall_context_includes_relevant(self):
        self.store.save("preference", "user prefers concise nvidia summaries")
        ctx = self.store.recall_context("nvidia earnings summary")
        self.assertIn("nvidia", ctx)
        self.assertIn("Relevant memory", ctx)

    def test_empty_store_returns_empty(self):
        self.assertEqual(self.store.recall_contents(), [])
        self.assertEqual(self.store.recall_context("anything"), "")


if __name__ == "__main__":
    unittest.main()
