# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from types import SimpleNamespace

from trytond.modules.company.tests import (
    CompanyTestMixin, create_company, create_employee, set_company)
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class ElectronicMailActivityTestCase(CompanyTestMixin, ModuleTestCase):
    'Test ElectronicMailActivity module'
    module = 'electronic_mail_activity'

    def _create_user(self):
        return SimpleNamespace(
            employee=SimpleNamespace(
                party=SimpleNamespace(
                    name='Sender User',
                    email='sender@example.com',
                    )),
            smtp_server=SimpleNamespace(smtp_email='bcc@example.com'),
            add_signature=False,
            signature='',
            )

    def _create_mail(self, mailbox, message_id, references=None,
            in_reply_to=None):
        pool = Pool()
        Mail = pool.get('electronic.mail')

        message = MIMEMultipart('alternative')
        message['Date'] = formatdate()
        message['Subject'] = 'Parent'
        message['From'] = 'source@example.com'
        message['To'] = 'recipient@example.com'
        message['Message-ID'] = message_id
        if references:
            message['References'] = references
        if in_reply_to:
            message['In-Reply-To'] = in_reply_to
        message.attach(MIMEText('Body', 'plain'))
        return Mail.create_from_mail(message, mailbox)

    def _create_activity(self, Activity, ActivityType, employee, **kwargs):
        activity_type, = ActivityType.create([{
                    'name': 'Mail',
                    }])
        values = {
            'activity_type': activity_type.id,
            'employee': employee.id,
            'date': datetime.date.today(),
            'dtstart': datetime.datetime.now(),
            'state': 'planned',
            'subject': 'Activity',
            }
        values.update(kwargs)
        activity, = Activity.create([values])
        return activity

    @with_transaction()
    def test_activity_thread_headers_from_previous_references(self):
        pool = Pool()
        Activity = pool.get('activity.activity')
        ActivityType = pool.get('activity.type')
        Mailbox = pool.get('electronic.mail.mailbox')

        company = create_company()
        with set_company(company):
            employee = create_employee(company, 'Receiver')
            employee.party.email = 'recipient@example.com'
            employee.party.save()
            mailbox, = Mailbox.create([{'name': 'Mailbox'}])
            parent_mail = self._create_mail(
                mailbox,
                '<parent@example.com>',
                references='<root@example.com>')
            parent_activity = self._create_activity(
                Activity, ActivityType, employee, mail=parent_mail.id)
            reply_activity = self._create_activity(
                Activity, ActivityType, employee,
                related_activity=parent_activity.id)

            self.assertEqual(parent_activity.in_reply_to, '<parent@example.com>')
            self.assertEqual(
                parent_activity.references,
                '<root@example.com> <parent@example.com>')
            self.assertEqual(reply_activity.in_reply_to, '<parent@example.com>')
            self.assertEqual(
                reply_activity.references,
                '<root@example.com> <parent@example.com>')
            self.assertEqual(
                reply_activity.original_mail_message_id,
                '<parent@example.com>')

            mime_message = reply_activity.create_mime_message(
                self._create_user())

            self.assertEqual(
                mime_message['In-Reply-To'], '<parent@example.com>')
            self.assertEqual(
                mime_message['References'],
                '<root@example.com> <parent@example.com>')

    @with_transaction()
    def test_activity_thread_headers_from_previous_in_reply_to(self):
        pool = Pool()
        Activity = pool.get('activity.activity')
        ActivityType = pool.get('activity.type')
        Mailbox = pool.get('electronic.mail.mailbox')

        company = create_company()
        with set_company(company):
            employee = create_employee(company, 'Receiver')
            employee.party.email = 'recipient@example.com'
            employee.party.save()
            mailbox, = Mailbox.create([{'name': 'Mailbox'}])
            parent_mail = self._create_mail(
                mailbox,
                '<parent@example.com>',
                in_reply_to='<root@example.com>')
            parent_activity = self._create_activity(
                Activity, ActivityType, employee, mail=parent_mail.id)
            reply_activity = self._create_activity(
                Activity, ActivityType, employee,
                related_activity=parent_activity.id)

            self.assertEqual(parent_activity.in_reply_to, '<parent@example.com>')
            self.assertEqual(
                parent_activity.references,
                '<root@example.com> <parent@example.com>')
            self.assertEqual(reply_activity.in_reply_to, '<parent@example.com>')
            self.assertEqual(
                reply_activity.references,
                '<root@example.com> <parent@example.com>')

            mime_message = reply_activity.create_mime_message(
                self._create_user())

            self.assertEqual(
                mime_message['In-Reply-To'], '<parent@example.com>')
            self.assertEqual(
                mime_message['References'],
                '<root@example.com> <parent@example.com>')


del ModuleTestCase
