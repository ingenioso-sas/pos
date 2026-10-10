# Copyright (C) 2024 - Today: Odoo Community Association (OCA)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Point of Sale - Custom UX",
    "version": "13.0.1.0.1",
    "category": "Point Of Sale",
    "summary": "Limit category list height in POS frontend for better UX",
    "description": """
Point of Sale - Custom UX
=========================

This module improves the Point of Sale frontend layout by limiting
the height of the category list scroller (``.category-list-scroller``)
to 20% of the viewport height (``20vh``).

Without this, the category bar can take too much vertical space on
screens with many categories, pushing the product list down and forcing
extra scrolling.

No new models, views or configuration are added. Only a CSS asset is
injected into ``point_of_sale.assets``.
    """,
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/pos",
    "license": "AGPL-3",
    "depends": ["point_of_sale"],
    "data": ["views/assets.xml"],
}
