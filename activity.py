# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import fields

__all__ = ['Activity']
__metaclass__ = PoolMeta


class Activity:
    __name__ = 'activity.activity'

    mail = fields.Many2One('electronic.mail', "Related Mail")

    @classmethod
    def create_activity(cls, servers):
        mails = {}
        IMAP = Pool().get('imap.server')
        activity_servers = IMAP.search([
            ('state', '=', 'done'),
            ('model', '=', 'activity.activity')
            ], order =[])
        if not servers:
            servers = activity_servers
        mails = IMAP.get_emails(servers)

    #    for mail in mails:
    #        mail.subject
    #        mail.to
    #        mail.from_
    #        mail.cc
    #        mail.body_plain

    #        mail.deliveredto
    #        mail.reference
    #        mail.reply_to
    #        mail.in_reply_to
    #        mail.message_id
    #        mail.cc
        return mails
