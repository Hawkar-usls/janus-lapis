"""Source-locked Demiurge-to-Beetle search-steering tests: no internet and no Rowan."""
import copy
import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).resolve().parents[1]/"tools"/"beetle_director_overlay.py"
spec=importlib.util.spec_from_file_location("beetle_director_overlay",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def samples(completed=0):
    meta={"schema_id":"janus.rowan.observer_state.v1",
          "latest_durable_external_run":40147900977,
          "last_completed_mutants":completed,
          "underlying_state_is_derived_from":"a"*64}
    council={"schema_id":"janus.demiurge.rowan_council_proposal.v1",
             "sources":{"meta_registry":{"canonical_run":40147900977,
                "sha256":m.rowan_digest(meta),"source_artifact_sha256":"a"*64}},
             "next_beetle_direction_id":"protein_stability_falsifiers",
             "next_aura_question_id":"RAW_ASSAY_LINEAGE" if completed<8 else "EXTERNAL_HOLDOUT",
             "completed_pilot_cases":completed,
             "gates":{k:False for k in (
                 "rowan_credit_spend_new","rowan_job_submission_new",
                 "beetle_candidates_empirical_evidence",
                 "aura_predictions_empirical_evidence",
                 "production_model_weight_promotion")},
             "scientific_authority":"NONE__PROPOSAL_NOT_EXPERIMENT"}
    council["content_sha256"]=m.rowan_digest(council)
    direction={"id":"protein_stability_falsifiers",
               "keywords":["BBC1"],"target_repositories":["Hawkar-usls/janus-meta-registry"],
               "sources":[{"kind":"arxiv","query":"base arxiv","max_results":8},
                          {"kind":"zenodo","query":"base zenodo","max_results":6},
                          {"kind":"github","query":"base github","max_results":6}]}
    return meta,council,direction

def rehash(c):
    c["content_sha256"]=m.rowan_digest({k:v for k,v in c.items() if k!="content_sha256"})

class Tests(unittest.TestCase):
    def test_pre_frozen_data_selects_raw_assay(self):
        a,b,d=samples()
        self.assertEqual(m.verify_rowan_focus(a,b),"RAW_ASSAY_LINEAGE")
        focused=m.focus_rowan_direction(d,"RAW_ASSAY_LINEAGE")
        self.assertIn("Tsuboyama",focused["sources"][0]["query"])
        self.assertEqual(d["sources"][0]["query"],"base arxiv")
        self.assertFalse(focused["source_bound_research_question_is_evidence"])
    def test_complete_eight_switches_external_holdout(self):
        a,b,d=samples(8)
        self.assertEqual(m.verify_rowan_focus(a,b),"EXTERNAL_HOLDOUT")
        self.assertIn("independent",m.focus_rowan_direction(d,"EXTERNAL_HOLDOUT")["sources"][0]["query"])
    def test_stale_meta_reverts_to_base(self):
        a,b,d=samples()
        a["last_completed_mutants"]=1
        self.assertIsNone(m.verify_rowan_focus(a,b))
        self.assertEqual(m.focus_rowan_direction(d,None),d)
    def test_integrity_digest_tamper_rejected(self):
        a,b,_=samples()
        b["next_aura_question_id"]="EXTERNAL_HOLDOUT"
        self.assertIsNone(m.verify_rowan_focus(a,b))
    def test_credit_authority_escalation_rejected_even_rehash(self):
        a,b,_=samples()
        b["gates"]["rowan_credit_spend_new"]=True
        rehash(b)
        self.assertIsNone(m.verify_rowan_focus(a,b))
    def test_unauthorized_oracle_question_rejected_even_rehash(self):
        a,b,_=samples()
        b["next_aura_question_id"]="https://evil.example/steal-token"
        rehash(b)
        self.assertIsNone(m.verify_rowan_focus(a,b))
    def test_incomplete_count_cannot_force_external_holdout(self):
        a,b,_=samples(3)
        b["next_aura_question_id"]="EXTERNAL_HOLDOUT"
        rehash(b)
        self.assertIsNone(m.verify_rowan_focus(a,b))
    def test_non_rowan_lane_unchanged(self):
        _,_,d=samples()
        d["id"]="kusto_ocean_data"
        self.assertEqual(m.focus_rowan_direction(d,"RAW_ASSAY_LINEAGE"),d)
    def test_no_source_urls_from_untrusted_payload(self):
        _,_,d=samples()
        d0=copy.deepcopy(d)
        d["sources"][0]["query"]="malicious nonsense"
        focused=m.focus_rowan_direction(d,"RAW_ASSAY_LINEAGE")
        self.assertNotIn("malicious",focused["sources"][0]["query"])
        self.assertEqual(d0["sources"][1]["max_results"],focused["sources"][1]["max_results"])
    def test_independent_evidence_not_assigned(self):
        a,b,_=samples()
        b["gates"]["beetle_candidates_empirical_evidence"]=True
        rehash(b)
        self.assertIsNone(m.verify_rowan_focus(a,b))

if __name__=="__main__":unittest.main()
