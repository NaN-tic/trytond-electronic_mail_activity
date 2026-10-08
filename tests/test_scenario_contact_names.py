import datetime
import unittest
from email.message import EmailMessage

from proteus import Model
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.pool import Pool
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules, set_user
from trytond.transaction import Transaction


class TestContactNames(unittest.TestCase):
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
        Type = Model.get('activity.type')
        Mail = Model.get('electronic.mail')
        Mailbox = Model.get('electronic.mail.mailbox')
        Relation = Model.get('party.relation.all')
        RelationType = Model.get('party.relation.type')
        staff = Party(name='Example Employee')
        staff.contact_mechanisms.new(type='email', value='staff@internal.example')
        staff.save()
        employee = Employee(party=staff, company=company)
        employee.save()
        user = User(config.user)
        user.companies.append(company)
        user.company = company
        user.employees.append(employee)
        user.employee = employee
        user.save()
        set_user(user)
        kind = Type(name='Email')
        kind.save()
        mailbox = Mailbox(name='Inbox')
        mailbox.save()
        relation_type = RelationType(name='Has Contact')
        relation_type.save()
        customer = Party(name='Example Workshop Ltd')
        customer.contact_mechanisms.new(type='email', value='shared@client.example')
        customer.save()
        people = []
        for name in ['Élia Sun North', 'Elia Sun South', 'Nora Vale']:
            person = Party(name=name)
            person.contact_mechanisms.new(type='email', value='shared@client.example')
            person.save()
            Relation(from_=customer, to=person, type=relation_type).save()
            people.append(person)
        outsider = Party(name='Outside Person')
        outsider.contact_mechanisms.new(type='email', value='shared@client.example')
        outsider.save()

        cases = [
            ('  ELIA   SUN NORTH  ', people[0], 'direct'),
            ('Nora Vale | Example Workshop Ltd', people[2], 'direct'),
            ('Nora Vale Additional', people[2], 'direct'),
            ('Elia Sun', None, 'direct'),
            ('Nora', None, 'direct'),
            ('', None, 'direct'),
            ('Different Person', None, 'direct'),
            ('Outside Person', None, 'direct'),
            ('Example Workshop Ltd', None, 'direct'),
            ('Nora Vale', people[2], 'reply_to'),
            ('Nora Vale', people[2], 'forwarded'),
            ]
        for name, expected, mode in cases:
            with self.subTest(name=name, mode=mode):
                author = ('"%s" <shared@client.example>' % name
                    if name else 'shared@client.example')
                message = EmailMessage()
                message['From'] = author if mode == 'direct' else 'staff@internal.example'
                message['To'] = 'staff@internal.example'
                message['Subject'] = 'Example request'
                body = 'Message'
                if mode == 'reply_to':
                    message['Reply-To'] = author
                elif mode == 'forwarded':
                    body = ('---------- Forwarded message ---------\n'
                        'From: %s\nTo: staff@internal.example\n'
                        'Subject: Request\n\nMessage' % author)
                message.set_content(body)
                mail = Mail(mailbox=mailbox, from_=str(message['From']),
                    to=str(message['To']), reply_to=str(message.get('Reply-To', '')),
                    subject=message['Subject'], date=datetime.datetime.now(),
                    mail_file=message.as_bytes())
                mail.save()
                activity = Activity(activity_type=kind, employee=employee,
                    party=customer, origin=mail, dtstart=mail.date)
                activity.save()
                activity.click('guess')
                self.assertEqual([c.party for c in activity.contacts],
                    [expected] if expected else [])
                activity.click('guess')
                self.assertEqual(len(activity.contacts), 1 if expected else 0)
                with Transaction().start(config.database_name, config.user,
                        readonly=True, context=config.context):
                    record = Pool().get('activity.activity')(activity.id)
                    raw = record.get_mail_contacts(record.get_mail_participants())
                    self.assertEqual(len(raw['shared@client.example']), 5)

        # An exact match wins over longer names, even when they share a prefix.
        exact = Party(name='Elia Sun')
        exact.contact_mechanisms.new(type='email', value='shared@client.example')
        exact.save()
        Relation(from_=customer, to=exact, type=relation_type).save()
        mail = Mail(mailbox=mailbox, from_='Elia Sun <shared@client.example>',
            to='staff@internal.example', date=datetime.datetime.now())
        mail.save()
        activity = Activity(activity_type=kind, employee=employee,
            party=customer, origin=mail, dtstart=mail.date)
        activity.save()
        activity.click('guess')
        self.assertEqual([c.party for c in activity.contacts], [exact])
