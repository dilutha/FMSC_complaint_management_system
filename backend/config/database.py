"""Database configuration from environment variables.

Kept separate from settings.py so the rules below can be unit-tested.

Precedence (documented in backend/database/README.md):

1. Engine: ``FMSC_DB_ENGINE=sqlite`` (the case module's existing local-test
   switch) wins; otherwise ``DB_ENGINE``; default PostgreSQL. SQLite is only
   allowed for local development and tests.
2. Connection: either ``DATABASE_URL`` **or** the individual ``DB_NAME``,
   ``DB_USER``, ``DB_PASSWORD``, ``DB_HOST``, ``DB_PORT`` variables. Setting
   both is an error rather than a silent precedence surprise. The original
   ``POSTGRES_*`` names are still read as fallbacks for ``DB_*``.
3. Options: ``DB_SSLMODE``, ``DB_SSLROOTCERT``, ``DB_CONNECT_TIMEOUT``,
   ``DB_CONN_MAX_AGE`` and ``DB_POOL_MODE`` apply to both forms; a value in the
   ``DATABASE_URL`` query string (e.g. ``?sslmode=verify-full``) wins.

Supabase specifics:

* Hosts ending in ``supabase.co`` / ``supabase.com`` default to
  ``sslmode=require`` and refuse weaker modes.
* The shared pooler (``*.pooler.supabase.com``) needs the user name in the form
  ``<role>.<project-ref>``.
* Transaction-mode pooling (port 6543) does not support prepared statements or
  persistent connections, so both are turned off.
* Tests never run against a Supabase host: Django's test runner creates and
  drops a whole database.

Connection pooling (``DB_POOL``, default on outside tests):
  Opening a connection to a hosted database is expensive (TLS + auth over the
  internet; ~3.7 s measured from Sri Lanka to Supabase eu-north-1). Django's
  development server handles every request in a new thread, so per-thread
  persistent connections (CONN_MAX_AGE) are never reused there. A psycopg
  connection pool is shared by all threads of the process, so requests reuse
  open connections. Django requires CONN_MAX_AGE=0 when pooling. Pool size is
  kept small (default 4) to stay well inside Supabase's pooler client limits.
"""
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
SECURE_SSL_MODES = ("require", "verify-ca", "verify-full")
POOL_MODES = ("direct", "session", "transaction")
SUPABASE_SUFFIXES = (".supabase.co", ".supabase.com")
_POSTGRES_ENGINES = ("postgresql", "postgres", "django.db.backends.postgresql")
_SQLITE_ENGINES = ("sqlite", "sqlite3", "django.db.backends.sqlite3")
_SEPARATE_KEYS = ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT")


def is_supabase_host(host: str) -> bool:
    return bool(host) and host.lower().rstrip(".").endswith(SUPABASE_SUFFIXES)


def is_supabase_pooler(host: str) -> bool:
    return is_supabase_host(host) and ".pooler." in host.lower()


def _get(environ, *names, default=None):
    for name in names:
        value = environ.get(name)
        if value not in (None, ""):
            return value
    return default


def _int(value, name):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ImproperlyConfigured(f"{name} must be a whole number.") from None


