"""Notification dispatch.

notify() is idempotent: each (recipient, dedup_key) pair is stored at most once
(enforced by a unique constraint), so re-processing an event never produces a
second notification or a second email.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Role, User

from .models import Notification

logger = logging.getLogger("apps.notifications")


def notify(recipients, *, event_type, title, body="", case=None, target_type="", target_id=None, dedup_key,
           exclude=None):
    """Create one notification per recipient. Returns the newly created ones."""
    exclude_id = getattr(exclude, "pk", None)
    users = {u.pk: u for u in recipients if u is not None and u.is_active and u.pk != exclude_id}
    if not users:
        return []
    already = set(
        Notification.objects.filter(dedup_key=dedup_key, recipient_id__in=users).values_list("recipient_id", flat=True)
    )
    fresh = [
        Notification(
            recipient_id=pk,
            event_type=event_type,
            title=title[:150],
            body=(body or "")[:500],
            case=case,
            target_type=target_type,
            target_id=target_id,
            dedup_key=dedup_key,
        )
        for pk in users
        if pk not in already
    ]
    if not fresh:
        return []
    # ignore_conflicts covers a concurrent delivery of the same event.
    Notification.objects.bulk_create(fresh, ignore_conflicts=True)
    created = list(
        Notification.objects.filter(dedup_key=dedup_key, recipient_id__in=[n.recipient_id for n in fresh])
        .exclude(recipient_id__in=already)
        .select_related("recipient")
    )
    if settings.FMSC_NOTIFICATIONS["EMAIL_ENABLED"]:
        ids = [n.pk for n in created]
        transaction.on_commit(lambda: send_pending_emails(ids))
    return created


def send_pending_emails(notification_ids):
    """Email each notification at most once. The row is claimed before sending."""
    for notification in Notification.objects.filter(pk__in=notification_ids).select_related("recipient"):
        if not notification.recipient.email:
            continue
        claimed = Notification.objects.filter(pk=notification.pk, email_sent_at__isnull=True).update(
            email_sent_at=timezone.now()
        )
        if not claimed:
            continue
        try:
            send_mail(
                subject=f"[FMSC] {notification.title}",
                message=f"{notification.body}\n\nOpen the FMSC app to see the details.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.recipient.email],
            )
        except Exception:  # an email outage must not affect in-app notifications
            logger.exception("Email delivery failed for notification %s", notification.pk)
            Notification.objects.filter(pk=notification.pk).update(email_sent_at=None)


def mark_read(notification):
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
    return notification


def mark_all_read(user) -> int:
    return Notification.objects.filter(recipient=user, is_read=False).update(is_read=True, read_at=timezone.now())


# --- Recipient helpers ------------------------------------------------------------


def case_admins():
    return list(
        User.objects.filter(is_active=True).filter(Q(role__in=[Role.CASE_ADMIN, Role.SYSTEM_ADMIN]) | Q(is_superuser=True))
    )


def management_viewers():
    return list(User.objects.filter(is_active=True, role=Role.MANAGEMENT))


def authority_members(authority):
    if authority is None or not authority.is_active:
        return []
    return list(authority.members.filter(is_active=True))
