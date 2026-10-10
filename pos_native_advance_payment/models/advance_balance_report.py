# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AdvanceBalanceReport(models.TransientModel):
    _name = 'advance.balance.report'
    _description = 'Reporte de Cartera - Saldos a Favor'

    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    advance_account_id = fields.Many2one(
        'account.account', string='Cuenta de Anticipos',
        related='company_id.pos_advance_account_id', readonly=True)

    partner_ids = fields.Many2many('res.partner', string='Clientes')
    include_zero = fields.Boolean(string='Incluir saldos en cero', default=False)

    line_ids = fields.One2many(
        'advance.balance.report.line', 'report_id',
        string='Líneas del reporte')

    def action_generate(self):
        self.line_ids.unlink()
        partners = self.partner_ids or self.env['res.partner'].search([])
        today = fields.Date.today()
        to_create = []
        for partner in partners:
            try:
                # Fuente única: pagos + notas crédito (igual que TPV).
                balance = partner.pos_advance_balance
                unreconciled = partner._get_unreconciled_advance_payments()
                notes = partner._get_unreconciled_credit_notes()
            except Exception:
                continue
            if not self.include_zero and balance <= 0.0:
                continue
            dates = []
            for payment, _r in unreconciled:
                dates.append(payment.payment_date or today)
            for note in notes:
                dates.append(note.invoice_date or today)
            oldest = min(dates) if dates else False
            latest = max(dates) if dates else False
            days = (today - oldest).days if oldest else 0
            to_create.append({
                'report_id': self.id,
                'partner_id': partner.id,
                'balance': balance,
                'days_oldest': days,
                'oldest_date': oldest,
                'latest_date': latest,
            })

        if to_create:
            self.env['advance.balance.report.line'].create(to_create)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'advance.balance.report',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_print_pdf(self):
        self.action_generate()
        return self.env.ref(
            'pos_native_advance_payment.action_report_advance_balance'
        ).report_action(self)


class AdvanceBalanceReportLine(models.TransientModel):
    _name = 'advance.balance.report.line'
    _description = 'Línea de reporte de cartera'

    report_id = fields.Many2one('advance.balance.report', string='Reporte')
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    balance = fields.Float(string='Saldo a Favor')
    days_oldest = fields.Integer(string='Días del más antiguo')
    oldest_date = fields.Date(string='Movimiento más antiguo')
    latest_date = fields.Date(string='Último movimiento')
    aging_range = fields.Char(string='Antigüedad', compute='_compute_aging_range')

    def _compute_aging_range(self):
        for r in self:
            if r.days_oldest <= 30:
                r.aging_range = '<= 30 días'
            elif r.days_oldest <= 60:
                r.aging_range = '31-60 días'
            else:
                r.aging_range = '> 60 días'
