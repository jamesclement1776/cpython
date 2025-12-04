import json
import os
import subprocess
import sys
import textwrap
import unittest

from test.support import os_helper


class FirmamentEmitterTests(unittest.TestCase):
    def _run_instrumented_script(self, source: str):
        with os_helper.temp_dir() as tmpdir:
            script = os.path.join(tmpdir, "firmament_script.py")
            with open(script, "w", encoding="utf-8") as handle:
                handle.write(textwrap.dedent(source))

            env = os.environ.copy()
            env["FIRMAMENT2_ENABLE"] = "1"
            env["FIRMAMENT2_INCLUDE_CODE_META"] = "1"

            proc = subprocess.run(
                [sys.executable, "-I", "-S", script],
                text=True,
                capture_output=True,
                env=env,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)

        lines = []
        for line in proc.stdout.splitlines():
            if line.strip():
                lines.append(json.loads(line))
        return lines

    def test_emitters_produce_events(self):
        events = self._run_instrumented_script(
            """
            def add(a, b):
                return a + b

            add(1, 2)
            """
        )

        self.assertTrue(events, "expected firmament2 events to be emitted")

        event_types = {event.get("type") for event in events}
        self.assertIn("tokenizer", event_types)
        self.assertIn("ast", event_types)

        control_events = {
            event["payload"].get("event")
            for event in events
            if event.get("type") == "c" and "payload" in event
        }
        for expected in {
            "SOURCE_BEGIN",
            "SOURCE_END",
            "CODE_CREATE",
            "CODE_DESTROY",
            "FRAME_ENTER",
        }:
            self.assertIn(expected, control_events)


if __name__ == "__main__":
    unittest.main()
