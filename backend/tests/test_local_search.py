import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from db import facts


class LocalSemanticSearchTests(unittest.TestCase):
    def test_ranks_by_cosine_and_ignores_incompatible_vectors(self):
        collection = MagicMock()
        collection.find.return_value = [
            {"fact": "unrelated", facts.VECTOR_FIELD: [0, 3]},
            {"fact": "closest", facts.VECTOR_FIELD: [5, 0]},
            {"fact": "similar", facts.VECTOR_FIELD: [1, 1]},
            {"fact": "old dimensions", facts.VECTOR_FIELD: [1, 0, 0]},
            {"fact": "zero", facts.VECTOR_FIELD: [0, 0]},
        ]
        with patch.dict(os.environ, {"MONGODB_VECTOR_SEARCH": "local"}), patch.object(facts, "get_db", return_value=SimpleNamespace(user_facts=collection)), patch.object(facts, "embed_query", return_value=[1, 0]):
            result = facts.get_relevant_facts("reader", "question", limit=2)

        self.assertEqual(result, ["closest", "similar"])
        self.assertEqual(collection.find.call_args.args[0]["user_id"], "reader")
        collection.aggregate.assert_not_called()

    def test_local_startup_does_not_require_atlas_search(self):
        db = MagicMock()
        with patch.dict(os.environ, {"MONGODB_VECTOR_SEARCH": "local"}), patch.object(facts, "get_db", return_value=db):
            facts.ensure_vector_index()
        db.command.assert_called_once_with("ping")
        db.user_facts.list_search_indexes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
