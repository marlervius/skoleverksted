import unittest

from Skoleverksted.backend.platform.models import YearPlanGenerateRequest
from Skoleverksted.backend.platform.year_planner import build_year_plan


class YearPlannerTests(unittest.TestCase):
    def test_fallback_plan_balances_weeks_and_lessons(self):
        request = YearPlanGenerateRequest(
            subject="Historie",
            level="VG2",
            school_year="2026-2027",
            lessons_per_week=2,
            teaching_weeks=38,
            number_of_periods=9,
            competency_goals=["utforske fortiden gjennom kilder"],
            use_ai=False,
        )
        plan = build_year_plan(request)

        self.assertEqual(plan.planning_source, "fallback")
        self.assertEqual(len(plan.periods), 9)
        self.assertEqual(sum(period.duration_weeks for period in plan.periods), 38)
        self.assertEqual(sum(period.lesson_count for period in plan.periods), 76)
        self.assertEqual(plan.periods[0].week_start, "2026-W34")
        self.assertTrue(all(period.learning_goals for period in plan.periods))

    def test_generic_subject_still_gets_requested_number_of_periods(self):
        request = YearPlanGenerateRequest(
            subject="Medieproduksjon",
            level="VG1",
            school_year="2026-2027",
            teaching_weeks=30,
            number_of_periods=6,
            use_ai=False,
        )
        plan = build_year_plan(request)
        self.assertEqual(len(plan.periods), 6)
        self.assertEqual(sum(period.duration_weeks for period in plan.periods), 30)


if __name__ == "__main__":
    unittest.main()
