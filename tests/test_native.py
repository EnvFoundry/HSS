"""Exercise compiled engines through the same preparation and study APIs as hosts."""

import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest
from hss.manager import Manager


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a):
        current = [i + 1]
        for j, right in enumerate(b):
            current.append(
                min(current[-1] + 1, previous[j + 1] + 1, previous[j] + (left != right))
            )
        previous = current
    return previous[-1]


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (os.environ.get("HSS_RUSTC") or shutil.which("rustc")):
            if os.environ.get("HSS_TEST_NATIVE"):
                raise RuntimeError("Native CI requires rustc")
            raise unittest.SkipTest("Native tests require Rust and a C++ compiler")
        cls.temporary = tempfile.TemporaryDirectory(prefix="hss-native-")
        cls.root = Path(cls.temporary.name)
        cls.manager = Manager(cls.root / "space")
        result = cls.manager.prepare(
            ["corpus-assembly", "text-collation"],
            backends={"corpus-assembly": "rust", "text-collation": "cpp"},
        )
        if result["failed"] or result["pending"]:
            cls.temporary.cleanup()
            raise RuntimeError(str(result))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_unicode_corpus_and_offsets(self):
        text = "研究 🙂 words words\n另一项研究\n"
        path = self.root / "中文 corpus.txt"
        path.write_text(text, encoding="utf-8", newline="")
        result = self.manager.run_study(
            {
                "tasks": [
                    {
                        "id": "profile",
                        "operation": "native_profile",
                        "paths": [str(path)],
                    },
                    {
                        "id": "find",
                        "operation": "native_concordance",
                        "paths": [str(path)],
                        "query": "研究",
                        "context": 3,
                    },
                ]
            },
            self.root / "corpus-results",
        )
        data = json.loads(Path(result["results"]).read_text(encoding="utf-8"))
        self.assertEqual(data["profile"]["characters"], len(text))
        self.assertEqual(data["profile"]["bytes"], len(text.encode("utf-8")))
        matches = data["find"]["tables"]["matches"]
        self.assertEqual(len(matches), 2)
        for row in matches:
            self.assertEqual(text[row["start"] : row["end"]], "研究")
            self.assertEqual(
                text.encode("utf-8")[row["byte_start"] : row["byte_end"]].decode(),
                "研究",
            )

    def test_alignment_matches_independent_dynamic_program(self):
        rng = random.Random(17)
        pairs = [
            ("", ""),
            ("", "甲🙂"),
            ("研究", ""),
            ("kitten", "sitting"),
            ("甲乙", "乙甲"),
        ]
        pairs += [
            (
                "".join(rng.choices("a甲🙂\n", k=rng.randrange(1, 30))),
                "".join(rng.choices("a甲🙂\n", k=rng.randrange(1, 30))),
            )
            for _ in range(35)
        ]
        left, right = self.root / "甲.txt", self.root / "乙.txt"
        for a, b in pairs:
            left.write_text(a, encoding="utf-8", newline="")
            right.write_text(b, encoding="utf-8", newline="")
            run = self.manager.execute("native-alignment", [str(left), str(right)])
            self.assertEqual(run["exit_code"], 0, run["stderr"])
            result = json.loads(run["stdout"])
            self.assertEqual(result["distance"], distance(a, b))
            self.assertEqual("".join(s["left"] for s in result["segments"]), a)
            self.assertEqual("".join(s["right"] for s in result["segments"]), b)
            for segment in result["segments"]:
                self.assertEqual(
                    segment["left"], a[segment["left_start"] : segment["left_end"]]
                )
                self.assertEqual(
                    segment["right"], b[segment["right_start"] : segment["right_end"]]
                )

    def test_prepared_native_components_are_reused(self):
        result = self.manager.plan(
            ["corpus-assembly", "text-collation"],
            backends={"corpus-assembly": "rust", "text-collation": "cpp"},
        )
        self.assertTrue(all(a["action"] == "reuse" for a in result["actions"]))
        self.assertEqual(
            set(
                self.manager.context(["corpus-assembly", "text-collation"])["bindings"]
            ),
            {"native-corpus", "native-alignment"},
        )


if __name__ == "__main__":
    unittest.main()
