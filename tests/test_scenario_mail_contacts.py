import datetime
import unittest
from email.message import EmailMessage

from proteus import Model
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules, set_user


class TestMailContacts(unittest.TestCase):
    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        config = activate_modules('electronic_mail_activity')
        create_company()
        company = get_company()
        Party = Model.get('party.party')
        Employee = Model.get('company.employee')
        User = Model.get('res.user')
        Activity = Model.get('activity.activity')
        ActivityType = Model.get('activity.type')
        Mail = Model.get('electronic.mail')
        Mailbox = Model.get('electronic.mail.mailbox')
        RelationType = Model.get('party.relation.type')
        Relation = Model.get('party.relation.all')
        employee_party = Party(name='Employee')
        employee_party.contact_mechanisms.new(
            type='email', value='staff@internal.example')
        employee_party.save()
        employee = Employee(party=employee_party, company=company)
        employee.save()
        company.party.contact_mechanisms.new(
            type='email', value='support@internal.example')
        company.party.save()
        user = User(config.user)
        user.companies.append(company)
        user.company = company
        user.employees.append(employee)
        user.employee = employee
        user.save()
        set_user(user)
        customer = Party(name='Customer')
        customer.save()
        relation_type = RelationType(name='Has Contact')
        relation_type.save()
        contacts = []
        for name, emails in [
                ('Sender', ['primary@example.com', 'sender@example.com']),
                ('Copy', ['copy@example.com']),
                ('Signature', ['signature@example.com'])]:
            contact = Party(name=name)
            for address in emails:
                contact.contact_mechanisms.new(type='email', value=address)
            contact.save()
            Relation(from_=customer, to=contact, type=relation_type).save()
            contacts.append(contact)
        activity_type = ActivityType(name='Incoming Mail')
        activity_type.save()
        mailbox = Mailbox(name='Inbox')
        mailbox.save()
        header = ('---------- Forwarded message ---------\n'
            'De: Sender <SENDER@example.com>\nDate: Wednesday\n'
            'Subject: Original request\nTo: staff@internal.example\n'
            'Cc: Copy <copy@example.com>\n\n')
        for mode in ['direct', 'plain', 'html', 'nested', 'internal']:
            with self.subTest(mode=mode):
                message = EmailMessage()
                message['From'] = ('sender@example.com' if mode == 'direct'
                    else 'staff@internal.example')
                message['To'] = 'support@internal.example'
                message['Subject'] = 'Customer request'
                if mode == 'direct':
                    message['Cc'] = 'copy@example.com, sender@example.com'
                body = header + 'Reply\nSignature signature@example.com'
                if mode == 'internal':
                    body = 'Mention sender@example.com in ordinary text'
                elif mode == 'nested':
                    body = ('---------- Forwarded message ---------\n'
                        'From: staff@internal.example\n'
                        'To: support@internal.example\n\n' + body)
                if mode == 'html':
                    body = body.replace('<', '&lt;').replace('>', '&gt;')
                    body = '<div>' + body.replace('\n', '<br>') + '</div>'
                message.set_content(body,
                    subtype='html' if mode == 'html' else 'plain',
                    cte='quoted-printable')
                mail = Mail(mailbox=mailbox, from_=str(message['From']),
                    to=str(message['To']), cc=str(message.get('Cc', '')),
                    subject=str(message['Subject']),
                    date=datetime.datetime.now(), mail_file=message.as_bytes())
                mail.save()
                activity = Activity(activity_type=activity_type,
                    employee=employee, party=customer, origin=mail, mail=mail,
                    dtstart=mail.date, state='planned')
                activity.save()
                self.assertFalse(activity.contacts)
                activity.click('guess')
                self.assertEqual([c.party for c in activity.contacts],
                    [] if mode == 'internal' else contacts[:2])
                activity.click('guess')
                self.assertEqual(len(activity.contacts),
                    0 if mode == 'internal' else 2)
