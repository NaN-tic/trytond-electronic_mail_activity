# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .activity import *
from .imap import *

def register():
    Pool.register(
        Activity,
        IMAPServer,
        module='electronic_mail_activity', type_='model')
