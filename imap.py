# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import fields

__all__ = ['IMAPServer']
__metaclass__ = PoolMeta


class IMAPServer:
    __name__ = 'imap.server'

    employee = fields.Many2One('company.employee', 'Default Employee')

    @classmethod
    def fetch_mails(cls, servers):
        Activity = Pool().get('activity.activity')
        activity_servers = []
        other_servers = []
        for server in servers:
            if server.model and server.model.model == 'activity.activity':
                activity_servers.append(server)
            else:
                other_servers.append(server)
        mails = {}
        if activity_servers:
            mails.update(super(IMAPServer, cls).fetch_mails(activity_servers))
            Activity.create_activity(mails)
        if other_servers:
            mails.update(super(IMAPServer, cls).fetch_mails(other_servers))
        return mails
