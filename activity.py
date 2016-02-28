# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import fields, ModelView
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction
from email.utils import parseaddr, formataddr, formatdate, make_msgid
from email import Encoders
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import mimetypes
from trytond.modules.electronic_mail.electronic_mail import _make_header,\
    msg_from_string
import logging
import datetime
try:
    from html2text import html2text
except ImportError:
    message = "Unable to import html2text and it's needed."
    logging.getLogger('MailObj').error(message)
    raise Exception(message)

__all__ = ['Activity', 'ActivityReplyMail']
__metaclass__ = PoolMeta


class Activity:
    __name__ = 'activity.activity'

    mail = fields.Many2One('electronic.mail', "Related Mail", readonly=True,
            ondelete='CASCADE')
    have_mail = fields.Function(fields.Boolean('Have mail'), 'get_have_mail')
    #related_activity = fields.Many2One('activity.activity', 'Related activity',
    #    domain=[('id', 'in', Eval('resource.activities', []))], depends=['resource'])
    related_activity = fields.Many2One('activity.activity', 'Related activity')

    @classmethod
    def __setup__(cls):
        super(Activity, cls).__setup__()
        cls._error_messages.update({
                'mail_received': ('The activity (id: "%s") is a mail received '
                    'so you ca not send.'),
                'no_smtp_server': ('The user "%s", do not have the SMTP '
                    'server deffined. Without it, it is no possible to send '
                    'mails.'),
                'no_mailbox': ('The user "%s", do not have the mailbox '
                    'server deffined. Without it, it is no possible to send '
                    'mails.'),
                'no_valid_mail': ('The "%s" of the party "%s" it is not '
                    'correct.'),
                })
        cls._buttons.update({
            'new': {},
            'reply': {},
            })

    @property
    def message_id(self):
        return self.mail and self.mail.message_id or make_msgid()

    @property
    def in_reply_to(self):
        return self.mail and self.mail.in_reply_to or (self.related_activity
            and self.related_activity.mail and
            self.related_activity.mail.message_id or "")

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
    def get_have_mail(self, activities, name):
        result = {}
        for activity in activities:
            result[activity.id] = activity.mail and True or False
        return result

    @classmethod
    @ModelView.button
    def new(cls, activities):
        user = cls.check_activity_user_info()
        if user:
            for activity in activities:
                if activity.mail and activity.mail.flag_received:
                    cls.raise_user_error('mail_received', activity.id)
                cls.send_mail(activity, user)

    @classmethod
    @ModelView.button_action('electronic_mail_activity.wizard_replymail')
    def reply(cls, activities):
        cls.check_activity_user_info()

    @classmethod
    def check_activity_user_info(cls):
        "Check if user have deffined the a server and a mailbox"
        User = Pool().get('res.user')
        user = User(Transaction().user)
        if user and user.smtp_server:
            if user.mailbox:
                return user
            cls.raise_user_error('no_mailbox', user.name)
        else:
            cls.raise_user_error('no_smtp_server', user.name)

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
        SMTP = Pool().get('smtp.server')

        if activity.mail:
            mail = activity.mail
        else:
            # Prepare the mail strucuture
            mimetype_mail = activity.create_mimetype(user)
            # Create the mail
            mail = ElectronicMail.create_from_mail(mimetype_mail,
                user.mailbox)

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
            cls.raise_user_error('no_valid_mail', (email_to, name_to))
        if activity.contacts:
            for c in activity.contacts:
                emails_cc = ElectronicMail.validate_emails(c.email)
                if emails_cc:
                    emails.append(emails_cc)
                else:
                    cls.raise_user_error('no_valid_mail',
                        (activity.contacts[0].email,
                            activity.contacts[0].name))
        if user and user.smtp_server and user.smtp_server.smtp_email:
            emails.append(user.smtp_server.smtp_email)

        # Send the mail
        # TODO: Create a send_mail function in SMTP module to control there
        # the possible errors. The "electronic_mail_template/template.py" will
        # use it to. And other possible modules will have a function.
        #   SMTP.send_mail(server, from, cc, email)
        # This method (sendmail in the smtplib) may raise the following
        # exceptions:
        # SMTPRecipientsRefused
        #     All recipients were refused. Nobody got the mail. The recipients
        #       attribute of the exception object is a dictionary with
        #       information about the refused recipients (like the one returned
        #       when at least one recipient was accepted).
        # SMTPHeloError
        #     The server did not reply properly to the HELO greeting.
        # SMTPSenderRefused
        #     The server did not accept the from_addr.
        # SMTPDataError
        #     The server replied with an unexpected error code (other than a
        #       refusal of a recipient).
        try:
            server = SMTP.get_smtp_server(user.smtp_server)
            mail_str = ElectronicMail._get_mail(mail)
            server.sendmail(mail.from_, emails, mail_str)
            server.quit()
            ElectronicMail.write([mail], {
                    'flag_send': True,
                    })
            cls.write([activity], {
                    'mail': mail.id,
                    })
        except:
            cls.raise_user_error('smtp_error')

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
                Encoders.encode_base64(attachment)
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
            contact_mechanisms_copy = contact_mechanisms
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
    def create_activity(cls, received_mails):
        IMAPServer = Pool().get('imap.server')
        CompanyEmployee = Pool().get('company.employee')
        ElectronicMail = Pool().get('electronic.mail')
        Attachment = Pool().get('ir.attachment')
        ActivityType = Pool().get('activity.type')

        values = []
        attachs = {}
        for server_id, mails in received_mails.iteritems():
            servers = IMAPServer.browse([server_id])
            server = servers and servers[0] or None
            for mail in mails:
                # Control if the mail recevied is send by us, searching if
                # there are any activity with that mail attached
                activity_exist = cls.search([
                    ('mail', '=', mail.id)
                    ])
                if activity_exist:
                    continue
                # Take the possible employee, if not the default.
                deliveredtos = mail.deliveredto and [mail.deliveredto] or []
                deliveredtos.extend([m[1] for m in mail.all_to])
                deliveredtos.extend([m[1] for m in mail.all_cc])
                deliveredtos = ElectronicMail.validate_emails(deliveredtos)
                contact = None
                if deliveredtos:
                    employees = CompanyEmployee.search([])
                    parties = [p.party.id for p in employees]
                    contacts = []
                    for deliveredto in deliveredtos:
                        cm = cls.get_contact_mechanism(deliveredto, parties)
                        if cm:
                            contacts.append(cm)
                    contact = contacts and contacts[0] or None
                employee = None
                if contact:
                    emails_employee = [c.value
                        for c in contact.party.contact_mechanisms
                        if c.type == 'email']
                    employee = CompanyEmployee.search([
                        ('party', '=', contact.party.id)
                        ])
                if not employee:
                    employee = server and server.employee or None
                    emails_employee = (server and server.employee and
                        [server.employee.party.email] or [])
                else:
                    employee = employee[0]

                # Search for the parties with that mails, to attach in the
                # contacts and main contact
                mail_from = ElectronicMail.validate_emails(
                    parseaddr(mail.from_.replace(',', ' '))[1])
                contact = cls.get_contact_mechanism(mail_from)
                main_contact = contact and contact.party or False

                email_to = []
                for to in mail.all_to:
                    if to[1] not in emails_employee:
                        email_to.append(to[1])
                email_cc = email_to + [m[1] for m in mail.all_cc]
                emails_cc = ElectronicMail.validate_emails(email_cc)
                contacts = []
                for email_cc in emails_cc:
                    contact = cls.get_contact_mechanism(email_cc)
                    if contact:
                        contacts.append(contact.party.id)

                # Search for the possible activity referenced to add in the
                # same resource.
                referenced_mail = []
                if mail.in_reply_to:
                    referenced_mail = ElectronicMail.search([
                        ('message_id', '=', mail.in_reply_to)
                        ])
                if not referenced_mail and mail.reference:
                    referenced_mail = ElectronicMail.search([
                        ('message_id', 'in', mail.reference)
                        ])

                # Fill the fields, in case the activity don't have enought
                # information
                resource = None
                party = (main_contact and
                    [r.to for r in main_contact.relations] or [])
                party = party and party[0] or None
                if referenced_mail:
                    # Search if the activity have resource to use for activity
                    # that create now.
                    referenced_mails = [r.id for r in referenced_mail]
                    activities = cls.search([
                        ('mail', 'in', referenced_mails)
                        ])
                    if activities:
                        resource = activities[0].resource
                        party = resource and resource.party or party

                # TODO: Search for a better default.
                # By the moment search the first activity type with the 0 in
                # sequence
                activity_types = ActivityType.search([
                    ('sequence', '=', 0)
                    ])
                activity_type = activity_types and activity_types[0] or None

                # Create the activity
                base_values = {
                    'subject': mail.subject or "NONE",
                    'activity_type': activity_type,
                    'employee': employee.id,
                    'dtstart': datetime.datetime.now(),
                    'description': (mail.body_plain
                        or html2text(mail.body_html)),
                    'mail': mail.id,
                    'state': 'planned',
                    'resource': None,
                    }
                values = base_values.copy()
                if resource:
                    values['resource'] = str(resource)
                if party:
                    values['party'] = party.id
                if main_contact:
                    values['main_contact'] = main_contact.id
                if contacts:
                    values['contacts'] = [('add', contacts)]
                try:
                    activity = cls.create([values])
                except:
                    activity = cls.create([base_values])

                # Add all the possible attachments from the mil to the activity
                msg = msg_from_string(mail.mail_file)
                attachs = ElectronicMail.get_attachments(msg)
                if attachs:
                    values = []
                    for attach in attachs:
                        values.append({
                                'name': attach.get('filename', mail.subject),
                                'type': 'data',
                                'data': attach.get('data'),
                                'resource': str(activity[0])
                                })
                    try:
                        Attachment.create(values)
                    except Exception, e:
                        logging.getLogger('Activity Mail').info(
                            'The mail (%s) has attachments but they are not '
                            'possible to attach to the activity (%s).\n\n%s' %
                            (mail.id, activity.id, e))
        return mails


class ActivityReplyMail(Wizard):
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
