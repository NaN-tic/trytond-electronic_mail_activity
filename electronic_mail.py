# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from email import message_from_bytes
from trytond.config import config
from trytond.pool import Pool, PoolMeta
from trytond.modules.widgets import tools

QUEUE_NAME = config.get('electronic_mail', 'queue_name', default='default')


class ElectronicMail(metaclass=PoolMeta):
    __name__ = 'electronic.mail'

    @classmethod
    def _create_activity(cls, mails):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Activity = pool.get('activity.activity')
        ActivityType = pool.get('activity.type')
        ActivityConfiguration = pool.get('activity.configuration')
        Attachment = pool.get('ir.attachment')

        config = ActivityConfiguration(1)
        employee = config.employee
        processed_mailbox = config.processed_mailbox

        activity_type = ActivityType(ModelData.get_id('activity',
                'incoming_email_type'))

        activities = []
        activity_attachments = []
        for mail in mails:
            if mail.mailbox == processed_mailbox:
                continue
            activity = Activity()
            if mail.subject:
                activity.subject = mail.subject.replace('\r', '')
            activity.activity_type = activity_type
            activity.employee = employee
            activity.dtstart = mail.date
            if mail.body_plain:
                activity.description = tools.text_to_js(mail.body_plain)
            elif mail.body_html:
                activity.description = tools.html_to_js(mail.body_html)
            activity.mail = mail
            activity.state = 'planned'

            activity.resource = None
            activity.origin = mail

            if mail.mail_file:
                msg = message_from_bytes(mail.mail_file)
                attachments = []
                for attachment in cls.get_attachments(msg):
                    attachments.append(Attachment(
                        name = attachment.get('filename', mail.subject),
                        type = 'data',
                        data = attachment.get('data')))
                activity_attachments.append(attachments)
            activities.append(activity)

        if activities:
            Activity.save(activities)
            to_save = []
            for activity, attachments in zip(activities, activity_attachments):
                for attachment in attachments:
                    attachment.name = attachment.name.replace(
                        '\n','').replace('\r', '')
                    attachment.resource = str(activity)
                to_save += attachments
            Attachment.save(to_save)
            Activity.guess(activities)

        # mails to processed mailbox
        cls.write(mails, {'mailbox': processed_mailbox})
