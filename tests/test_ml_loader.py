import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from modules.ml import loader


class ModelLoaderTests(unittest.TestCase):
    def setUp(self):
        with loader._MODEL_LOAD_LOCK:
            self.original_cache = loader._MODEL_CACHE.copy()
            loader._MODEL_CACHE.clear()

    def tearDown(self):
        with loader._MODEL_LOAD_LOCK:
            loader._MODEL_CACHE.clear()
            loader._MODEL_CACHE.update(self.original_cache)

    def test_concurrent_first_use_deserializes_once(self):
        model = {"model": "shared"}

        def deserialize(_path):
            time.sleep(0.02)
            return model

        with patch.object(loader, "_joblib_load", side_effect=deserialize) as load:
            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(lambda _: loader.get_burnout_model(), range(16)))

        self.assertEqual(load.call_count, 1)
        self.assertTrue(all(result is model for result in results))


if __name__ == "__main__":
    unittest.main()
