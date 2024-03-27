# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import activity
from . import electronic_mail
from . import configuration
from . import user

def register():
    Pool.register(
        activity.Activity,
        activity.Cron,
        electronic_mail.ElectronicMail,
        user.User,
        configuration.Configuration,
        activity.ActivityType,
        module='electronic_mail_activity', type_='model')
    Pool.register(
        activity.ActivityReplyMail,
        module='electronic_mail_activity', type_='wizard')
