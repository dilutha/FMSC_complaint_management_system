"""The only way to write audit events. Values are sanitised so passwords,
tokens and secrets can never be stored, even if a caller passes them."""
import logging

from django.db import IntegrityError, transaction

from .models import AuditEvent, AuditSource

logger = logging.getLogger("apps.audit")

_SECRET_MARKERS = ("password", "token", "secret", "api_key", "authorization")
_MAX_TEXT = 1000


def _is_secret(key) -> bool:
    key = str(key).lower()
    return any(marker in key for marker in _SECRET_MARKERS)


def sanitise(value):
    """Return a JSON-safe copy with secret-looking keys redacted and long text trimmed."""
    if isinstance(value, dict):
        return {str(k): ("[redacted]" if _is_secret(k) else sanitise(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitise(v) for v in value]
    if isinstance(value, str):
        return value if len(value) <= _MAX_TEXT else value[:_MAX_TEXT] + "…"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def record(action, *, actor=None, entity=None, entity_type=None, entity_id=None, entity_label="",
           previous=None, new=None, reason="", metadata=None, source=AuditSource.API, dedup_key=None):
    """Append one audit event. Pass either `entity` (a model instance) or
    `entity_type` + `entity_id`. Returns the event (the existing one when
    `dedup_key` has already been recorded)."""
    if entity is not None:
        entity_type = entity_type or entity._meta.model_name
        entity_id = entity.pk
        entity_label = entity_label or str(entity)[:200]
    if not entity_type or entity_id is None:
        raise ValueError("record() needs an entity or entity_type and entity_id.")

    fields = dict(
        actor=actor if actor is not None and getattr(actor, "pk", None) else None,
        actor_label=(actor.display_name if actor is not None else "System")[:150],
        actor_role=(getattr(actor, "role", "") if actor is not None else "")[:20],
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        entity_label=(entity_label or "")[:200],
        previous_value=sanitise(previous),
        new_value=sanitise(new),
        reason=sanitise(reason or ""),
        metadata=sanitise(metadata or {}),
        source=source,
        dedup_key=dedup_key,
    )
    if dedup_key is None:
        return AuditEvent.objects.create(**fields)
    try:
        with transaction.atomic():
            return AuditEvent.objects.create(**fields)
    except IntegrityError:
        return AuditEvent.objects.get(dedup_key=dedup_key)
