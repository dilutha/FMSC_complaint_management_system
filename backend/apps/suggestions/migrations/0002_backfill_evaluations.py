"""Create evaluation records for suggestion cases submitted before this app
existed. The status is derived from the case status (same mapping as
services.initial_status_for). Safe to re-run: existing records are skipped."""
from django.db import migrations

STATUS_FROM_CASE = {
    "submitted": "submitted",
    "under_review": "under_evaluation",
    "waiting_for_information": "under_evaluation",
    "assigned": "accepted",
    "in_progress": "accepted",
    "reopened": "accepted",
    "solved": "implemented",
    "closed": "implemented",
    "rejected": "declined",
}


def backfill(apps, schema_editor):
    Case = apps.get_model("cases", "Case")
    History = apps.get_model("cases", "CaseStatusHistory")
    Evaluation = apps.get_model("suggestions", "SuggestionEvaluation")
    for case in Case.objects.filter(case_type="suggestion", suggestion_evaluation__isnull=True):
        status = STATUS_FROM_CASE[case.status]
        reason = ""
        if status == "declined":
            last = History.objects.filter(case=case, to_status="rejected").order_by("-id").first()
            reason = (last.reason if last else "") or "Rejected before suggestion evaluation was recorded."
        Evaluation.objects.create(
            case=case, status=status, responsible_unit_id=case.assigned_authority_id, decision_reason=reason,
            implemented_at=case.solved_at if status == "implemented" else None,
            progress_percent=100 if status == "implemented" else 0,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("suggestions", "0001_initial"),
        ("cases", "0001_initial"),
    ]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
