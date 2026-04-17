import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.task import Task
from src.simulator import SimulationEngine
from src.registry import registry
from src.selectors import (
    earliest_deadline_selector, least_laxity_selector,
    earliest_arrival_selector, highest_priority_selector,
    shortest_period_selector, get_selector
)
from src.config import Config, ConfigTask, ConfigSimulation, ConfigStrategy


class TestTask(unittest.TestCase):
    def test_periodic_task_deadline(self):
        t = Task(name="T1", execution_time=1.0, period=4.0, deadline=4.0, arrival_time=0.0)
        self.assertEqual(t.absolute_deadline, 4.0)
        self.assertEqual(t.absolute_arrival, 0.0)
        self.assertTrue(t.is_periodic())

    def test_aperiodic_task(self):
        t = Task(name="A1", execution_time=1.5, arrival_time=2.0, deadline=5.0)
        self.assertFalse(t.is_periodic())
        self.assertEqual(t.absolute_deadline, 7.0)

    def test_laxity(self):
        t = Task(name="T1", execution_time=2.0, period=5.0, deadline=5.0, arrival_time=0.0)
        self.assertEqual(t.laxity(0.0), 3.0)
        self.assertEqual(t.laxity(1.0), 2.0)
        t.advance(1.0)
        self.assertEqual(t.laxity(1.0), 3.0)

    def test_task_copy(self):
        t = Task(name="T1", execution_time=1.0, period=4.0, arrival_time=0.0)
        c = t.copy()
        self.assertEqual(c.name, t.name)
        self.assertEqual(c.instance_id, t.instance_id)
        self.assertEqual(c.remaining_time, t.remaining_time)


class TestSelectors(unittest.TestCase):
    def setUp(self):
        self.tasks = [
            Task(name="T1", execution_time=1.0, period=4.0, arrival_time=0.0, priority=1),
            Task(name="T2", execution_time=2.0, period=6.0, arrival_time=0.0, priority=2),
            Task(name="T3", execution_time=1.5, period=3.0, arrival_time=0.0, priority=3),
        ]

    def test_earliest_deadline(self):
        result = earliest_deadline_selector(self.tasks, 0.0)
        self.assertEqual(result.name, "T3")

    def test_highest_priority(self):
        result = highest_priority_selector(self.tasks, 0.0)
        self.assertEqual(result.name, "T1")

    def test_shortest_period(self):
        result = shortest_period_selector(self.tasks, 0.0)
        self.assertEqual(result.name, "T3")

    def test_empty_queue(self):
        self.assertIsNone(earliest_deadline_selector([], 0.0))
        self.assertIsNone(least_laxity_selector([], 0.0))

    def test_get_selector_invalid(self):
        with self.assertRaises(ValueError):
            get_selector("nonexistent")


class TestRegistry(unittest.TestCase):
    def setUp(self):
        registry._strategies.clear()

    def tearDown(self):
        registry._strategies.clear()

    def test_register_and_get(self):
        registry.register("test", {"type": "dynamic", "selector": "earliest_deadline"})
        self.assertIn("test", registry.list_names())
        self.assertEqual(registry.get("test")["type"], "dynamic")

    def test_validate_dynamic_ok(self):
        registry.register("edf", {"type": "dynamic", "selector": "earliest_deadline"})
        ok, msg = registry.validate("edf")
        self.assertTrue(ok)

    def test_validate_dynamic_missing_selector(self):
        registry.register("bad", {"type": "dynamic"})
        ok, msg = registry.validate("bad")
        self.assertFalse(ok)
        self.assertIn("missing", msg)

    def test_validate_unknown_strategy(self):
        ok, msg = registry.validate("nonexistent")
        self.assertFalse(ok)

    def test_validate_round_robin(self):
        registry.register("rr", {"type": "round_robin", "params": {"quantum": 1.0}})
        ok, msg = registry.validate("rr")
        self.assertTrue(ok)


class TestSimulation(unittest.TestCase):
    def setUp(self):
        registry._strategies.clear()
        for s in [
            {"name": "edf", "type": "dynamic", "selector": "earliest_deadline", "params": {}},
            {"name": "rms", "type": "fixed_priority", "priority_key": "period", "params": {}},
            {"name": "fcfs", "type": "queue", "selector": "earliest_arrival", "params": {}},
            {"name": "rr", "type": "round_robin", "params": {"quantum": 1.0}},
        ]:
            registry.register(s["name"], s)

    def test_edf_single_task(self):
        tasks = [Task(name="T1", execution_time=2.0, period=4.0, arrival_time=0.0, instance_id=0)]
        sim = SimulationEngine(tasks, 0.0, 10.0, "edf")
        result = sim.run()
        self.assertGreater(result.throughput(), 0)

    def test_edf_three_periodic_tasks(self):
        tasks = []
        for i in range(3):
            tasks.append(Task(
                name="T1", execution_time=1.0, period=4.0,
                arrival_time=0.0, instance_id=i
            ))
            tasks.append(Task(
                name="T2", execution_time=2.0, period=6.0,
                arrival_time=0.0, instance_id=i
            ))

        sim = SimulationEngine(tasks, 0.0, 12.0, "edf")
        result = sim.run()
        self.assertGreater(result.throughput(), 0)
        self.assertGreaterEqual(result.cpu_utilization(), 0)

    def test_rr_scheduler(self):
        tasks = [
            Task(name="T1", execution_time=2.0, period=4.0, arrival_time=0.0, instance_id=0),
            Task(name="T2", execution_time=2.0, period=4.0, arrival_time=0.0, instance_id=0),
        ]
        sim = SimulationEngine(tasks, 0.0, 8.0, "rr")
        result = sim.run()
        self.assertGreater(result.throughput(), 0)

    def test_invalid_strategy_raises(self):
        tasks = [Task(name="T1", execution_time=1.0, arrival_time=0.0)]
        with self.assertRaises(ValueError):
            SimulationEngine(tasks, 0.0, 10.0, "nonexistent_strategy")


class TestConfig(unittest.TestCase):
    def test_config_simulation_defaults(self):
        sim = ConfigSimulation()
        self.assertEqual(sim.start, 0.0)
        self.assertEqual(sim.end, 10.0)
        self.assertEqual(sim.strategy, "edf")

    def test_config_task(self):
        t = ConfigTask(name="T1", execution_time=1.0, period=4.0, priority=1)
        self.assertEqual(t.name, "T1")
        self.assertEqual(t.period, 4.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
