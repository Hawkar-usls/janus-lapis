import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import rowan_fundamentum_translate as m


def pka():
    return {"schema_id":m.RESEARCH,"case_id":"SYNTHETIC-CASE-1","input_sha256":"a"*64,
            "provider":{"name":"Rowan","workflow_type":"pka","method":"starling"},
            "workflow_uuid":"abcdef01-1234-1234-1234-abcdef012345",
            "event":"ROWAN_RESULT_COLLECTED_UNVERIFIED",
            "result":{"kind":"MODEL_PREDICTION_NOT_EXPERIMENT",
                      "strongest_acid_pka":10.17,"strongest_base_pka":None}}


def bbc1():
    return {"schema_id":m.BBC1,"source_commit":"b"*40,"source_sha256":"c"*64,
            "wildtype":{"state":"PROVIDER_RESULT_RETURNED","ptm":0.8,"avg_lddt":0.9},
            "pilot_cases":[{"mutation":z,"provider_state":"PROVIDER_RESULT_RETURNED",
                            "ptm":0.60+i/100,"avg_lddt":0.70}
                           for i,z in enumerate(
                            ["G48D","G53A","W38L","K13N","G64Q","Q44V","E42H","T8A"])],
            "all_eight_ready_for_descriptive_association":True,
            "signed_label_direction_verified_against_original_raw_assay":False,
            "protein_stability_or_fitness_inferred":False,
            "topa_scientific_review":"OPEN"}


class Cases(unittest.TestCase):
    def test_pka_projection_only(self):
        candidate,ir,brief,manifest=m.transform(pka())
        self.assertEqual(candidate["facts"]["values"]["strongest_acid_pka"],10.17)
        self.assertEqual(candidate["for_fundamentum"]["P_VS_NP"],"OPEN")
        self.assertFalse(candidate["for_fundamentum"]["proof_or_exact_sat_witness"])
        self.assertTrue(all(x["operator"]=="ANNOTATE" for x in ir["algorithm"]["steps"]))
        self.assertEqual(manifest["rowan_api_calls"],0)
        self.assertIn("Не является SAT",brief)

    def test_deterministic_and_english(self):
        self.assertEqual(m.transform(pka(),"en"),m.transform(copy.deepcopy(pka()),"en"))
        self.assertIn("Not a SAT solution",m.transform(pka(),"en")[2])

    def test_bbc1_requires_eight_consistent(self):
        result=m.transform(bbc1())[0]
        self.assertEqual(result["facts"]["ready_count"],8)
        for change in [
            lambda x:x["pilot_cases"].pop(),
            lambda x:x["pilot_cases"][1].update(mutation="G48D"),
            lambda x:x["pilot_cases"][0].update(ptm=2),
            lambda x:x.update(all_eight_ready_for_descriptive_association=False),
            lambda x:x.update(protein_stability_or_fitness_inferred=True),
            lambda x:x.update(topa_scientific_review="APPROVED")]:
            case=bbc1();change(case)
            with self.assertRaises(m.TranslationBlocked):m.transform(case)

    def test_invalid_or_premature_pka(self):
        for change in [
            lambda x:x.update(event="INVALID"),
            lambda x:x["provider"].update(workflow_type="unknown"),
            lambda x:x.update(workflow_uuid=None),
            lambda x:x["result"].update(kind="INVALID"),
            lambda x:x["result"].update(strongest_acid_pka=float("inf")),
            lambda x:x.update(input_sha256="invalid"),
            lambda x:x.update(event="ROWAN_RESULT_PENDING")]:
            item=pka();change(item)
            with self.assertRaises((m.TranslationBlocked,ValueError)):m.transform(item)
        pending=pka();pending["event"]="ROWAN_RESULT_PENDING";pending["result"]=None
        self.assertEqual(m.transform(pending)[0]["facts"]["data_status"],"NO_RESULT")

    def test_unsupported_schema(self):
        with self.assertRaises(m.TranslationBlocked):
            m.transform({"schema_id":"janus.unrelated.v1"})

    def test_write_once_cache_and_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/"source.json";out=root/"output"
            source.write_text(json.dumps(pka()),encoding="utf-8")
            self.assertEqual(m.translate_file(source,out),"TRANSLATED_NEW")
            self.assertEqual(m.translate_file(source,out),"CACHE_HIT_SAME_CONTENT")
            folder=next(out.iterdir())
            (folder/"brief.txt").write_text("tampered",encoding="utf-8")
            with self.assertRaises(m.TranslationBlocked):m.translate_file(source,out)

    def test_input_size(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"oversize";p.write_bytes(b"x"*(m.MAX_INPUT_BYTES+1))
            with self.assertRaises(m.TranslationBlocked):
                m.translate_file(p,Path(td)/"outputs")


if __name__=="__main__":
    unittest.main()
