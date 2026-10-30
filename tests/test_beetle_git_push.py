"""Offline failure injection for the exact durable state publication command."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from beetle_git_push import push_state


def response(code=0, stderr=""):
    return subprocess.CompletedProcess([], code, "", stderr)


class DurablePushTests(unittest.TestCase):
    def test_server_failure_retries_same_non_force_commit(self):
        run = mock.Mock(side_effect=[response(1, "remote: Internal Server Error"), response()])
        sleep = mock.Mock()
        self.assertEqual(push_state(Path("."), runner=run, sleeper=sleep),
                         {"status": "PUSH_CONFIRMED", "attempts": 2})
        self.assertEqual(run.call_args_list[0], run.call_args_list[1])
        args = run.call_args.args[0]
        self.assertEqual(args[-3:], ["push", "origin", "HEAD:beetle-state"])
        self.assertNotIn("--force", args)
        sleep.assert_called_once_with(2)

    def test_conflict_or_auth_failure_never_retries(self):
        for detail in ("[rejected] (fetch first)", "non-fast-forward", "permission denied",
                       "authentication failed", "protected branch", "unexpected failure",
                       "Internal Server Error: permission denied"):
            with self.subTest(detail=detail):
                run = mock.Mock(return_value=response(1, detail))
                sleep = mock.Mock()
                with self.assertRaisesRegex(RuntimeError, "BEETLE_DURABLE_PUSH_NOT_CONFIRMED"):
                    push_state(Path("."), runner=run, sleeper=sleep)
                self.assertEqual(run.call_count, 1)
                sleep.assert_not_called()

    def test_exhaustion_is_bounded_and_hides_remote_credentials(self):
        run = mock.Mock(return_value=response(1, "Internal Server Error secret-token-sentinel"))
        sleep = mock.Mock()
        with self.assertRaises(RuntimeError) as caught:
            push_state(Path("."), runner=run, sleeper=sleep)
        self.assertNotIn("secret-token-sentinel", str(caught.exception))
        self.assertEqual(run.call_count, 3)
        self.assertEqual(sleep.call_args_list, [mock.call(2), mock.call(4)])

    def test_uncertain_timeout_repeats_idempotent_push(self):
        run = mock.Mock(side_effect=[subprocess.TimeoutExpired("git", 90), response()])
        self.assertEqual(push_state(Path("."), runner=run, sleeper=lambda _: None)["attempts"], 2)

    def test_real_remote_has_exact_commit_after_retry_and_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, remote = root / "worker", root / "durable.git"
            def git(*args):
                return subprocess.run(["git", *map(str, args)], check=True,
                                      text=True, capture_output=True).stdout.strip()
            git("init", "--bare", remote)
            git("init", "-b", "beetle-state", repo)
            git("-C", repo, "config", "user.name", "Offline Test")
            git("-C", repo, "config", "user.email", "test@example.invalid")
            git("-C", repo, "remote", "add", "origin", remote)
            (repo / "receipt.json").write_text('{"verified":true}\n')
            git("-C", repo, "add", "receipt.json")
            git("-C", repo, "commit", "-m", "verified receipt")
            expected = git("-C", repo, "rev-parse", "HEAD")
            calls = []
            def inject(command, **kwargs):
                calls.append(command)
                return response(1, "remote: Internal Server Error") if len(calls) == 1 else subprocess.run(command, **kwargs)
            self.assertEqual(push_state(repo, runner=inject, sleeper=lambda _: None)["attempts"], 2)
            self.assertEqual(git("--git-dir", remote, "rev-parse", "refs/heads/beetle-state"), expected)
            self.assertEqual(push_state(repo)["attempts"], 1)
            self.assertEqual(git("--git-dir", remote, "rev-parse", "refs/heads/beetle-state"), expected)


if __name__ == "__main__":
    unittest.main()
