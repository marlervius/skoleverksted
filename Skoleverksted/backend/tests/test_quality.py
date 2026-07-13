import unittest

from Skoleverksted.backend.platform.models import QualityPassportRequest
from Skoleverksted.backend.platform.quality import build_quality_passport


class QualityPassportTests(unittest.TestCase):
    def test_exposes_source_and_math_limitations(self):
        passport = build_quality_passport(QualityPassportRequest(
            module="matematikk",
            title="Prosent",
            content=("Oppgaven bruker en norsk lønnstabell og forklarer beregningen. [K] " * 20),
            sources=["SSB tabell 123"],
            competency_goals=["M1"],
            has_answer_key=True,
            compiled=True,
            math_incorrect=0,
            math_unparseable=1,
            prompt_version="math-v2",
        ))

        self.assertEqual(passport.overall_status, "needs_review")
        self.assertTrue(any("manuell kontroll" in text for text in passport.limitations))
        self.assertEqual(next(check for check in passport.checks if check.code == "math_correctness").status, "warning")


    def test_blocks_known_placeholders_and_math_errors(self):
        passport = build_quality_passport(QualityPassportRequest(
            module="fag",
            title="Uferdig ark",
            content=("Dette er faglig innhold som ennå ikke er ferdigstilt. " * 20) + " TODO",
            math_incorrect=2,
        ))
        self.assertEqual(passport.overall_status, "failed")
        self.assertEqual(next(check for check in passport.checks if check.code == "placeholders").status, "failed")


if __name__ == "__main__":
    unittest.main()
