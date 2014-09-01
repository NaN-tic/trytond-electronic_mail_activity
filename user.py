# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['User']
__metaclass__ = PoolMeta


class User:
    __name__ = "res.user"

    smtp_server = fields.Many2One('smtp.server', 'SMTP Server',
        domain=[('state', '=', 'done')])
    mailbox = fields.Many2One('electronic.mail.mailbox', 'Mailbox')
