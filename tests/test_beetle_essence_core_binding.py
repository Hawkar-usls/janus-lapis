"""Fail-closed Universal Beetle proof of ESSENCE multi-core research lanes."""
import copy
import importlib.util
from pathlib import Path
import unittest
from tools import beetle_essence_core_binding as b

p=Path(__file__).resolve().parents[1]/"tools"/"beetle_director_overlay.py"
spec=importlib.util.spec_from_file_location("beetle_director_overlay",p)
overlay=importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)


def fixture():
    questions=[
        {"id":"essence_independent_core_tests",
         "title":"Independent tests of inherited JANUS microkernels",
         "keywords":["modular neural evolution","independent benchmark"],
         "target_repositories":["Hawkar-usls/Janus_Genesis","Hawkar-usls/Demi_Head"],
         "priority":82},
        {"id":"essence_prospective_weight_gain",
         "title":"Prospective neural model generalization controls",
         "keywords":["prospective validation","grouped cross validation"],
         "target_repositories":["Hawkar-usls/janus-meta-registry","Hawkar-usls/Janus_Genesis"],
         "priority":78}
    ]
    sources=[{
      "role":role,"repository":repo,"ref":ref,"path":path,
      "commit_sha":"a"*40,"git_blob_sha1":"b"*40,"json_sha256":"c"*64,
      "scientific_evidence":False,"production_authority":False
    } for role,(repo,ref,path) in b.ROLES.items()]
    core={
        "schema":"janus.essence.beetle_core_bridge/2.9",
        "status":"CORE_LINKED_SEARCH_STEERING_ONLY",
        "source_count":6,"sources":sources,"search_questions":questions,
        "science_claim":"RESEARCH_STEERING_NOT_INDEPENDENT_EVIDENCE",
        "authority_delta":0,"automatic_production_promotion":False,
        "producer_can_modify_model_weights":False,
        "producer_can_write_other_repositories":False}
    core["receipt_sha256"]=b.sha(core)
    live={
        "essence_core_bridge_ingested":True,
        "essence_core_bridge_receipt_sha256":core["receipt_sha256"],
        "core_bridge_scientific_authority":False,
        "ad_hoc_directions":[
            {"id":"demiurge_"+q["id"],"source":"ESSENCE_CORE_BRIDGE",
             **{k:v for k,v in q.items() if k!="id"}}
            for q in questions]}
    return live,core

class CoreBeetleBinding(unittest.TestCase):
    def test_two_verified_research_lanes_survive_and_have_all_mirrors(self):
        live,core=fixture()
        accepted,ok=b.filter_core_topics(live,core)
        self.assertTrue(ok)
        self.assertEqual(len(accepted["ad_hoc_directions"]),2)
        self.assertTrue(b.valid_catalog(core,live))
        d=overlay.adhoc_to_direction(accepted["ad_hoc_directions"][0])
        self.assertEqual(d["mirror_lenses"],
                         ["FORWARD","REVERSE","COUNTEREVIDENCE","CONTROL"])
        self.assertEqual({s["kind"] for s in d["sources"]},
                         {"arxiv","zenodo","github"})

    def test_missing_remote_catalog_drops_only_core(self):
        live,core=fixture()
        normal={"id":"safe_independent_topic","source":"JANUS_DESIRES",
                "keywords":["control"],"target_repositories":["Hawkar-usls/Janus_Genesis"]}
        live["ad_hoc_directions"].append(normal)
        accepted,ok=b.filter_core_topics(live,{})
        self.assertFalse(ok)
        self.assertEqual(accepted["ad_hoc_directions"],[normal])

    def test_sha_mismatch_cannot_enter_beetle(self):
        live,core=fixture()
        live["essence_core_bridge_receipt_sha256"]="f"*64
        self.assertFalse(b.filter_core_topics(live,core)[1])

    def test_modified_core_query_rejected_even_if_rehashed(self):
        live,core=fixture()
        core["search_questions"][0]["keywords"]=["inject arbitrary target"]
        core["receipt_sha256"]=b.sha({k:v for k,v in core.items()
                                        if k!="receipt_sha256"})
        live["essence_core_bridge_receipt_sha256"]=core["receipt_sha256"]
        self.assertFalse(b.filter_core_topics(live,core)[1])

    def test_modified_live_query_rejected(self):
        live,core=fixture()
        live["ad_hoc_directions"][0]["keywords"].append("unsafe arbitrary task")
        self.assertFalse(b.filter_core_topics(live,core)[1])

    def test_no_scientific_or_production_authority_escalation(self):
        live,core=fixture()
        for field,value in [
          ("science_claim","PROOF"),
          ("authority_delta",1),
          ("automatic_production_promotion",True),
          ("producer_can_modify_model_weights",True),
          ("producer_can_write_other_repositories",True)]:
            c=copy.deepcopy(core)
            c[field]=value
            c["receipt_sha256"]=b.sha({k:v for k,v in c.items()
                                        if k!="receipt_sha256"})
            L=copy.deepcopy(live)
            L["essence_core_bridge_receipt_sha256"]=c["receipt_sha256"]
            self.assertFalse(b.filter_core_topics(L,c)[1],field)

    def test_changed_source_role_is_rejected_even_with_valid_digest(self):
        live,core=fixture()
        core["sources"][0]["path"]="evil/outside/allowlist"
        core["receipt_sha256"]=b.sha({k:v for k,v in core.items()
                                      if k!="receipt_sha256"})
        live["essence_core_bridge_receipt_sha256"]=core["receipt_sha256"]
        self.assertFalse(b.filter_core_topics(live,core)[1])


if __name__=="__main__":
    unittest.main()
