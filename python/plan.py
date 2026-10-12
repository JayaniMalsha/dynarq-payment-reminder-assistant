
"""Payment reminder rules engine."""

import argparse
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

STEPS = ("friendly", "firm", "final")
THRESHOLDS = {"friendly": 3, "firm": 10, "final": 24}

SKIP_MESSAGES = {
    "duplicate_id": "Duplicate invoice ID",
    "invalid_amount": "Amount is missing, invalid, or not positive",
    "missing_due_date": "Due date is missing",
    "invalid_due_date": "Due date is not a valid YYYY-MM-DD date",
    "invalid_paid_date": "Paid date is invalid or after today",
}


def parse_date(value):
    """Parse a real date in exactly YYYY-MM-DD format."""
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            return None
        return parsed
    except ValueError:
        return None


def format_amount(amount):
    return f"{Decimal(str(amount)):,.2f}"


def make_message(invoice, step, days_overdue):
    customer = invoice["customer"]
    invoice_id = invoice["id"]
    due_date = invoice["due_date"]
    amount = format_amount(invoice["amount"])
    currency = invoice["currency"]

    if step == "friendly":
        opening = f"Dear {customer}, this is a friendly reminder"
    elif step == "firm":
        opening = f"Dear {customer}, we are following up regarding"
    else:
        opening = f"Dear {customer}, this is a final reminder regarding"

    return (
        f"{opening} invoice {invoice_id}, due on {due_date}, "
        f"for {currency} {amount}. It is {days_overdue} days overdue. "
        "Please review the outstanding payment."
    )


def build_plan(invoices, sent, today):
    today_date = parse_date(today)
    if today_date is None:
        raise ValueError("Today must be a valid date in YYYY-MM-DD format.")

    if not isinstance(invoices, list) or not isinstance(sent, list):
        raise ValueError("Invoices and sent reminders must be JSON lists.")

    # Every invoice with a duplicated ID must be skipped.
    id_counts = {}
    for invoice in invoices:
        if isinstance(invoice, dict):
            invoice_id = invoice.get("id")
            if isinstance(invoice_id, str):
                id_counts[invoice_id] = id_counts.get(invoice_id, 0) + 1

    sent_steps = {}
    for entry in sent:
        if not isinstance(entry, dict):
            continue
        invoice_id = entry.get("invoice_id")
        step = entry.get("step")
        if isinstance(invoice_id, str) and step in STEPS:
            sent_steps.setdefault(invoice_id, set()).add(step)

    actions = []
    skipped = []
    skipped_ids = set()

    for invoice in invoices:
        if not isinstance(invoice, dict):
            skipped.append({
                "invoice_id": "",
                "reason": "invalid_amount",
            })
            continue

        invoice_id = invoice.get("id")
        if not isinstance(invoice_id, str):
            invoice_id = ""

        reason = None

        if invoice_id and id_counts.get(invoice_id, 0) > 1:
            reason = "duplicate_id"
        else:
            amount = invoice.get("amount")
            if (
                isinstance(amount, bool)
                or not isinstance(amount, (int, float))
                or not Decimal(str(amount)).is_finite()
                or amount <= 0
            ):
                reason = "invalid_amount"

        if reason is None:
            due_value = invoice.get("due_date")
            if due_value is None or due_value == "":
                reason = "missing_due_date"
            elif parse_date(due_value) is None:
                reason = "invalid_due_date"

        paid_value = invoice.get("paid_date")
        paid_date = None

        if reason is None and paid_value is not None:
            paid_date = parse_date(paid_value)
            if paid_date is None or paid_date > today_date:
                reason = "invalid_paid_date"

        if reason:
            if reason != "duplicate_id" or invoice_id not in skipped_ids:
                skipped.append({
                    "invoice_id": invoice_id,
                    "reason": reason,
                })
                if reason == "duplicate_id":
                    skipped_ids.add(invoice_id)
            continue

        if paid_date is not None:
            continue

        due_date = parse_date(invoice["due_date"])
        days_overdue = (today_date - due_date).days

        if days_overdue < THRESHOLDS["friendly"]:
            continue

        if days_overdue >= THRESHOLDS["final"]:
            step = "final"
        elif days_overdue >= THRESHOLDS["firm"]:
            step = "firm"
        else:
            step = "friendly"

        step_index = STEPS.index(step)
        already_sent = sent_steps.get(invoice_id, set())

        # A sent step at this level or any higher level blocks this action.
        if any(STEPS.index(s) >= step_index for s in already_sent):
            continue

        actions.append({
            "invoice_id": invoice_id,
            "step": step,
            "needs_approval": step in ("firm", "final"),
            "days_overdue": days_overdue,
            "message": make_message(invoice, step, days_overdue),
        })

    actions.sort(key=lambda item: item["invoice_id"])
    skipped.sort(key=lambda item: item["invoice_id"])

    return {
        "today": today,
        "actions": actions,
        "skipped": skipped,
    }


def read_json(path):
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def main():
    parser = argparse.ArgumentParser(
        description="Plan today's payment reminders."
    )
    parser.add_argument("--invoices", required=True)
    parser.add_argument("--sent", required=True)
    parser.add_argument("--today", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    try:
        plan = build_plan(
            read_json(args.invoices),
            read_json(args.sent),
            args.today,
        )
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(plan, file, indent=2)
            file.write("\n")
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
