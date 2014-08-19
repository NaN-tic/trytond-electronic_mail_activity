# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView

__all__ = ['IMAPServer']
__metaclass__ = PoolMeta


class IMAPServer:
    __name__ = 'imap.server'

    @classmethod
    @ModelView.button
    def get_emails(cls, servers):
        for server in servers:
            if server.model and server.model == 'activity.activity':
                Activity = Pool().get('activity.activity')
                mails = Activity.create_activity(servers)
            else:
                mails = super(IMAPServer, cls).get_emails(servers)
        return mails
