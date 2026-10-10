# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    pos_advance_account_id = fields.Many2one(
        'account.account',
        string="Cuenta de Anticipos para TPV",
        domain=[('reconcile', '=', True), ('internal_type', 'in', ['receivable', 'payable'])],
        help="Cuenta contable para rastrear los saldos a favor (anticipos) de los clientes en el TPV.\n\n"
             "Debe ser una cuenta de PASIVO (los anticipos recibidos de clientes son dinero que la empresa "
             "le debe al cliente en bienes, servicios o devolución). En el PUC colombiano corresponde a "
             "2805 - Anticipos de Clientes.\n\n"
             "Requisitos de configuración de la cuenta:\n"
             "1. Tipo interno: 'Pagado / Cuenta por pagar' (payable).\n"
             "2. Conciliar: activado. Esto es imprescindible para poder conciliar los depósitos (créditos) "
             "contra el consumo posterior (débitos) y calcular el saldo disponible real por cliente."
    )

    advance_overdraft_limit = fields.Float(
        string="Límite de Sobregiro por Defecto (Saldo a Favor)",
        default=0.0,
        help="Límite de sobregiro predeterminado para todos los clientes. "
             "Se puede ajustar por cliente individualmente."
    )

    pos_deposit_product_id = fields.Many2one(
        'product.template',
        string="Producto Auxiliar de Depósito (TPV)",
        help="Producto de tipo servicio, sin impuestos ni stock, usado en los "
             "pedidos de depósito para que la sesión cuadre caja por método "
             "(efectivo/banco) como una venta normal pero sin entrega. "
             "Su cuenta de ingreso debe ser la cuenta de anticipos.",
    )

    pos_advance_journal_id = fields.Many2one(
        'account.journal',
        string="Diario Clearing de Anticipos",
        domain=[('type', '=', 'bank')],
        help="Diario banco cuyas cuentas por defecto (débito/crédito) son la "
             "cuenta de anticipos. El account.payment del depósito usa este "
             "diario para asentar Dr Anticipos / Cr CxC SIN tocar efectivo "
             "(el efectivo ya queda en la sesión TPV). No usar diario cash.",
    )

    def _sync_deposit_product_income(self):
        """Alinea la cuenta de ingreso del producto auxiliar con anticipos."""
        for company in self:
            product = company.pos_deposit_product_id
            advance = company.pos_advance_account_id
            if product and advance:
                product.with_context(force_company=company.id).write(
                    {'property_account_income_id': advance.id})
