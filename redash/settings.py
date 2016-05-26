import json
import os
import urlparse
from funcy import distinct


def parse_db_url(url):
    url_parts = urlparse.urlparse(url)
    connection = {'threadlocals': True}

    if url_parts.hostname and not url_parts.path:
        connection['name'] = url_parts.hostname
    else:
        connection['name'] = url_parts.path[1:]
        connection['host'] = url_parts.hostname
        connection['port'] = url_parts.port
        connection['user'] = url_parts.username
        connection['password'] = url_parts.password

    return connection


def fix_assets_path(path):
    fullpath = os.path.join(os.path.dirname(__file__), path)
    return fullpath


def array_from_string(str):
    array = str.split(',')
    if "" in array:
        array.remove("")

    return array


def set_from_string(str):
    return set(array_from_string(str))


def parse_boolean(str):
    return json.loads(str.lower())


def all_settings():
    from types import ModuleType

    settings = {}
    for name, item in globals().iteritems():
        if not callable(item) and not name.startswith("__") and not isinstance(item, ModuleType):
            settings[name] = item

    return settings


NAME = os.environ.get('REDASH_NAME', 're:dash')

REDIS_URL = os.environ.get('REDASH_REDIS_URL', "redis://localhost:6379/0")
PROXIES_COUNT = int(os.environ.get('REDASH_PROXIES_COUNT', "1"))

STATSD_HOST = os.environ.get('REDASH_STATSD_HOST', "127.0.0.1")
STATSD_PORT = int(os.environ.get('REDASH_STATSD_PORT', "8125"))
STATSD_PREFIX = os.environ.get('REDASH_STATSD_PREFIX', "redash")

# Connection settings for re:dash's own database (where we store the queries, results, etc)
DATABASE_CONFIG = parse_db_url(os.environ.get("REDASH_DATABASE_URL", "postgresql://redash:meila2016@localhost/redash"))

# Celery related settings
CELERY_BROKER = os.environ.get("REDASH_CELERY_BROKER", REDIS_URL)
CELERY_BACKEND = os.environ.get("REDASH_CELERY_BACKEND", CELERY_BROKER)

# The following enables periodic job (every 5 minutes) of removing unused query results.
QUERY_RESULTS_CLEANUP_ENABLED = parse_boolean(os.environ.get("REDASH_QUERY_RESULTS_CLEANUP_ENABLED", "true"))
QUERY_RESULTS_CLEANUP_COUNT = int(os.environ.get("REDASH_QUERY_RESULTS_CLEANUP_COUNT", "100"))
QUERY_RESULTS_CLEANUP_MAX_AGE = int(os.environ.get("REDASH_QUERY_RESULTS_CLEANUP_MAX_AGE", "7"))

AUTH_TYPE = os.environ.get("REDASH_AUTH_TYPE", "api_key")
PASSWORD_LOGIN_ENABLED = parse_boolean(os.environ.get("REDASH_PASSWORD_LOGIN_ENABLED", "true"))
ENFORCE_HTTPS = parse_boolean(os.environ.get("REDASH_ENFORCE_HTTPS", "false"))

MULTI_ORG = parse_boolean(os.environ.get("REDASH_MULTI_ORG", "false"))

# The following is deprecated and should be defined with the Organization object
GOOGLE_APPS_DOMAIN = set_from_string(os.environ.get("REDASH_GOOGLE_APPS_DOMAIN", ""))