def _from_url(url: str) -> tuple[dict, dict]:
    parts = urlsplit(url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must start with postgresql:// or postgres://.")
    if not parts.hostname:
        raise ImproperlyConfigured("DATABASE_URL has no host name.")
    conn = {
        "NAME": unquote(parts.path.lstrip("/")) or "postgres",
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname,
        "PORT": str(parts.port or 5432),
    }
    return conn, dict(parse_qsl(parts.query))


def build_databases(environ, *, sqlite_path, allow_sqlite: bool, testing: bool) -> dict:
    """Return Django's DATABASES setting for the given environment mapping."""
    legacy = _get(environ, "FMSC_DB_ENGINE")
    engine = (legacy if legacy in _SQLITE_ENGINES else _get(environ, "DB_ENGINE", "FMSC_DB_ENGINE",
                                                            default="postgresql")).strip().lower()
    if engine in _SQLITE_ENGINES:
        if not allow_sqlite:
            raise ImproperlyConfigured("SQLite is only permitted for local development and tests.")
        return {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": sqlite_path}}
    if engine not in _POSTGRES_ENGINES:
        raise ImproperlyConfigured(f"Unsupported DB_ENGINE '{engine}'. Use django.db.backends.postgresql.")

    url = _get(environ, "DATABASE_URL")
    if url:
        clash = [k for k in _SEPARATE_KEYS if _get(environ, k)]
        if clash:
            raise ImproperlyConfigured(
                f"Set either DATABASE_URL or {', '.join(clash)}, not both (see backend/database/README.md)."
            )
        conn, url_options = _from_url(url)
    else:
        conn = {
            "NAME": _get(environ, "DB_NAME", "POSTGRES_DB", default="fmsc_cases"),
            "USER": _get(environ, "DB_USER", "POSTGRES_USER", default="fmsc"),
            "PASSWORD": _get(environ, "DB_PASSWORD", "POSTGRES_PASSWORD", default=""),
            "HOST": _get(environ, "DB_HOST", "POSTGRES_HOST", default="localhost"),
            "PORT": str(_get(environ, "DB_PORT", "POSTGRES_PORT", default="5432")),
        }
        url_options = {}

    host = conn["HOST"]
    supabase = is_supabase_host(host)
    if testing and supabase:
        raise ImproperlyConfigured(
            "Tests must not run against a Supabase database (the test runner creates and drops a database). "
            "Run tests with FMSC_DB_ENGINE=sqlite or point DB_HOST at a local PostgreSQL server."
        )
    if is_supabase_pooler(host) and "." not in conn["USER"]:
        raise ImproperlyConfigured(
            "The Supabase pooler needs the user name as <role>.<project-ref>, e.g. postgres.abcdefghijklmnop."
        )

    sslmode = url_options.pop("sslmode", None) or _get(environ, "DB_SSLMODE",
                                                       default="require" if supabase else "prefer")
    if sslmode not in SSL_MODES:
        raise ImproperlyConfigured(f"DB_SSLMODE must be one of: {', '.join(SSL_MODES)}.")
    if supabase and sslmode not in SECURE_SSL_MODES:
        raise ImproperlyConfigured("Supabase connections must use DB_SSLMODE=require, verify-ca or verify-full.")
    sslrootcert = url_options.pop("sslrootcert", None) or _get(environ, "DB_SSLROOTCERT")
    if sslmode in ("verify-ca", "verify-full") and not sslrootcert:
        raise ImproperlyConfigured(f"DB_SSLMODE={sslmode} needs DB_SSLROOTCERT (the CA certificate file path).")

    pool_mode = (_get(environ, "DB_POOL_MODE") or ("transaction" if conn["PORT"] == "6543" else "direct")).lower()
    if pool_mode not in POOL_MODES:
        raise ImproperlyConfigured(f"DB_POOL_MODE must be one of: {', '.join(POOL_MODES)}.")

    options = {
        "sslmode": sslmode,
        "connect_timeout": _int(url_options.pop("connect_timeout", None) or _get(environ, "DB_CONNECT_TIMEOUT",
                                                                                 default="10"),
                                "DB_CONNECT_TIMEOUT"),
        "application_name": url_options.pop("application_name", None) or "fmsc-backend",
        **url_options,
    }
    if sslrootcert:
        options["sslrootcert"] = sslrootcert

    conn_max_age = _int(_get(environ, "DB_CONN_MAX_AGE", "POSTGRES_CONN_MAX_AGE", default="60"), "DB_CONN_MAX_AGE")
    health_checks = conn_max_age > 0
    disable_server_side_cursors = False
    if pool_mode == "transaction":
        # The shared pooler cannot keep prepared statements, cursors or session
        # state between transactions (Supabase docs, "Transaction mode").
        options["prepare_threshold"] = None
        conn_max_age = 0
        disable_server_side_cursors = True

    use_pool = _get(environ, "DB_POOL", default="false" if testing else "true").lower() in ("1", "true", "yes", "on")
    if use_pool:
        options["pool"] = {
            "min_size": _int(_get(environ, "DB_POOL_MIN_SIZE", default="1"), "DB_POOL_MIN_SIZE"),
            "max_size": _int(_get(environ, "DB_POOL_MAX_SIZE", default="4"), "DB_POOL_MAX_SIZE"),
            # Seconds a request waits for a free connection before failing clearly.
            "timeout": _int(_get(environ, "DB_POOL_TIMEOUT", default="15"), "DB_POOL_TIMEOUT"),
            # Retire idle/old connections before the server or pooler drops them.
            "max_idle": _int(_get(environ, "DB_POOL_MAX_IDLE", default="120"), "DB_POOL_MAX_IDLE"),
            "max_lifetime": _int(_get(environ, "DB_POOL_MAX_LIFETIME", default="900"), "DB_POOL_MAX_LIFETIME"),
        }
        conn_max_age = 0  # required by Django when pooling
        # A health check costs one network round trip (~250 ms to Supabase) per
        # request, so it is opt-in; broken connections are discarded by the pool.
        health_checks = _get(environ, "DB_POOL_CHECK", default="false").lower() in ("1", "true", "yes", "on")

    return {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            **conn,
            "CONN_MAX_AGE": conn_max_age,
            "CONN_HEALTH_CHECKS": health_checks,
            "DISABLE_SERVER_SIDE_CURSORS": disable_server_side_cursors,
            "OPTIONS": options,
        }
    }


def describe(db: dict) -> dict:
    """Connection summary that is safe to print: never includes the password."""
    options = db.get("OPTIONS", {})
    return {
        "engine": db["ENGINE"].rsplit(".", 1)[-1],
        "host": "(local file)" if "sqlite" in db["ENGINE"] else db.get("HOST"),
        "port": db.get("PORT"),
        "name": str(db.get("NAME")),
        "user": db.get("USER"),
        "password_set": bool(db.get("PASSWORD")),
        "sslmode": options.get("sslmode"),
        "pool_mode": "transaction" if db.get("DISABLE_SERVER_SIDE_CURSORS") else "direct/session",
        "django_pool": (f"on (max {options['pool']['max_size']})" if isinstance(options.get("pool"), dict)
                        else "off"),
        "supabase": is_supabase_host(db.get("HOST") or ""),
    }
