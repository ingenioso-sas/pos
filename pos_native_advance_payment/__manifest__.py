# -*- coding: utf-8 -*-
{
    'name': 'POS Native Advance Payment (Cartera)',
    'version': '13.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Use native Odoo advance payments (saldos a favor) seamlessly in POS.',
    'description': """
        Permite a los clientes usar sus saldos a favor (anticipos registrados en contabilidad nativa) 
        como método de pago en el TPV.

        Funcionalidades:
        - Selección de cuenta de anticipos configurable.
        - Cálculo en tiempo real del saldo disponible desde account.move.line.
        - Validación en el TPV para impedir sobregiros.
        - Conciliación contable automática al validar el pedido.
    """,
    'author': 'Ing.Factura S.L. / AI Assistant',
    'depends': ['point_of_sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/product_deposit.xml',
        'views/res_config_settings_views.xml',
        'views/pos_payment_method_views.xml',
        'views/res_partner_views.xml',
        'views/assets.xml',
        'views/advance_balance_report_view.xml',
        'views/pay_advance_wizard_view.xml',
    ],
    'qweb': [
        'static/src/xml/pos_native_advance_payment.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
