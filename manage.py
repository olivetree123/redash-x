#!/usr/bin/env python
"""
CLI to manage redash.
"""
import json

from flask_script import Manager

from redash import settings, models, __version__
from redash.wsgi import app
from redash.cli import users, database, data_sources, organization
from redash.monitor import get_status

manager = Manager(app)
manager.add_command("database", database.manager)
manager.add_command("users", users.manager)
manager.add_command("ds", data_sources.manager)
manager.add_command("org", organization.manager)



@manager.command
def version():
    """Displays re:dash version."""
    print __version__

@manager.command
def status():
    print json.dumps(get_status(), indent=2)

@manager.command
def runworkers():
    """Start workers (deprecated)."""
    print "** This command is deprecated. Please use Celery's CLI to control the workers. **"


@manager.shell
def make_shell_context():
    from redash.models import db
    return dict(app=app, db=db, models=models)


@manager.command
def check_settings():
    """Show the settings as re:dash sees them (useful for debugging)."""
    for name, item in settings.all_settings().iteritems():
        print "{} = {}".format(name, item)

@manager.command
def send_test_mail():
    from redash import mail
    from flask_mail import Message

    mail.send(Message(subject="Test Message from re:dash", recipients=[settings.MAIL_DEFAULT_SENDER], body="Test message."))


if __name__ == '__main__':
    manager.run()
