# Copyright 2018 GRAP - Sylvain LE GAL
# Copyright 2018 Tecnativa S.L. - David Vidal
# Copyright 2019 Coop IT Easy SCRLfs
#                   Pierrick Brun <pierrick.brun@akretion.com>
# Copyright 2019 Druidoo - Iván Todorovich
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    iface_order_mgmt = fields.Boolean(
        string="Order Management",
        help="Allows to manage orders in the frontend",
        default=True,
    )

    iface_reprint_done_order = fields.Boolean(
        string="Reprint Orders",
        default=True,
        help="Allows to reprint already done orders in the frontend",
    )

    iface_return_done_order = fields.Boolean(
        string="Return Orders",
        default=True,
        help="Allows to return already done orders in the frontend",
    )

    iface_copy_done_order = fields.Boolean(
        string="Duplicate Orders",
        default=True,
        help="Allows to duplicate already done orders in the frontend",
    )

    iface_load_done_order_max_qty = fields.Integer(
        string="Maximum Orders to load",
        default=10,
        required=True,
        help="Maximum number of orders to load on the PoS at its init. "
        "Set it to 0 to load none (it's still possible to load them by "
        "ticket code).",
    )

    disable_return_payment_method_restriction = fields.Boolean(
        string="Disable Return Payment Restriction",
        help="If checked, any payment method can be used for returns.",
    )

    return_bypass_payment_method_ids = fields.Many2many(
        comodel_name="pos.payment.method",
        relation="pos_config_return_bypass_payment_method_rel",
        column1="config_id",
        column2="payment_method_id",
        string="Exempt Return Payment Methods",
        help="Payment methods that can be used for returns even if they were not used in the original order.",
    )

    pending_order_modification_confirmation = fields.Char(
        string="Pending Order Modification Confirmation",
        default="modificar orden",
        help="Word the cashier must type in the PoS to confirm that an "
        "unsynchronized order can be modified.",
    )
