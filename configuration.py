from trytond.pool import Pool, PoolMeta
from trytond.model import fields, ModelView


__all__ = ['Configuration']


class Configuration(metaclass=PoolMeta):
    'Activity Configuration'
    __name__ = 'activity.configuration'

    employee = fields.Many2One('company.employee', 'Employee', required=True)
    pending_mailbox = fields.Many2One('electronic.mail.mailbox', 'Pending Mailbox',
            required=True)
    processed_mailbox = fields.Many2One('electronic.mail.mailbox', 'Processed Mailbox',
            required=True)