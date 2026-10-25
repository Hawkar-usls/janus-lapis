"""Protein-stability candidate relevance gate: independent synthetic fixtures."""
import importlib.util
from pathlib import Path
import sys
import unittest

TOOLS=Path(__file__).resolve().parents[1]/"tools"
sys.path.insert(0,str(TOOLS))
spec=importlib.util.spec_from_file_location("universal_beetle",TOOLS/"universal_beetle.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ROWAN={"id":"protein_stability_falsifiers::FORWARD",
       "base_direction_id":"protein_stability_falsifiers"}
ROWAN_REVERSE={"id":"protein_stability_falsifiers::REVERSE",
       "base_direction_id":"protein_stability_falsifiers"}
OTHER={"id":"large_data_methods::CONTROL","base_direction_id":"large_data_methods"}

class Relevance(unittest.TestCase):
    def test_accept_protein_mutation_stability(self):
        self.assertTrue(m.rowan_domain_scope(ROWAN,{"title":"Protein stability of mutations",
          "summary":"Benchmarks of thermodynamic stability of single point mutants"}))
    def test_accept_primary_assay_bbc1(self):
        self.assertTrue(m.rowan_domain_scope(ROWAN,{"title":"BBC1 proteolysis assay data",
          "summary":"Raw proteolysis measurements and controls"}))
    def test_accept_external_ddg_negative_controls(self):
        self.assertTrue(m.rowan_domain_scope(ROWAN_REVERSE,{"title":"Mutation DeltaDeltaG negative controls",
          "summary":"Protein fold thermodynamic stability ΔΔG measurements"}))
    def test_reject_computer_vision_keyword_coincidence(self):
        self.assertFalse(m.rowan_domain_scope(ROWAN,{"title":"HBB2OBB rotation box benchmark",
          "summary":"High confidence score and independent validation reproducibility"}))
    def test_reject_quantum_sensing_biolab_noise(self):
        self.assertFalse(m.rowan_domain_scope(ROWAN_REVERSE,{"title":"Quantum biolaboratory",
          "summary":"Independent research protocol, source stability and negative control"}))
    def test_reject_generic_protein_prediction_without_mutation(self):
        self.assertFalse(m.rowan_domain_scope(ROWAN,{"title":"Protein folding",
          "summary":"High confidence 3D structures and shape prediction"}))
    def test_unrelated_research_scopes_untouched(self):
        self.assertTrue(m.rowan_domain_scope(OTHER,{"title":"Cloud Atlas",
          "summary":"Astronomy and satellites"}))
    def test_no_mutation_keyword_false_positive(self):
        self.assertFalse(m.rowan_domain_scope(ROWAN,{"title":"Recovered quantum sensor",
          "summary":"Protein sequence indexing without experimentally measured effects"}))
    def test_original_direction_id_also_matched(self):
        d={"id":"protein_stability_falsifiers"}
        self.assertFalse(m.rowan_domain_scope(d,{"title":"Reproducibility of network packets",
          "summary":"Evidence proofs and inversion"}))

if __name__=="__main__":unittest.main()
