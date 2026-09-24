"""Regression checks for container removal during resource sampling."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_docker_stats as collector


class CollectorTests(unittest.TestCase):
    def test_removed_runner_preserves_partial_samples_and_next_interval(self):
        sample = '{"Name":"benchmark-demucs-1","CPUPerc":"100%"}\n'
        removed = subprocess.CalledProcessError(
            1, ["docker", "stats"], output=sample,
            stderr="Error response from daemon: No such container: runner\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "stats.ndjson"
            with (
                patch("sys.argv", ["collector", "--project-name", "benchmark", "--output", str(output)]),
                patch.object(collector, "command_output", side_effect=["runner worker", removed, "worker", sample]) as command,
                patch.object(collector.time, "sleep", side_effect=[None, KeyboardInterrupt]),
                patch("sys.stderr"),
            ):
                collector.main()
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row["Name"] == "benchmark-demucs-1" and row["timestamp"] for row in rows))
            self.assertEqual(command.call_args_list[-1].args[0][-1], "worker")
            self.assertNotIn("runner", command.call_args_list[-1].args[0])

    def test_removed_container_without_partial_output(self):
        removed = subprocess.CalledProcessError(
            1, ["docker", "stats"], stderr="Error response from daemon: No such container: runner",
        )
        with patch.object(collector, "command_output", side_effect=["runner", removed]), patch("sys.stderr"):
            self.assertEqual(collector.collect_stats("benchmark"), "")

    def test_unrelated_docker_failure_is_not_hidden(self):
        error = subprocess.CalledProcessError(
            1, ["docker", "stats"], stderr="Cannot connect to the Docker daemon",
        )
        with patch.object(collector, "command_output", side_effect=["worker", error]):
            with self.assertRaises(subprocess.CalledProcessError):
                collector.collect_stats("benchmark")

    def test_empty_project_does_not_sample_other_containers(self):
        with patch.object(collector, "command_output", return_value="") as command:
            self.assertEqual(collector.collect_stats("benchmark"), "")
            self.assertEqual(command.call_count, 1)


if __name__ == "__main__":
    unittest.main()
