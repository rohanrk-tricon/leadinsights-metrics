import unittest

from app.agents.sql_policy import build_policy_feedback


class SQLPolicyTests(unittest.TestCase):
    def test_non_time_bound_lead_question_does_not_require_campaign_window(self):
        question = "Which campaign generated the most leads?"
        sql = """
        SELECT c.name, COUNT(*) AS lead_count
        FROM leadinsights.lead_txn_davc ltd
        JOIN leadinsights.lead_davc ld ON ld.id = ltd.lead_id
        JOIN leadinsights.campaign c ON c.id = ltd.campaign_id
        WHERE ld.email NOT ILIKE '%@triconinfotech.com'
          AND ld.email NOT ILIKE '%@test.com'
          AND ld.email NOT ILIKE '%@informa.com'
        GROUP BY c.name
        ORDER BY lead_count DESC
        LIMIT 5;
        """

        feedback = build_policy_feedback(question, sql)

        self.assertIsNone(feedback)

    def test_time_bound_lead_question_requires_campaign_window_columns(self):
        question = "How many leads were generated this month?"
        sql = """
        SELECT COUNT(*) AS lead_count
        FROM leadinsights.lead_txn_davc ltd
        JOIN leadinsights.lead_davc ld ON ld.id = ltd.lead_id
        JOIN leadinsights.campaign c ON c.id = ltd.campaign_id
        WHERE ld.email NOT ILIKE '%@triconinfotech.com'
          AND ld.email NOT ILIKE '%@test.com'
          AND ld.email NOT ILIKE '%@informa.com';
        """

        feedback = build_policy_feedback(question, sql)

        self.assertIsNotNone(feedback)
        self.assertIn("leadinsights.campaign.start_date", feedback)
        self.assertIn("leadinsights.campaign.end_date", feedback)


if __name__ == "__main__":
    unittest.main()