GOOGLE_CLIENT_ID = os.environ.get("REDASH_GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("REDASH_GOOGLE_CLIENT_SECRET", "")
GOOGLE_OAUTH_ENABLED = GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET

SAML_METADATA_URL = os.environ.get("REDASH_SAML_METADATA_URL", "")
SAML_LOGIN_ENABLED = SAML_METADATA_URL != ""
SAML_CALLBACK_SERVER_NAME = os.environ.get("REDASH_SAML_CALLBACK_SERVER_NAME", "")

STATIC_ASSETS_PATH = fix_assets_path(os.environ.get("REDASH_STATIC_ASSETS_PATH", "../rd_ui/app/"))
JOB_EXPIRY_TIME = int(os.environ.get("REDASH_JOB_EXPIRY_TIME", 3600 * 6))
COOKIE_SECRET = os.environ.get("REDASH_COOKIE_SECRET", "c292a0a3aa32397cdb050e233733900f")
LOG_LEVEL = os.environ.get("REDASH_LOG_LEVEL", "INFO")
ANALYTICS = os.environ.get("REDASH_ANALYTICS", "")

# Mail settings:
MAIL_SERVER = os.environ.get('REDASH_MAIL_SERVER', 'localhost')
MAIL_PORT = int(os.environ.get('REDASH_MAIL_PORT', 25))
MAIL_USE_TLS = parse_boolean(os.environ.get('REDASH_MAIL_USE_TLS', 'false'))
MAIL_USE_SSL = parse_boolean(os.environ.get('REDASH_MAIL_USE_SSL', 'false'))
MAIL_USERNAME = os.environ.get('REDASH_MAIL_USERNAME', None)
MAIL_PASSWORD = os.environ.get('REDASH_MAIL_PASSWORD', None)
MAIL_DEFAULT_SENDER = os.environ.get('REDASH_MAIL_DEFAULT_SENDER', None)
MAIL_MAX_EMAILS = os.environ.get('REDASH_MAIL_MAX_EMAILS', None)
MAIL_ASCII_ATTACHMENTS = parse_boolean(os.environ.get('REDASH_MAIL_ASCII_ATTACHMENTS', 'false'))

HOST = os.environ.get('REDASH_HOST', '')

HIPCHAT_API_TOKEN = os.environ.get('REDASH_HIPCHAT_API_TOKEN', None)
HIPCHAT_API_URL = os.environ.get('REDASH_HIPCHAT_API_URL', None)
HIPCHAT_ROOM_ID = os.environ.get('REDASH_HIPCHAT_ROOM_ID', None)

WEBHOOK_ENDPOINT = os.environ.get('REDASH_WEBHOOK_ENDPOINT', None)
WEBHOOK_USERNAME = os.environ.get('REDASH_WEBHOOK_USERNAME', None)
WEBHOOK_PASSWORD = os.environ.get('REDASH_WEBHOOK_PASSWORD', None)

# CORS settings for the Query Result API (and possbily future external APIs).
# In most cases all you need to do is set REDASH_CORS_ACCESS_CONTROL_ALLOW_ORIGIN
# to the calling domain (or domains in a comma separated list).
ACCESS_CONTROL_ALLOW_ORIGIN = set_from_string(os.environ.get("REDASH_CORS_ACCESS_CONTROL_ALLOW_ORIGIN", ""))
ACCESS_CONTROL_ALLOW_CREDENTIALS = parse_boolean(os.environ.get("REDASH_CORS_ACCESS_CONTROL_ALLOW_CREDENTIALS", "false"))
ACCESS_CONTROL_REQUEST_METHOD = os.environ.get("REDASH_CORS_ACCESS_CONTROL_REQUEST_METHOD", "GET, POST, PUT")
ACCESS_CONTROL_ALLOW_HEADERS = os.environ.get("REDASH_CORS_ACCESS_CONTROL_ALLOW_HEADERS", "Content-Type")

# Query Runners
default_query_runners = [
    'redash.query_runner.big_query',
    'redash.query_runner.google_spreadsheets',
    'redash.query_runner.graphite',
    'redash.query_runner.mongodb',
    'redash.query_runner.mql',
    'redash.query_runner.mysql',
    'redash.query_runner.pg',
    'redash.query_runner.url',
    'redash.query_runner.influx_db',
    'redash.query_runner.elasticsearch',
    'redash.query_runner.presto',
    'redash.query_runner.hive_ds',
    'redash.query_runner.impala_ds',
    'redash.query_runner.vertica',
    'redash.query_runner.treasuredata',
    'redash.query_runner.oracle',
    'redash.query_runner.sqlite',
    'redash.query_runner.mssql',
]

enabled_query_runners = array_from_string(os.environ.get("REDASH_ENABLED_QUERY_RUNNERS", ",".join(default_query_runners)))
additional_query_runners = array_from_string(os.environ.get("REDASH_ADDITIONAL_QUERY_RUNNERS", ""))

QUERY_RUNNERS = distinct(enabled_query_runners + additional_query_runners)

# Support for Sentry (http://getsentry.com/). Just set your Sentry DSN to enable it:
SENTRY_DSN = os.environ.get("REDASH_SENTRY_DSN", "")

# Client side toggles:
ALLOW_SCRIPTS_IN_USER_INPUT = parse_boolean(os.environ.get("REDASH_ALLOW_SCRIPTS_IN_USER_INPUT", "false"))
DATE_FORMAT = os.environ.get("REDASH_DATE_FORMAT", "DD/MM/YY")

# Features:
FEATURE_ALLOW_ALL_TO_EDIT_QUERIES = parse_boolean(os.environ.get("REDASH_FEATURE_ALLOW_ALL_TO_EDIT", "true"))
FEATURE_TABLES_PERMISSIONS = parse_boolean(os.environ.get("REDASH_FEATURE_TABLES_PERMISSIONS", "false"))
VERSION_CHECK = parse_boolean(os.environ.get("REDASH_VERSION_CEHCK", "true"))

# BigQuery
BIGQUERY_HTTP_TIMEOUT = int(os.environ.get("REDASH_BIGQUERY_HTTP_TIMEOUT", "600"))

# Enhance schema fetching
SCHEMA_RUN_TABLE_SIZE_CALCULATIONS = parse_boolean(os.environ.get("REDASH_SCHEMA_RUN_TABLE_SIZE_CALCULATIONS", "false"))

### Common Client config
COMMON_CLIENT_CONFIG = {
    'allowScriptsInUserInput': ALLOW_SCRIPTS_IN_USER_INPUT,
    'dateFormat': DATE_FORMAT,
    'dateTimeFormat': "{0} HH:mm".format(DATE_FORMAT),
    'allowAllToEditQueries': FEATURE_ALLOW_ALL_TO_EDIT_QUERIES,
}
