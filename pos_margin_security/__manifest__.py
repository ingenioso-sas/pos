# Copyright 2018 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Pos Sale Margin Security",
    "version": "13.0.0.0.1",
    "author": "Anderson B" "Tecnativa" "Odoo Community Association (OCA)",
    "website": "https://github.com/ingenioso-sas/margin-analysis",
    "category": "Sales",
    "license": "AGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["anderson-buitron"],
    "depends": ["pos_margin", "sale_margin_security"],
    "data": [
        "security/pos_margin_security_security.xml",
        "views/pos_margin_security_view.xml",
    ],
    "installable": True,
}
