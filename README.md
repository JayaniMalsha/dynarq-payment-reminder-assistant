# Payment Reminder Assistant

A Python-based payment reminder planner for small-business invoices, with a web page for reviewing and approving reminders.

## Requirements
- Python 3.10 or newer
- No third-party Python packages required

## Run Tests
From the project root:
```bash
python -m unittest discover -s python/tests -v
```

## Generate the Reminder Plan
From the `python/` directory:
```bash
python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json
```
The command writes the planned actions and skipped invoices to `actions.json`.

## Run the Web Page
From the `python/` directory:
```bash
python app.py
```
Open `http://localhost:8000`. Configure `PORT`, `DATA_DIR`, and `TODAY` using environment variables when needed.

## Decisions and Rules
- Calculate overdue days using calendar dates.
- Send a friendly reminder from 3 days overdue, a firm reminder from 10 days, and a final reminder from 24 days.
- Require approval for firm and final reminders; friendly reminders do not require approval.
- Skip invalid invoice data, paid invoices, invoices not yet 3 days overdue, and reminders already sent at the same or a higher step.
- Apply validation in the specified order and sort actions and skipped invoices by invoice ID.
- Reminder messages include invoice details and overdue days without inventing fees, interest, or payment deadlines.
- Keep approval and rejection decisions in memory while the web app is running.

## Future Improvements
- Add more automated tests for validation precedence, duplicate IDs, sent history, and date boundaries.
- Persist approval decisions and add authentication for production use.
- Improve logging, error reporting, and deployment configuration.