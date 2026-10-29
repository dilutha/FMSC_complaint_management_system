"""Database-level protection for the audit log (PostgreSQL).

Blocks UPDATE and DELETE on audit rows even from code that bypasses the ORM.
The single permitted update is Django's ON DELETE SET NULL when a user account
is removed (actor_id becomes NULL; the actor_label snapshot keeps the name).
Other databases rely on the model and queryset guards in apps.audit.models.
"""
from django.db import migrations

CREATE = """
CREATE OR REPLACE FUNCTION audit_event_protect() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'audit events cannot be deleted';
    END IF;
    IF (to_jsonb(NEW) - 'actor_id') IS DISTINCT FROM (to_jsonb(OLD) - 'actor_id')
       OR (NEW.actor_id IS NOT NULL AND NEW.actor_id IS DISTINCT FROM OLD.actor_id) THEN
        RAISE EXCEPTION 'audit events cannot be modified';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_event_protect
BEFORE UPDATE OR DELETE ON audit_auditevent
FOR EACH ROW EXECUTE FUNCTION audit_event_protect();
"""

DROP = """
DROP TRIGGER IF EXISTS audit_event_protect ON audit_auditevent;
DROP FUNCTION IF EXISTS audit_event_protect();
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(DROP)


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
