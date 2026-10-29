"""Merged, visibility-filtered case timeline."""
from apps.cases.models import Case, CaseStatus, UpdateKind

from . import access


def _role_label(role):
    from apps.accounts.models import Role

    return Role(role).label if role in Role.values else ""


def _actor_factory(viewer, viewer_is_staff):
    def _actor(user, role="", authority=None):
        """`role` and `authority` are the snapshots stored with the entry, so the
        label shows the capacity the person acted in at the time."""
        if user is None:
            return {"id": None, "name": "System", "role": "", "department": None}
        role_label = _role_label(role or getattr(user, "role", ""))
        department = authority.name if authority else None
        if viewer_is_staff:
            name = user.display_name
        elif user.pk == viewer.pk:
            name = "You"
        else:
            # Submitters see the role or department rather than individual staff identities.
            name = department or role_label or "Faculty staff"
        return {"id": user.pk if (viewer_is_staff or user.pk == viewer.pk) else None, "name": name,
                "role": role_label, "department": department}

    return _actor


def build_timeline(case: Case, viewer) -> list:
    is_staff = access.is_staff_for(viewer, case)
    _actor = _actor_factory(viewer, is_staff)
    entries = []

    for h in case.status_history.select_related("changed_by", "actor_authority"):
        entries.append(
            {
                "type": "status_change",
                "at": h.created_at,
                "title": CaseStatus(h.to_status).label,
                "body": h.reason,
                "from_status": h.from_status or None,
                "to_status": h.to_status,
                "actor": _actor(h.changed_by, h.actor_role, h.actor_authority),
                "is_internal": False,
            }
        )

    updates = case.updates.select_related("author", "author_authority").prefetch_related("attachments")
    if not is_staff:
        updates = updates.filter(is_internal=False)
    for u in updates:
        if u.kind == UpdateKind.INFORMATION_REQUEST:
            continue  # already shown as the status change reason
        entries.append(
            {
                "type": "update",
                "at": u.created_at,
                "title": UpdateKind(u.kind).label,
                "body": u.body,
                "kind": u.kind,
                "actor": _actor(u.author, u.author_role, u.author_authority),
                "is_internal": u.is_internal,
                "attachment_ids": [a.pk for a in u.attachments.all()],
            }
        )

    if is_staff:
        for a in case.assignments.select_related("authority", "assigned_by", "recommended_authority"):
            entries.append(
                {
                    "type": "assignment",
                    "at": a.created_at,
                    "title": f"Assigned to {a.authority.name}",
                    "body": a.internal_note,
                    "actor": _actor(a.assigned_by),
                    "is_internal": True,
                    "is_override": a.is_override,
                    "recommended_authority": a.recommended_authority.name if a.recommended_authority else None,
                }
            )
        for d in case.deadline_changes.select_related("changed_by"):
            entries.append(
                {
                    "type": "deadline_change",
                    "at": d.created_at,
                    "title": "Deadline changed",
                    "body": d.reason,
                    "old_deadline": d.old_deadline,
                    "new_deadline": d.new_deadline,
                    "actor": _actor(d.changed_by),
                    "is_internal": True,
                }
            )
        for e in case.escalations.all():
            entries.append(
                {
                    "type": "escalation",
                    "at": e.created_at,
                    "title": f"Escalated (level {e.level})",
                    "body": "Deadline missed.",
                    "actor": _actor(None),
                    "is_internal": True,
                }
            )

    entries.sort(key=lambda e: (e["at"], {"status_change": 0, "assignment": 1}.get(e["type"], 2)))
    return entries
