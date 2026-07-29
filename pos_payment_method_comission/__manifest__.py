# Copyright (C) 2025-Today: Ing.Factura S.L
# @author: Ing.Factura S.L
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Point of Sale - Payment Method Commission",
    "summary": "Allows to define commissions for PoS payment methods.",
    "version": "13.0.2.0.0",
    "category": "Point of Sale",
    "author": "Ing.Factura S.L",
    "website": "https://www.ingfactura.com",
    "license": "AGPL-3",
    "depends": ["point_of_sale", "account"],
    "data": [
        "views/view_pos_payment_method.xml",
        "views/templates.xml",
    ],
    "qweb": [
        "static/src/xml/pos_payment_method_commission.xml",
    ],
    "images": [
        "static/description/icon.png",
    ],
    "installable": True,
}