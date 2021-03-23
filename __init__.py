# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import activity
from . import configuration
from . import user

def register():
    Pool.register(
        activity.Activity,
        activity.Cron,
        user.User,
        configuration.Configuration,
        module='electronic_mail_activity', type_='model')
    Pool.register(
        activity.ActivityReplyMail,
        module='electronic_mail_activity', type_='wizard')
