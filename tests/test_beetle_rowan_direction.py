import json
from pathlib import Path
import unittest

CONFIG=Path(__file__).resolve().parents[1]/"data"/"beetle"/"directions.json"
class BeetleRowanLaneTests(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads(CONFIG.read_text(encoding="utf-8"))
        self.lanes=[d for d in self.cfg["directions"] if d["id"]=="protein_stability_falsifiers"]
    def test_one_enabled_lane(self):
        self.assertEqual(len(self.lanes),1)
        self.assertTrue(self.lanes[0]["enabled"])
    def test_existing_four_lenses_mandatory(self):
        self.assertEqual(set(self.lanes[0]["mirror_lenses"]),set(self.cfg["default_mirror_lenses"]))
        self.assertEqual(set(self.lanes[0]["mirror_lenses"]),{"FORWARD","REVERSE","COUNTEREVIDENCE","CONTROL"})
    def test_only_current_approved_receiver_repos(self):
        self.assertEqual(set(self.lanes[0]["target_repositories"]),
            {"Hawkar-usls/janus-meta-registry","Hawkar-usls/aura-oracle-tg"})
    def test_bounded_discovery_no_grazer_approval(self):
        self.assertTrue(all(x.get("enabled") and 1<=x.get("max_results",0)<=10
            for x in self.lanes[0]["sources"]))
        self.assertFalse(any(task.get("direction_id")=="protein_stability_falsifiers"
            for task in self.cfg.get("grazer_tasks",[])))
    def test_candidates_never_empirical_authority(self):
        self.assertIn("BEETLE_DISCOVERY_ONLY",self.lanes[0]["epistemic_firewall"])
        self.assertIn("TOPA_INDEPENDENT_VALIDATION_REQUIRED",self.lanes[0]["epistemic_firewall"])
        self.assertIn("ROWAN_SPEND_AUTHORITY_ZERO",self.lanes[0]["epistemic_firewall"])
    def test_no_removed_old_directions(self):
        self.assertGreaterEqual(len(self.cfg["directions"]),18)
        self.assertEqual(len({d["id"] for d in self.cfg["directions"]}),len(self.cfg["directions"]))
    def test_global_budgets_unchanged(self):
        b=self.cfg["global_budget"]
        self.assertLessEqual(b["max_requests_per_run"],72)
        self.assertLessEqual(b["max_metadata_bytes_per_run"],15_000_000)

if __name__=="__main__":unittest.main()
