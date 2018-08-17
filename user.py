# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['User']


class User(metaclass=PoolMeta):
    __name__ = "res.user"

    smtp_server = fields.Many2One('smtp.server', 'SMTP Server',
        domain=[('state', '=', 'done')])
    mailbox = fields.Many2One('electronic.mail.mailbox', 'Mailbox')
    add_signature = fields.Boolean('Use Signature', help='The Plain signature '
        'from the User details will be appened to the mail.')
