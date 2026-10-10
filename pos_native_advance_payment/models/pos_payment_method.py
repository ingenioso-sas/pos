# -*- coding: utf-8 -*-
from odoo import _, models, fields, api
from odoo.exceptions import ValidationError

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    is_advance_payment = fields.Boolean(
        string="Es Método de Saldo a Favor",
        help="Si está marcado, el TPV validará contra pagos sin conciliar "
             "(account.payment) y consumirá el crédito en CxC del cliente. "
             "Toda venta que lo usa se factura siempre (obligatorio) y exige "
             "cliente con NIT."
    )

    @api.onchange('is_advance_payment')
    def _onchange_is_advance_payment(self):
        # Nativo: receivable_account_id es required=True (solo cuentas
        # receivable conciliables). No puede quedar vacío: se apunta a la
        # CxC de clientes para que el consumo concilie con facturas y pagos
        # (misma cuenta). NUNCA a la 2805 (payable: el dominio nativo la
        # excluye y, además, cuentas distintas no concilian).
        # split_transactions=True es obligatorio: sin él, las líneas del
        # cierre van agregadas por método sin partner y el consumo/ﬁado no
        # se puede atribuir por cliente.
        for record in self:
            company = record.company_id or self.env.company
            get_prop = self.env['ir.property'].with_context(
                force_company=company.id).get
            cxc = get_prop('property_account_receivable_id', 'res.partner')
            default_pos = company.account_default_pos_receivable_account_id
            if record.is_advance_payment:
                record.receivable_account_id = cxc or default_pos
                record.split_transactions = True
            elif default_pos and (not record.receivable_account_id
                                  or record.receivable_account_id == cxc):
                record.receivable_account_id = default_pos

    @api.constrains('is_advance_payment', 'is_cash_count')
    def _check_advance_and_cash(self):
        for record in self:
            if record.is_advance_payment and record.is_cash_count:
                raise ValidationError(_(
                    "Un método de pago no puede ser de Saldo a Favor "
                    "y de Efectivo al mismo tiempo."
                ))
