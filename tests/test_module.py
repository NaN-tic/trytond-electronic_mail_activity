
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class ElectronicMailActivityTestCase(CompanyTestMixin, ModuleTestCase):
    'Test ElectronicMailActivity module'
    module = 'electronic_mail_activity'

    @with_transaction()
    def test_cron_create_activity_needs_company(self):
        "Create activity cron needs a company"
        Cron = Pool().get('ir.cron')

        self.assertIn(
            'activity.activity|create_activity',
            Cron.methods_company_needed)


del ModuleTestCase
