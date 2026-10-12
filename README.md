# Payment Reminder Assistant

A Python-based payment reminder planner with a web interface for reviewing and approving reminders.

## Requirements
- Python 3.10+
- No third-party packages required

## Run Tests
From the project root:
```bash
python -m unittest discover -s python/tests -v
```

## Generate Reminder Plan
From the `python/` directory:
```bash
python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json
```

## Run Web Page
From the `python/` directory:
```bash
python app.py
```
Open http://localhost:8000. Configure `PORT`, `DATA_DIR`, and `TODAY` with environment variables if needed.

## Decisions and Rules
- Friendly reminders start at 3 days overdue, firm at 10, and final at 24.
- Firm and final reminders require approval; friendly reminders do not.
- Skip invalid invoices, paid invoices, invoices less than 3 days overdue, and reminders already sent at the same or a higher step.
- Validate data in the specified order and sort actions and skipped invoices by invoice ID.
- Messages avoid invented fees, interest, and deadlines.
- Approval and rejection decisions remain in memory while the app runs.

## Future Improvements
- Expand tests for validation precedence, duplicate IDs, sent history, and date boundaries.
- Persist decisions and add authentication.
- Improve logging, error handling, and deployment configuration.