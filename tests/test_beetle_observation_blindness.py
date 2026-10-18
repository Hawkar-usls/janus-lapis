"""Adversarial tests for sustained UNKNOWN with durable GitHub artifacts."""
from __future__ import annotations

import copy
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from beetle_observation_blindness import (BLIND_MARKER, BLIND_TITLE,
                                          prior_status, synchronize, unknown_streak)
from beetle_incident_issues import INCIDENT_ASSIGNEE, MARKER


CURRENT = dt.datetime(2026, 10, 18, 12, 0, tzinfo=dt.timezone.utc)
CURRENT_RUN = 200


def report(status='UNKNOWN'):
    return {'schema': 'janus.beetle_home_watchdog.v1', 'status': status,
            'alerts': [], 'scientific_authority_delta': 0}


class FakeAPI:
    def __init__(self, history=None):
        self.issues = []
        self.calls = []
        self.history = history or ['UNKNOWN']
        self.artifact_overrides = {}

    def list_all(self):
        return copy.deepcopy(self.issues)

    def request(self, method, path, payload=None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if method == 'GET' and '/actions/runs?' in path:
            history = []
            for index, _ in enumerate(self.history):
                when = CURRENT - dt.timedelta(hours=index)
                history.append({'id': CURRENT_RUN - index,
                                'created_at': when.isoformat().replace('+00:00', 'Z'),
                                'path': '.github/workflows/janus-beetle-home-watchdog.yml',
                                'head_branch': 'main', 'event': 'schedule',
                                'status': 'in_progress' if index == 0 else 'completed'})
            return {'workflow_runs': history}
        if method == 'GET' and '/actions/runs/' in path and '/artifacts?' in path:
            run_id = int(path.split('/actions/runs/')[1].split('/')[0])
            if run_id in self.artifact_overrides:
                return {'artifacts': copy.deepcopy(self.artifact_overrides[run_id])}
            index = CURRENT_RUN - run_id
            if index < 0 or index >= len(self.history):
                raise AssertionError(f'unexpected run id {run_id}')
            status = self.history[index]
            if status is None:
                return {'artifacts': [{'name': 'janus-watchdog-receipt-' + str(run_id)}]}
            return {'artifacts': [{
                'name': f'janus-watchdog-{status}-{run_id}', 'expired': False,
                'workflow_run': {'id': run_id, 'head_branch': 'main'}}]}
        if method == 'POST':
            created = {'number': 44, 'state': 'open', 'title': payload['title'],
                       'body': payload['body'],
                       'assignees': [{'login': n} for n in payload['assignees']]}
            self.issues.append(created)
            return copy.deepcopy(created)
        if method == 'PATCH':
            number = int(path.rsplit('/', 1)[1])
            issue = next(issue for issue in self.issues if issue['number'] == number)
            issue.update(payload)
            return copy.deepcopy(issue)
        raise AssertionError(f'unexpected API request {method} {path}')

    def mutations(self):
        return [call for call in self.calls if call[0] != 'GET']


class BlindnessTests(unittest.TestCase):
    def test_one_or_three_hourly_unknowns_are_not_alerted(self):
        for total in (1, 2, 3):
            with self.subTest(total=total):
                api = FakeAPI(['UNKNOWN'] * total)
                result = synchronize(report(), CURRENT_RUN, api)
                self.assertEqual(result['action'], 'UNKNOWN_GRACE_NO_WRITE')
                self.assertFalse(api.mutations())

    def test_four_hourly_unknowns_create_separate_assigned_issue(self):
        api = FakeAPI(['UNKNOWN'] * 4)
        api.issues.append({'number': 21, 'state': 'open', 'body': MARKER + 'delivery',
                           'assignees': []})
        streak = unknown_streak(api, CURRENT_RUN)
        self.assertEqual(streak['count'], 4)
        self.assertEqual(streak['minutes'], 180)
        self.assertTrue(streak['escalate'])
        result = synchronize(report(), CURRENT_RUN, api)
        self.assertEqual(result['action'], 'CREATE_OBSERVABILITY_LOSS')
        self.assertEqual(api.issues[1]['title'], BLIND_TITLE)
        self.assertIn(BLIND_MARKER, api.issues[1]['body'])
        self.assertIn('does not mean any delivery SLO failed', api.issues[1]['body'])
        self.assertEqual(api.issues[1]['assignees'], [{'login': INCIDENT_ASSIGNEE}])
        self.assertEqual(api.issues[0]['state'], 'open')

    def test_identical_unknown_repeat_is_no_write(self):
        api = FakeAPI(['UNKNOWN'] * 4)
        synchronize(report(), CURRENT_RUN, api)
        before = len(api.mutations())
        self.assertEqual(synchronize(report(), CURRENT_RUN, api)['action'],
                         'REPEAT_BLINDNESS_NO_WRITE')
        self.assertEqual(len(api.mutations()), before)

    def test_observation_return_pass_warn_or_alert_closes_blindness(self):
        for status in ('PASS', 'WARN', 'ALERT'):
            with self.subTest(status=status):
                api = FakeAPI(['UNKNOWN'] * 4)
                synchronize(report(), CURRENT_RUN, api)
                api.issues[0]['body'] += '\n## Maintainer notes\nKeep me!\n'
                closed = synchronize(report(status), CURRENT_RUN + 1, api)
                self.assertEqual(closed['action'], 'CLOSE_OBSERVABILITY_RESTORED')
                self.assertEqual(api.issues[0]['state'], 'closed')
                self.assertIn('Keep me!', api.issues[0]['body'])
                self.assertIn('not proof of delivery', api.issues[0]['body'])

    def test_after_recovery_recurrence_reopens_same_issue(self):
        api = FakeAPI(['UNKNOWN'] * 4)
        synchronize(report(), CURRENT_RUN, api)
        synchronize(report('PASS'), CURRENT_RUN + 1, api)
        self.assertEqual(synchronize(report(), CURRENT_RUN, api)['action'],
                         'REOPEN_OBSERVABILITY_LOSS')
        self.assertEqual(api.issues[0]['state'], 'open')
        self.assertEqual(len(api.issues), 1)

    def test_known_sample_or_missing_artifact_breaks_streak(self):
        for separator in ('PASS', 'WARN', 'ALERT', None):
            with self.subTest(separator=separator):
                api = FakeAPI(['UNKNOWN', 'UNKNOWN', separator, 'UNKNOWN', 'UNKNOWN'])
                streak = unknown_streak(api, CURRENT_RUN)
                self.assertEqual(streak['count'], 2)
                self.assertFalse(streak['escalate'])
                self.assertEqual(synchronize(report(), CURRENT_RUN, api)['action'],
                                 'UNKNOWN_GRACE_NO_WRITE')

    def test_corrupt_artifact_or_duplicate_blind_issue_fails_closed(self):
        api = FakeAPI(['UNKNOWN'] * 4)
        api.artifact_overrides[199] = [{
            'name': 'janus-watchdog-UNKNOWN-199', 'expired': False,
            'workflow_run': {'id': 777, 'head_branch': 'main'}}]
        with self.assertRaisesRegex(ValueError, 'provenance'):
            unknown_streak(api, CURRENT_RUN)
        self.assertFalse(api.mutations())
        api.artifact_overrides.clear()
        synchronize(report(), CURRENT_RUN, api)
        api.issues.append({'number': 45, 'state': 'closed', 'body': BLIND_MARKER})
        with self.assertRaisesRegex(ValueError, 'multiple observation'):
            synchronize(report('PASS'), CURRENT_RUN, api)
        self.assertEqual(len(api.mutations()), 1)

    def test_current_run_not_in_history_does_not_invent_evidence(self):
        api = FakeAPI(['UNKNOWN'] * 4)
        with self.assertRaisesRegex(ValueError, 'current trusted main run'):
            unknown_streak(api, 999)

    def test_human_unassignment_not_overridden_on_recurrence(self):
        api = FakeAPI(['UNKNOWN'] * 4)
        synchronize(report(), CURRENT_RUN, api)
        api.issues[0]['assignees'] = []
        synchronize(report('PASS'), CURRENT_RUN + 1, api)
        synchronize(report(), CURRENT_RUN, api)
        self.assertEqual(api.issues[0]['assignees'], [])
        self.assertNotIn('assignees', api.mutations()[-1][2])

    def test_prior_status_accepts_only_unique_provenanced_artifact(self):
        api = FakeAPI(['UNKNOWN'] * 4)
        self.assertEqual(prior_status(api, 199), 'UNKNOWN')
        api.artifact_overrides[199] = [
            {'name': 'janus-watchdog-UNKNOWN-199', 'expired': False,
             'workflow_run': {'id': 199, 'head_branch': 'main'}},
            {'name': 'janus-watchdog-PASS-199', 'expired': False,
             'workflow_run': {'id': 199, 'head_branch': 'main'}}]
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            prior_status(api, 199)

    def test_expired_artifact_cannot_prove_a_continuous_unknown_streak(self):
        api = FakeAPI(['UNKNOWN'] * 4)
        api.artifact_overrides[198] = [{
            'name': 'janus-watchdog-UNKNOWN-198', 'expired': True,
            'workflow_run': {'id': 198, 'head_branch': 'main'}}]
        self.assertIsNone(prior_status(api, 198))
        self.assertEqual(unknown_streak(api, CURRENT_RUN)['count'], 2)
        self.assertFalse(api.mutations())

    def test_179_minutes_59_seconds_never_rounds_up_to_escalation(self):
        class JustBelowThreshold(FakeAPI):
            def request(self, method, path, payload=None):
                result = super().request(method, path, payload)
                if method == 'GET' and '/actions/runs?' in path:
                    result['workflow_runs'][-1]['created_at'] = (
                        CURRENT - dt.timedelta(minutes=179, seconds=59)
                    ).isoformat().replace('+00:00', 'Z')
                return result

        api = JustBelowThreshold(['UNKNOWN'] * 4)
        self.assertFalse(unknown_streak(api, CURRENT_RUN)['escalate'])
        self.assertFalse(api.mutations())


if __name__ == '__main__':
    unittest.main()
