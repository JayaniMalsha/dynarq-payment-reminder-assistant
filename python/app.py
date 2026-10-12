"""Owner-facing payment reminder assistant."""

import html
import json
import os
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from plan import build_plan, format_amount, read_json

PORT = int(os.environ.get("PORT", "8000"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "../data"))
TODAY = os.environ.get("TODAY", date.today().isoformat())

# Decisions are kept in memory while the server runs.
decisions = {}

SKIP_REASONS = {
    "duplicate_id": "This invoice ID appears more than once.",
    "invalid_amount": "The amount is missing, invalid, or not positive.",
    "missing_due_date": "The due date is missing.",
    "invalid_due_date": "The due date is not a valid YYYY-MM-DD date.",
    "invalid_paid_date": "The paid date is invalid or after today.",
}


def safe(value):
    """Escape values before inserting them into HTML."""
    return html.escape(str(value), quote=True)


def render_page():
    """Build the HTML page using the shared rules engine."""
    try:
        invoices = read_json(DATA_DIR / "invoices.json")
        sent = read_json(DATA_DIR / "sent.json")
        plan = build_plan(invoices, sent, TODAY)

        invoice_map = {
            item.get("id"): item
            for item in invoices
            if isinstance(item, dict)
        }
        error = None

    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        plan = {"actions": [], "skipped": []}
        invoice_map = {}
        error = str(exc)

    parts = [
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Payment Reminder Assistant</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font: 16px/1.5 Arial, sans-serif;
      max-width: 1050px;
      margin: 0 auto;
      padding: 20px;
      color: #222;
      background: #f7f8fa;
    }
    h1, h2 { line-height: 1.25; }
    .card {
      background: white;
      border: 1px solid #d5d9df;
      border-radius: 10px;
      padding: 16px;
      margin: 14px 0;
      overflow-wrap: anywhere;
    }
    .error {
      background: #fff0f0;
      border: 1px solid #c62828;
      border-radius: 8px;
      padding: 12px;
      overflow-wrap: anywhere;
    }
    .muted { color: #555; }
    button {
      min-height: 44px;
      padding: 10px 16px;
      margin: 5px 8px 5px 0;
      cursor: pointer;
      font-size: 1rem;
      border: 1px solid #888;
      border-radius: 6px;
      background: white;
      color: #222;
    }
    button:focus-visible {
      outline: 3px solid #245dcc;
      outline-offset: 3px;
    }
    .approve { background: #e8f5e9; }
    .reject { background: #ffebee; }
    .status { font-weight: bold; }
    @media (max-width: 480px) {
      body { padding: 12px; }
      .card { padding: 12px; }
      button { width: 100%; margin: 5px 0; }
    }
  </style>
</head>
<body>
  <h1>Payment Reminder Assistant</h1>
  <p class="muted">Today's plan: """
        + safe(TODAY)
        + """</p>
"""
    ]

    if error is not None:
        parts.append(
            '<section class="error"><strong>Unable to load the plan.</strong><p>'
            + safe(error)
            + "</p><p>Check the invoice and sent-reminder data files.</p></section>"
        )
        parts.append("</body></html>")
        return "".join(parts).encode("utf-8")

    actions = plan["actions"]
    parts.append("<h2>Today's reminders</h2>")

    if not actions:
        parts.append(
            "<p>There are no reminders to action today.</p>"
        )

    for action in actions:
        invoice_id = action["invoice_id"]
        invoice_data = invoice_map.get(invoice_id, {})
        decision = decisions.get(invoice_id, "Pending")

        parts.append('<section class="card">')
        parts.append(
            "<h3>"
            + safe(invoice_data.get("customer", "Unknown customer"))
            + " — Invoice "
            + safe(invoice_id)
            + "</h3>"
        )

        try:
            amount_text = format_amount(invoice_data["amount"])
        except (KeyError, ValueError, TypeError):
            amount_text = "Unavailable"

        parts.append(
            "<p><strong>Amount:</strong> "
            + safe(invoice_data.get("currency", ""))
            + " "
            + safe(amount_text)
            + "<br><strong>Due date:</strong> "
            + safe(invoice_data.get("due_date", ""))
            + "<br><strong>Days overdue:</strong> "
            + safe(action["days_overdue"])
            + "</p>"
        )

        parts.append(
            "<p><strong>Reminder step:</strong> "
            + safe(action["step"].title())
            + "<br><strong>Approval required:</strong> "
            + ("Yes" if action["needs_approval"] else "No")
            + "</p>"
        )

        parts.append(
            "<p><strong>Message:</strong><br>"
            + safe(action["message"])
            + "</p>"
        )

        if action["needs_approval"]:
            parts.append(
                '<p class="status">Decision: '
                + safe(decision)
                + "</p>"
            )

            # Approval decisions are accepted only for planned reminders
            # that require approval.
            if decision == "Pending":
                parts.append(
                    '<form method="post" action="/">'
                    '<input type="hidden" name="invoice_id" value="'
                    + safe(invoice_id)
                    + '">'
                    '<button class="approve" type="submit" '
                    'name="decision" value="Approved">'
                    "Approve reminder</button>"
                    '<button class="reject" type="submit" '
                    'name="decision" value="Rejected">'
                    "Reject reminder</button>"
                    "</form>"
                )

        parts.append("</section>")

    parts.append("<h2>Skipped invoices</h2>")

    if not plan["skipped"]:
        parts.append("<p>No invoices were skipped.</p>")

    for item in plan["skipped"]:
        reason = SKIP_REASONS.get(
            item["reason"], "The invoice data is invalid."
        )
        parts.append(
            '<section class="card"><strong>Invoice '
            + safe(item["invoice_id"] or "(missing ID)")
            + "</strong><p>"
            + safe(reason)
            + "</p></section>"
        )

    parts.append("</body></html>")
    return "".join(parts).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            content = render_page()
            self.send_response(200)
        except Exception:
            content = (
                b"Unable to render the page. Check the application and data."
            )
            self.send_response(500)

        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid request length")
            return

        if length <= 0 or length > 10000:
            self.send_error(400, "Invalid request length")
            return

        try:
            body = self.rfile.read(length).decode("utf-8")
            form = parse_qs(body)
        except (UnicodeDecodeError, ValueError):
            self.send_error(400, "Invalid form submission")
            return

        invoice_id = form.get("invoice_id", [""])[0]
        decision = form.get("decision", [""])[0]

        if decision not in ("Approved", "Rejected") or not invoice_id:
            self.send_error(400, "Invalid decision")
            return

        # Verify that the invoice currently has a planned action requiring
        # approval before recording the decision.
        try:
            invoices = read_json(DATA_DIR / "invoices.json")
            sent = read_json(DATA_DIR / "sent.json")
            plan = build_plan(invoices, sent, TODAY)

            eligible_ids = {
                action["invoice_id"]
                for action in plan["actions"]
                if action["needs_approval"]
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.send_error(500, "Unable to validate the reminder")
            return

        if invoice_id not in eligible_ids:
            self.send_error(400, "This invoice does not require approval")
            return

        decisions[invoice_id] = decision

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, format_string, *args):
        # Keep terminal output quiet.
        pass


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(
        f"Payment Reminder Assistant running at http://localhost:{PORT}"
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
