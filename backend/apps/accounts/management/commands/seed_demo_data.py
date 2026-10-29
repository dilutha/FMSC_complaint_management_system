"""Representative demo cases for the dashboards and workflows (development only).

    python manage.py seed_demo_data

Creates demo users first (seed_demo_users), then drives each scenario through
the real workflow services, so status history, messages, notifications and
audit records are genuine. Idempotent: a scenario is skipped when its case
(same title, same demo submitter) already exists. Refuses to run unless
DJANGO_DEBUG=true or FMSC_ALLOW_DEMO_USERS=true.
"""
import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.cases.models import Authority, Case, Category
from apps.cases.services import assignment, submission, updates, workflow
from apps.suggestions import services as suggestions

# (submitter, title, description, category, location, priority, case type, steps)
# steps: ("review", msg) | ("assign", dept_code, msg) | ("progress", msg) | ("solve", note) | ("confirm",)
#        | ("accept_suggestion", dept_code, reason)
SCENARIOS = [
    ("demo_student", "Wi-Fi keeps dropping in Computer Lab 2",
     "The Wi-Fi connection drops every few minutes during practical sessions in Computer Lab 2.",
     "it", "Computer Lab 2", "normal", "complaint", []),
    ("demo_lecturer", "Projector flickers in Lecture Hall B",
     "The projector in Lecture Hall B flickers constantly, making slides hard to read.",
     "classroom", "Lecture Hall B", "normal", "complaint",
     [("review", "Reviewing the report before assigning it to a department.")]),
    ("demo_non_academic", "Roof leak in the records room",
     "Rain water leaks through the ceiling of the records room and is damaging files.",
     "maintenance", "Records room, Administration building", "urgent", "complaint",
     [("review", "Urgent: risk of damage to records."),
      ("assign", "maintenance", "Building repairs are handled by the Maintenance Department.")]),
    ("demo_student", "Examination results missing on the student portal",
     "My semester examination results are not visible on the student portal.",
     "examination", "Student portal", "normal", "complaint",
     [("assign", "examination-unit", "Examination records are maintained by the Examination Unit."),
      ("progress", "The Examination Unit is verifying the relevant examination records.")]),
    ("demo_lecturer", "Statistics software licences expired in Lab 1",
     "The statistics software in Computer Lab 1 shows a licence-expired error.",
     "it", "Computer Lab 1", "urgent", "complaint",
     [("assign", "it-unit", "Software licences are managed by the IT Department."),
      ("progress", "The IT Department has contacted the vendor about renewal."),
      ("solve", "The licences were renewed and the software was reactivated on all lab computers.")]),
    ("demo_non_academic", "Clarification needed on the leave approval process",
     "The approval steps for staff leave requests are unclear and requests are delayed.",
     "other", "Faculty Office", "normal", "complaint",
     [("assign", "deans-office", "Faculty procedures are clarified by the Dean's Office.")]),
    ("demo_student", "Broken chairs in Lecture Hall C",
     "Several chairs in the front rows of Lecture Hall C are broken.",
     "classroom", "Lecture Hall C", "normal", "complaint",
     [("assign", "maintenance", "Furniture repairs are handled by the Maintenance Department."),
      ("progress", "The maintenance team has inspected the reported chairs."),
      ("solve", "Eight chairs were repaired and two were replaced."),
      ("confirm",)]),
    ("demo_student", "Extend library opening hours during examinations",
     "Please keep the faculty library open until 10 pm during the examination period.",
     "other", "Faculty library", "normal", "suggestion", []),
    ("demo_lecturer", "Add charging points in the student study area",
     "Students need more power outlets near the study tables.",
     "maintenance", "Student study area", "normal", "suggestion",
     [("accept_suggestion", "maintenance", "A useful improvement within this year's maintenance budget.")]),
]


class Command(BaseCommand):
    help = "Create representative demo cases in every workflow state (development only; idempotent)."

    def handle(self, *args, **options):
        allowed = settings.DEBUG or os.environ.get("FMSC_ALLOW_DEMO_USERS", "").lower() in ("1", "true", "yes")
        if not allowed:
            raise CommandError("Demo data is for local development only (set DJANGO_DEBUG=true).")
        call_command("seed_demo_users", quiet_table=True, stdout=self.stdout)
        case_admin = User.objects.get(username="demo_case_admin")
        created = skipped = 0
        for submitter_name, title, description, category, location, priority, case_type, steps in SCENARIOS:
            submitter = User.objects.get(username=submitter_name)
            if Case.objects.filter(title=title, submitted_by=submitter).exists():
                skipped += 1
                continue
            case = submission.submit_case(
                actor=submitter, title=title, description=description, case_type=case_type,
                category=Category.objects.get(code=category), location=location, requested_priority=priority,
                declaration_accepted=True,
            )
            for step in steps:
                case = Case.objects.get(pk=case.pk)
                self._apply(case, step, case_admin, submitter)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Demo cases ready: {created} created, {skipped} already present."))

    @staticmethod
    def _department_user(code):
        return User.objects.filter(authorities__code=code, username__startswith="demo_").first()

    def _apply(self, case, step, case_admin, submitter):
        kind = step[0]
        if kind == "review":
            workflow.transition(case, "under_review", actor=case_admin, reason=step[1])
        elif kind == "assign":
            assignment.assign_case(case, actor=case_admin, authority=Authority.objects.get(code=step[1]),
                                   message=step[2])
        elif kind == "progress":
            officer = self._department_user(case.assigned_authority.code)
            workflow.transition(case, "in_progress", actor=officer, reason=step[1])
        elif kind == "solve":
            officer = self._department_user(case.assigned_authority.code)
            workflow.transition(case, "solved", actor=officer, resolution_note=step[1])
        elif kind == "confirm":
            updates.verify_resolution(case, actor=submitter, confirmed=True, feedback="Thank you, it is fixed.")
        elif kind == "accept_suggestion":
            suggestions.accept(case, actor=case_admin, responsible_unit=Authority.objects.get(code=step[1]),
                               reason=step[2])
