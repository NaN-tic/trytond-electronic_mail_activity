# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import fields, ModelView
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction
from trytond.pyson import Eval, Bool
from email.utils import formataddr, formatdate, make_msgid, parseaddr
from email import encoders, message_from_bytes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import mimetypes
from trytond.modules.electronic_mail.electronic_mail import _make_header
import logging
import datetime
from trytond.i18n import gettext
from trytond.exceptions import UserError

try:
    from html2text import html2text
except ImportError:
    message = "Unable to import html2text and it's needed."
    logging.getLogger('MailObj').error(message)
    raise Exception(message)

__all__ = ['Activity', 'ActivityReplyMail']


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.method.selection.extend([
            ('activity.activity|create_activity', "Create Activity")])


class Activity(metaclass=PoolMeta):
    __name__ = 'activity.activity'

    mail = fields.Many2One('electronic.mail', "Related Mail", readonly=True,
            ondelete='CASCADE')
    have_mail = fields.Function(fields.Boolean('Have mail'), 'get_have_mail')
    #related_activity = fields.Many2One('activity.activity', 'Related activity',
    #    domain=[('id', 'in', Eval('resource.activities', []))], depends=['resource'])
    related_activity = fields.Many2One('activity.activity', 'Related activity')
    mail_content = fields.Function(fields.Binary('Mail Content', filename='filename'),
        'get_mail_content')
    filename = fields.Function(fields.Char("File Name"), 'get_filename')

    @classmethod
    def __setup__(cls):
        super(Activity, cls).__setup__()
        cls._buttons.update({
                'new': {
                    'icon': 'tryton-email',
                    },
                'reply': {
                    'icon': 'tryton-forward',
                    },
                'guess': {
                    'icon': 'tryton-forward',
                    'invisible': Bool(Eval('resource', -1)),
                    'depends': ['resource'],
                    },
            })

    @property
    def message_id(self):
        return self.mail and self.mail.message_id or make_msgid()

    @property
    def in_reply_to(self):
        return self.mail and self.mail.in_reply_to or (self.related_activity
            and self.related_activity.mail and
            self.related_activity.mail.message_id or "")

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['electronic.mail']

    @property
    def reference(self):
        result = ""
        if self.mail and self.mail.reference:
            result = self.mail.reference
        elif self.related_activity and self.related_activity.mail:
            if self.related_activity.mail.reference:
                result += self.related_activity.mail.reference or ""
            else:
                result += self.related_activity.mail.in_reply_to or ""
            result += self.related_activity.mail.message_id or ""
        return result

    @classmethod
    def get_have_mail(cls, activities, name):
        result = {}
        for activity in activities:
            result[activity.id] = activity.mail and True or False
        return result

    def get_mail_content(self, name):
        pool = Pool()
        ElectronicMail = pool.get('electronic.mail')
        if isinstance(self.origin, ElectronicMail):
            return self.origin.preview

    def get_filename(self, name):
        return 'mail-content.html'

    @classmethod
    @ModelView.button
    def new(cls, activities):
        user = cls.check_activity_user_info()
        if user:
            for activity in activities:
                if activity.mail and activity.mail.flag_received:
                    raise UserError(gettext(
                        'electronic_mail_activity.mail_received',
                            activity=activity.id))
                cls.send_mail(activity, user)

    @classmethod
    @ModelView.button_action('electronic_mail_activity.wizard_replymail')
    def reply(cls, activities):
        cls.check_activity_user_info()

    @classmethod
    @ModelView.button
    def guess(cls, activities):
        activities = cls.browse(sorted(activities, key=lambda x: x.id))
        for activity in activities:
            activity = cls(activity)
            activity.guess_resource()
            # Each activity is saved because in this list there
            # could be a resource of another of the same list
            activity.save()

    @classmethod
    def check_activity_user_info(cls):
        "Check if user have deffined the a server and a mailbox"
        User = Pool().get('res.user')
        user = User(Transaction().user)
        if user and user.smtp_server:
            if user.mailbox:
                return user
            raise UserError(gettext(
            'electronic_mail_activity.no_mailbox',user=user.name))
        else:
            raise UserError(gettext(
            'electronic_mail_activity.no_smtp_server',user=user.name))

    @classmethod
    def send_mail(cls, activity, user):
        """
        Send out the given email using the SMTP_CLIENT if configured in the
        Tryton Server configuration

        :param email_id: Browse record of the email to be sent
        :param server: Browse Record of the server
        :param type_: If the mail to send is new or a reply
        """
        ElectronicMail = Pool().get('electronic.mail')

        if activity.mail:
            mail = activity.mail
        else:
            # Prepare the mail strucuture
            mimetype_mail = activity.create_mimetype(user)
            # Create the mail
            mail = ElectronicMail.create_from_mail(mimetype_mail,
                user.mailbox, activity)
        if not mail:
            return

        # Before to send, control if all mails are corrects
        # If there are no user in main contact or in contacts, we creat And
        # activity for internal reason and we send the mail to the employee.
        emails = []
        email_to = activity.contacts and activity.contacts[0].email or activity.employee.party.email
        name_to = activity.contacts and activity.contacts[0].name or activity.employee.party.name
        emails_to = ElectronicMail.validate_emails(email_to)
        if emails_to:
            emails.append(emails_to)
        else:
            raise UserError(gettext(
                'electronic_mail_activity.no_valid_mail',
                    email=email_to, party=name_to))
        if activity.contacts:
            for c in activity.contacts:
                emails_cc = ElectronicMail.validate_emails(c.email)
                if emails_cc:
                    emails.append(emails_cc)
                else:
                    raise UserError(gettext(
                        'electronic_mail_activity.no_valid_mail',
                            email=activity.contacts[0].email,
                            party=activity.contacts[0].name))
        if user and user.smtp_server and user.smtp_server.smtp_email:
            emails.append(user.smtp_server.smtp_email)

        user.smtp_server.send_mail(mail.from_, emails, mail.mail_file)
        ElectronicMail.write([mail], {
                'flag_send': True,
                })
        cls.write([activity], {
                'mail': mail.id,
                })

        logging.getLogger('Activity Mail').info(
            'Send email %s from activity %s (to %s)' % (mail.id, activity.id,
                emails))

        return True

    def create_mimetype(self, user):
        '''Create a MIMEtype structure from activity values
        :param activity: Object of the activity to send mail
        :param type_: To know if it's a new mail or a reply
        :return: MIMEtype
        '''
        Attachment = Pool().get('ir.attachment')

        message = MIMEMultipart()
        message['Message-Id'] = self.message_id
        message['Date'] = formatdate(localtime=True)

        # If reply, take from the related activity the message_id and
        # reference information
        if self.related_activity:
            message['In-Reply-To'] = self.in_reply_to
            message['Reference'] = self.reference
        message['From'] = (self.employee and formataddr((
                    _make_header(self.employee.party.name),
                    self.employee.party.email)) or
            formataddr((user.employee.party.name, user.employee.party.email)))
        message['To'] = (self.contacts and formataddr((
                    _make_header(self.contacts[0].name),
                    self.contacts[0].email)) or
            formataddr((self.employee.party.name, self.employee.party.email)))
        message['Cc'] = ",".join([
                formataddr((_make_header(c.name), c.email))
                for c in self.contacts])
        message['Bcc'] = (user and user.smtp_server and
            user.smtp_server.smtp_email or "")
        message['Subject'] = _make_header(self.subject)
        plain = self.description.encode('utf-8')
        if user.add_signature and user.signature:
            signature = user.signature.encode('utf-8')
            plain = '%s\n--\n%s' % (plain, signature)
        message.attach(MIMEText(plain, 'plain', _charset='utf-8'))

        # Attach reports
        attachs = Attachment.search([
            ('resource', '=', str(self)),
            ])
        if attachs:
            for attach in attachs:
                filename = attach.name
                data = attach.data
                content_type, encoding = mimetypes.guess_type(filename)
                maintype, subtype = (
                    content_type or 'application/octet-stream'
                    ).split('/', 1)
                attachment = MIMEBase(maintype, subtype)
                attachment.set_payload(data)
                encoders.encode_base64(attachment)
                attachment.add_header(
                    'Content-Disposition', 'attachment', filename=filename)
                attachment.add_header(
                    'Content-Transfer-Encoding', 'base64')
                message.attach(attachment)
        return message

    @classmethod
    def get_contact_mechanism(cls, email, parties=None, active=True):
        """ Get party and contact_mechanism from email.
                With the possibility to restic some party list
                and to search for the non active parties
        """
        ContactMechanism = Pool().get('party.contact_mechanism')
        PartyRelation = Pool().get('party.relation')
        domain = [
            ('type', '=', 'email'),
            ('active', '=', active),
            ('value', '=', email),
            ]
        if parties:
            domain.append(
                ('party', 'in', parties),
                )
        contact_mechanisms = ContactMechanism.search(domain)
        if contact_mechanisms:
            if len(contact_mechanisms) == 1:
                return contact_mechanisms[0]
            contact_mechanisms_copy = contact_mechanisms[:]
            for contact_mechanism in contact_mechanisms:
                party_relation = PartyRelation.search([
                    ('from_', '=', contact_mechanism.party.id),
                    ])
                if party_relation:
                    contact_mechanisms_copy.remove(contact_mechanism)
            if not contact_mechanisms_copy or len(contact_mechanisms_copy) > 1:
                return contact_mechanisms[0]
            if len(contact_mechanisms_copy) == 1:
                return contact_mechanisms_copy[0]
        return None

    @classmethod
    def create_activity(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        ElectronicMail = pool.get('electronic.mail')
        Activity = pool.get('activity.activity')
        ActivityType = pool.get('activity.type')
        ActivityConfiguration = pool.get('activity.configuration')
        Attachment = pool.get('ir.attachment')

        mails = ElectronicMail.search([
                    ('mailbox', '=', ActivityConfiguration(0).pending_mailbox)
                    ], order=[('date', 'ASC'), ('id', 'ASC')])
        activity_type = ActivityType(ModelData.get_id('activity',
                'incoming_email_type'))

        employee = ActivityConfiguration(0).employee
        processed_mailbox = ActivityConfiguration(0).processed_mailbox
        activities = []
        activity_attachments = []
        for mail in mails:
            activity = Activity()
            if mail.subject:
                activity.subject = mail.subject.replace('\r', '')
            activity.activity_type = activity_type
            activity.employee = employee
            activity.dtstart = mail.date
            if mail.body_plain:
                description = mail.body_plain
            elif mail.body_html:
                description = html2text(mail.body_html)
            else:
                description = None
            if description:
                activity.description = description.replace('\r', '').replace(
                    '<br/>', '\n')
            activity.mail = mail
            activity.state = 'planned'

            activity.resource = None
            activity.origin = mail

            if mail.mail_file:
                msg = message_from_bytes(mail.mail_file)
                attachments = []
                for attachment in ElectronicMail.get_attachments(msg):
                    attachments.append(Attachment(
                        name = attachment.get('filename', mail.subject),
                        type = 'data',
                        data = attachment.get('data')))
                activity_attachments.append(attachments)
            activities.append(activity)
            mail.mailbox = processed_mailbox

        if activities:
            cls.save(activities)
            to_save = []
            for activity, attachments in zip(activities, activity_attachments):
                for attachment in attachments:
                    attachment.name = attachment.name.replace(
                        '\n','').replace('\r', '')
                    attachment.resource = str(activity)
                to_save += attachments
            Attachment.save(to_save)
            ElectronicMail.save(mails)
            cls.guess(activities)

    def get_previous_activity(self):
        ElectronicMail = Pool().get('electronic.mail')
        if not isinstance(self.origin, ElectronicMail):
            return
        parent = self.origin.parent
        if not parent:
            return
        activities = self.search([
                ('origin', '=', parent)
                ], limit=1)
        if activities:
            return activities[0]

    @classmethod
    def emails_to_reject(cls):
        pool = Pool()
        Employee = pool.get('company.employee')
        Company = pool.get('company.company')
        ContactMechanism = pool.get('party.contact_mechanism')
        User = pool.get('res.user')

        employees = Employee.search([])
        parties = [x.party for x in employees]
        parties += [x.party for x in Company.search([])]
        contact_mechanisms = ContactMechanism.search([
                ('type', '=', 'email'),
                ('party', 'in', parties)
                ])
        mails = [x.value.lower() for x in contact_mechanisms]
        return set(mails)

    def guess_resource(self):
        pool = Pool()
        ElectronicMail = pool.get('electronic.mail')
        Activity = pool.get('activity.activity')
        Party = pool.get('party.party')

        previous_activity = self.get_previous_activity()
        if previous_activity:
            if previous_activity.resource:
                self.resource = previous_activity.resource
                self.party = previous_activity.resource.party
                if not self.party:
                    self.party = self.on_change_with_party()
        elif self.origin and isinstance(self.origin, ElectronicMail):
            # parseaddr return first email
            _, email_from = parseaddr(self.origin.from_)
            _, email_to = parseaddr(self.origin.to)
            rejected_emails = self.emails_to_reject()
            addresses = [x for x in (email_from, email_to)
                if x not in rejected_emails and x != '']
            if not addresses:
                return

            email = addresses[0]
            activities = Activity.search([
                ('party', '!=', None),
                ['OR',
                    [
                        ('origin.from_', 'ilike', '%' + email + '%',
                            'electronic.mail'),
                    ], [
                        ('origin.to', 'ilike', '%' + email + '%',
                            'electronic.mail'),
                    ],
                ],
                ], limit=1, order=[('dtstart', 'DESC')])
            if activities:
                self.party = activities[0].party
                return

            parties = Party.search([
                ('contact_mechanisms.value', 'ilike', email),
                ], limit=1)
            if parties:
                self.party = parties[0]


class ActivityReplyMail(Wizard, metaclass=PoolMeta):
    'Activity Reply Mail'
    __name__ = 'activity.activity.replymail'
    start_state = 'open_'
    open_ = StateAction('activity.act_activity_activity')

    def do_open_(self, action):
        Activity = Pool().get('activity.activity')

        activities = Activity.browse([Transaction().context['active_id']])
        re = "Re: "
        return_activities = []
        for activity in activities:
            return_activity = Activity.copy([activity])[0]
            if return_activity.subject[:3].lower() != re[:3].lower():
                return_activity.subject = "%s%s" % (re, return_activity.subject)
            return_activity.direction = 'outgoing'
            return_activity.dtstart = datetime.datetime.now()
            return_activity.mail = None
            return_activity.description = '\n'.join("> %s" % l.strip()
                for l in return_activity.description.split('\n'))
            return_activity.related_activity = activity.id
            return_activity.save()
            return_activities.append(return_activity.id)

        data = {'res_id': return_activities}
        if len(return_activities) == 1:
            action['views'].reverse()
        return action, data
