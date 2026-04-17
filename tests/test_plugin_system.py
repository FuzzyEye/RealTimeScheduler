import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.registry import registry
from src.plugins import load_plugin


class TestPluginSystem(unittest.TestCase):
    def setUp(self):
        registry._strategies.clear()

    def tearDown(self):
        registry._strategies.clear()

    def test_register_and_list(self):
        registry.register("custom_test", {
            "type": "dynamic",
            "selector": "earliest_deadline",
            "description": "Test plugin"
        })
        names = registry.list_names()
        self.assertIn("custom_test", names)

    def test_conditional_strategy_validation(self):
        registry.register("edf", {"type": "dynamic", "selector": "earliest_deadline", "params": {}})
        registry.register("cond", {
            "type": "conditional",
            "condition": {"metric": "laxity", "operator": "lt", "value": 2.0},
            "true_branch": "edf",
            "false_branch": "edf",
        })
        ok, msg = registry.validate("cond")
        self.assertTrue(ok)

    def test_conditional_unknown_branch(self):
        registry.register("bad_cond", {
            "type": "conditional",
            "condition": {"metric": "laxity", "operator": "lt", "value": 2.0},
            "true_branch": "nonexistent",
            "false_branch": "edf",
        })
        ok, msg = registry.validate("bad_cond")
        self.assertFalse(ok)
        self.assertIn("true_branch", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
