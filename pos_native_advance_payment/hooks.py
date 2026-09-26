# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        product = env.ref(
            'pos_native_advance_payment.product_template_pos_advance_deposit',
            raise_if_not_found=False,
        )
    except Exception:
        product = False
    if not product:
        return
    for company in env['res.company'].search([]):
        if not company.pos_deposit_product_id:
            company.pos_deposit_product_id = product.id
    for company in env['res.company'].search(
            [('pos_deposit_product_id', '!=', False),
             ('pos_advance_account_id', '!=', False)]):
        try:
            company._sync_deposit_product_income()
        except Exception:
            continue
