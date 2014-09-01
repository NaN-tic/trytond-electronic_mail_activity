# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .activity import *
from .imap import *
from .user import *

def register():
    Pool.register(
        Activity,
        IMAPServer,
        User,
        module='electronic_mail_activity', type_='model')
    Pool.register(
        ActivityReplyMail,
        module='electronic_mail_activity', type_='wizard')
