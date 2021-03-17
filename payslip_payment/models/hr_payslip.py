# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools import float_compare

import logging
_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip', 'mail.thread']

    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
        ('paid', 'Paid'),
        ('cancel', 'Rejected'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft',
        help="""* When the payslip is created the status is \'Draft\'
                \n* If the payslip is under verification, the status is \'Waiting\'.
                \n* If the payslip is confirmed then status is set to \'Done\'.
                \n* When user cancel payslip the status is \'Rejected\'.""", track_visibility='onchange')
    total_amount = fields.Float(string='Total Amount', compute='compute_total_amount', store=True)

    @api.depends('line_ids')
    @api.onchange('line_ids')
    def compute_total_amount(self):
        for slip in self:
            total_amount_new = 0.0
            for line in slip.line_ids:
                if line.salary_rule_id.code == 'NET':
                    total_amount_new+=line.total
            slip.total_amount = total_amount_new

    def set_to_paid(self):
        self.write({'state': 'paid'})


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('paid', 'Paid'),
        ('close', 'Close'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft')
    total_amount = fields.Float(string='Total Amount', compute='compute_total_amount')

    def batch_wise_payslip_confirm(self):
        for record in self.slip_ids:
            if record.state == 'draft':
                record.action_payslip_done()
        self.state = 'done'


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    payslip_id = fields.Many2one('hr.payslip', string='Expense', copy=False, help="Expense where the move line come from")

    def reconcile(self, writeoff_acc_id=False, writeoff_journal_id=False):
        res = super(AccountMoveLine, self).reconcile(writeoff_acc_id=writeoff_acc_id, writeoff_journal_id=writeoff_journal_id)
        account_move_ids = [
            l.move_id.id for l in self
            if float_compare(l.move_id._get_cash_basis_matched_percentage(), 1, precision_digits=5) == 0
        ]
        if account_move_ids:
            payslip = self.env['hr.payslip'].search([
                ('move_id', 'in', account_move_ids), ('state', '=', 'done')
            ])
            payslip.set_to_paid()
        return res
