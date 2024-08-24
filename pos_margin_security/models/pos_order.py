# Copyright 2020 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"
