import unittest

from plan import build_plan


def invoice(invoice_id="INV-1", days_overdue=3, **overrides):
    from datetime import date, timedelta

    due_date = date(2026, 10, 12) - timedelta(days=days_overdue)
    data = {
        "id": invoice_id,
        "customer": "Test Customer",
        "amount": 100.0,
        "currency": "EUR",
        "due_date": due_date.isoformat(),
        "paid_date": None,
    }
    data.update(overrides)
    return data


class PaymentReminderTests(unittest.TestCase):
    TODAY = "2026-10-12"

    def plan(self, invoices, sent=None):
        return build_plan(invoices, sent or [], self.TODAY)

    def test_empty_input(self):
        self.assertEqual(
            self.plan([]),
            {"today": self.TODAY, "actions": [], "skipped": []},
        )

    def test_friendly_starts_at_three_days(self):
        result = self.plan([invoice(days_overdue=3)])
        self.assertEqual(result["actions"][0]["step"], "friendly")
        self.assertFalse(result["actions"][0]["needs_approval"])

    def test_two_days_overdue_has_no_action(self):
        self.assertEqual(self.plan([invoice(days_overdue=2)])["actions"], [])

    def test_firm_starts_at_ten_days_and_needs_approval(self):
        action = self.plan([invoice(days_overdue=10)])["actions"][0]
        self.assertEqual(action["step"], "firm")
        self.assertTrue(action["needs_approval"])

    def test_final_starts_at_twenty_four_days(self):
        action = self.plan([invoice(days_overdue=24)])["actions"][0]
        self.assertEqual(action["step"], "final")
        self.assertTrue(action["needs_approval"])

    def test_paid_invoice_is_not_actioned(self):
        paid = invoice(paid_date="2026-10-10")
        self.assertEqual(self.plan([paid])["actions"], [])

    def test_sent_same_or_higher_step_blocks_action(self):
        data = invoice(days_overdue=10)
        sent = [{"invoice_id": "INV-1", "step": "firm"}]
        self.assertEqual(self.plan([data], sent)["actions"], [])

    def test_invalid_amount_is_skipped(self):
        data = invoice(amount=0)
        self.assertEqual(
            self.plan([data])["skipped"][0]["reason"], "invalid_amount"
        )

    def test_missing_due_date_is_skipped(self):
        data = invoice()
        data["due_date"] = ""
        self.assertEqual(
            self.plan([data])["skipped"][0]["reason"], "missing_due_date"
        )

    def test_duplicate_ids_are_skipped_once(self):
        result = self.plan([invoice(), invoice()])
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(result["skipped"][0]["reason"], "duplicate_id")
        self.assertEqual(result["actions"], [])

    def test_invalid_today_raises_error(self):
        with self.assertRaises(ValueError):
            build_plan([], [], "not-a-date")


if __name__ == "__main__":
    unittest.main()
