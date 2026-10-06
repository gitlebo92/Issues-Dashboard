"""
Per-unit outage/recovery email status, from the ART NOC outage report.

check_missing_recovery_emails (in _core) sorts every unit on the report into
five lists. This module turns those lists into one status per unit, which is
what the dashboard's indicator needs: "does THIS unit need an email?".

Read-only: it reads the downloaded spreadsheet and pings units. It never
sends an email and never writes to ERP.

Re-exported by work_tool/__init__.py like every other submodule.
"""

import os

from ._core import (
    art_recovery_report_path,
    check_missing_recovery_emails,
    download_art_noc_outage_report,
    ensure_net_array,
)


# Most actionable first. A unit can sit on more than one ticket in the
# report (one ticket fully emailed, another still open), so it can land in
# more than one list; the most urgent one is what the indicator shows.
RECOVERY_EMAIL_STATUS_ORDER = (
    "needs_initial_email",
    "needs_recovery_email",
    "potential_false_positive",
    "pending_recovery",
    "email_status_up_to_date",
)


def summarize_recovery_email_status(
    needs_recovery_email, needs_initial_email, potential_false_positive,
    pending_recovery, email_status_up_to_date,
):
    """
    Collapse the five result lists (in check_missing_recovery_emails's own
    return order) into {UNIT: {"status", "issue_id", "url", "subject"}}.

    Each list item is either a plain unit string or the dict
    _with_ticket_links builds (unit/issue_id/url/subject/...). Unit keys
    are uppercased so lookups from the browser don't depend on case.
    """
    lists = {
        "needs_recovery_email": needs_recovery_email,
        "needs_initial_email": needs_initial_email,
        "potential_false_positive": potential_false_positive,
        "pending_recovery": pending_recovery,
        "email_status_up_to_date": email_status_up_to_date,
    }
    by_unit = {}
    for status in RECOVERY_EMAIL_STATUS_ORDER:
        for item in lists.get(status) or []:
            if isinstance(item, dict):
                unit = str(item.get("unit") or "").strip().upper()
                info = {
                    "status": status,
                    "issue_id": item.get("issue_id") or "",
                    "url": item.get("url") or "",
                    "subject": item.get("subject") or "",
                }
            else:
                unit = str(item or "").strip().upper()
                info = {"status": status, "issue_id": "", "url": "", "subject": ""}
            if unit and unit not in by_unit:
                by_unit[unit] = info
    return by_unit


def recovery_email_status_check(download_if_missing=True):
    """
    Run the recovery-email check against the cached ART report.

    Returns (by_unit, error). On any failure by_unit is None, so a caller
    keeping a cache can leave its last good result in place rather than
    replacing it with an empty "nothing needs an email" answer.
    """
    path = art_recovery_report_path()
    if not os.path.isfile(path):
        if not download_if_missing:
            return None, (
                "No ART NOC outage report downloaded yet. It refreshes hourly, "
                "or run Recovery Email Check -> ART once to fetch it now."
            )
        path, error = download_art_noc_outage_report()
        if error:
            return None, f"Could not download the ART NOC outage report: {error}"
    # Loads the net sheet only if it isn't loaded yet. Unlike the manual
    # route's generate_net_array(), this never empties net_array while
    # other threads might be reading it.
    ensure_net_array()
    errors = []
    results = check_missing_recovery_emails(path, errors=errors)
    if errors:
        return None, errors[0]
    return summarize_recovery_email_status(*results), None
