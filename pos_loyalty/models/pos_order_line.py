# Copyright 2024-present, Gemini
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    reward_id = fields.Many2one("loyalty.reward", string="Applied Reward")

    @api.model
    def _order_line_fields(self, line, session_id=None):
        fields_to_return = super(PosOrderLine, self)._order_line_fields(
            line, session_id
        )
        fields_to_return[2]["reward_id"] = line[2].get("reward_id", False)
        return fields_to_return
