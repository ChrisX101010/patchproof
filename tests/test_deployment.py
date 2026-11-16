from datetime import datetime, timedelta, timezone
import unittest

from patchproof.deployment import check_free_plan, deployment_policy


class DeploymentGateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        self.plan = {'accountId': '123456789012', 'accountPlanType': 'FREE', 'accountPlanStatus': 'ACTIVE',
                     'accountPlanExpirationDate': (self.now + timedelta(days=10)).isoformat(),
                     'accountPlanRemainingCredits': {'amount': 20, 'unit': 'USD'}}

    def test_free_plan_only(self):
        check_free_plan(self.plan, '123456789012', self.now)

    def test_metered_demo_requires_explicit_boolean_and_valid_identity(self):
        self.assertEqual(deployment_policy(None, '123456789012', temporary_metered=True), 'TEMPORARY_METERED_DEMO')
        for approval in (False, None, 'yes', 1):
            with self.subTest(approval=approval), self.assertRaises(ValueError):
                deployment_policy(None, '123456789012', temporary_metered=approval)
        with self.assertRaises(ValueError):
            deployment_policy(None, 'unknown', temporary_metered=True)

    def test_fail_closed_for_paid_unknown_expired_or_wrong_account(self):
        variants = [{'accountPlanType': 'PAID'}, {'accountPlanType': 'UNKNOWN'}, {'accountPlanStatus': 'EXPIRED'},
                    {'accountId': '999999999999'}, {'accountPlanExpirationDate': self.now.isoformat()},
                    {'accountPlanRemainingCredits': {'amount': 0, 'unit': 'USD'}},
                    {'accountPlanRemainingCredits': {'amount': 'NaN', 'unit': 'USD'}}]
        for change in variants:
            with self.subTest(change=change), self.assertRaises(ValueError):
                check_free_plan({**self.plan, **change}, '123456789012', self.now)
        with self.assertRaises(ValueError):
            check_free_plan({}, '123456789012', self.now)


if __name__ == '__main__':
    unittest.main()
