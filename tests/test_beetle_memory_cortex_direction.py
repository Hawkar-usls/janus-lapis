import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import beetle_director_overlay as director


class CortexDirectionTests(unittest.TestCase):
    def test_current_director_really_schedules_cortex_without_more_lane_budget(self):
        base = Path(__file__).resolve().parents[1] / 'data/beetle/directions.json'
        static = {'scheduling': {'max_primary_directions_per_hour': 10,
                                'max_mirror_lanes_per_hour': 16,
                                'reserve_one_fairness_slot': True}}
        live = {'direction_priorities': {
            'cognition_memory_reverse': 100, 'mirror_bidirectional_provenance': 100,
            'registry_provenance': 100, 'swarm_distributed_systems': 100,
            'formal_proof_verification': 97}}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'effective.json'
            argv = ['director', '--base', str(base), '--static-url', 'https://fixture/static',
                    '--live-url', 'https://fixture/live', '--state-dir', tmp, '--out', str(out),
                    '--max-primary', '10', '--max-lanes', '16']
            with patch('sys.argv', argv), patch.object(director, 'load_remote', side_effect=[static, live]), \
                    contextlib.redirect_stdout(io.StringIO()):
                director.main()
            result = json.loads(out.read_text())
            self.assertIn('memory_cortex_incremental_sources', result['effective_meta']['selected_base_directions'])
            lanes = [x for x in result['directions'] if x.get('base_direction_id') == 'memory_cortex_incremental_sources']
            if not lanes:
                lanes = [x for x in result['directions'] if x['id'].startswith('memory_cortex_incremental_sources')]
            self.assertTrue(lanes, 'Cortex must be in actual lanes, not only selected primaries')
            self.assertLessEqual(len(result['directions']), 16)
            self.assertEqual({d['mirror_lens'] for d in result['directions']},
                             {'FORWARD', 'REVERSE', 'COUNTEREVIDENCE', 'CONTROL'})
            self.assertTrue(all(s['kind'] in {'arxiv', 'zenodo'} for d in lanes for s in d['sources']))


if __name__ == '__main__':
    unittest.main()
