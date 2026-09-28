import unittest
from unittest.mock import Mock, patch

from agent.src.embeddings.client import EmbeddingClient


class EmbeddingClientTests(unittest.TestCase):
    @patch("agent.src.embeddings.client.httpx.post")
    def test_cloud_request_pins_database_dimension(self, post: Mock) -> None:
        post.return_value.json.return_value = {
            "data": [{"index": 0, "embedding": [0.1, 0.2]}]
        }
        client = EmbeddingClient(dimensions=1024, send_dimensions=True)
        self.assertEqual(client.embed(["course"]), [[0.1, 0.2]])
        self.assertEqual(post.call_args.kwargs["json"]["dimensions"], 1024)

    @patch("agent.src.embeddings.client.httpx.post")
    def test_local_provider_can_omit_dimensions(self, post: Mock) -> None:
        post.return_value.json.return_value = {
            "data": [{"index": 0, "embedding": [0.1, 0.2]}]
        }
        EmbeddingClient(send_dimensions=False).embed(["course"])
        self.assertNotIn("dimensions", post.call_args.kwargs["json"])


if __name__ == "__main__":
    unittest.main()
