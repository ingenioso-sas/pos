# Copyright 2004-2010 OpenERP SA
# Copyright 2017 RGB Consulting S.L. (https://www.rgbconsulting.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class LoyaltyProgram(models.Model):
    _name = "loyalty.program"

    name = fields.Char(
        # string="Loyalty Program Name", size=32, index=True, required=True, translate=True
        string="Nombre programa de fidelidad",
        size=32,
        index=True,
        required=True,
        translate=True,
    )
    pp_currency = fields.Float(
        # string=_("Points per currency"),
        # help="Amount of loyalty points given to the " "customer per sold currency",
        string=_("Moneda por punto"),
        help="Cantidad de moneda vendida por punto ganado. \nEjemplo: 1000, es decir, por cada $1000 vendidos el cliente gana 1 punto.",
        translate=True,
    )
    pp_product = fields.Float(
        # string=_("Points per product"),
        # help="Amount of loyalty points given to the " "customer per product sold",
        string=_("Puntos por producto"),
        help="Cantidad de puntos de fidelidad otorgados al cliente por producto vendido.",
    )
    pp_order = fields.Float(
        # string=_("Points per order"),
        # help="Amount of loyalty points given to the "
        # "customer for each point of sale order","""
        string=_("Puntos por orden"),
        help="Cantidad de puntos de fidelidad entregados al "
        "cliente para cada pedido de punto de venta.",
        translate=True,
    )
    rounding = fields.Float(
        # string="Points Rounding",
        string="Redondeo de puntos",
        default=1,
        # help="Loyalty point amounts will be rounded to " "multiples of this value",
        help="Los montos de los puntos de fidelidad se redondearán a múltiplos de este valor: ",
        translate=True,
    )

    rule_ids = fields.One2many(
        comodel_name="loyalty.rule",
        inverse_name="loyalty_program_id",
        string="Reglas",  # string="Rules"
    )

    reward_ids = fields.One2many(
        comodel_name="loyalty.reward",
        inverse_name="loyalty_program_id",
        string="Recompensas",
        # string="Rewards",
    )
