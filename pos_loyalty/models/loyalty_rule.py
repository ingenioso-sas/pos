# Copyright 2004-2010 OpenERP SA
# Copyright 2017 RGB Consulting S.L. (https://www.rgbconsulting.com)
# Copyright 2018 Lambda IS DOOEL <https://www.lambda-is.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class LoyaltyRule(models.Model):
    _name = "loyalty.rule"

    # name = fields.Char(string="Rule Name", size=32, index=True, required=True)
    name = fields.Char(string="Nombre de la regla", size=32, index=True, required=True)
    type = fields.Selection(
        # selection=[("product", "Product"), ("category", "Category")],
        # string="Type",
        selection=[("product", "Producto"), ("category", "Categoria")],
        string="Tipo",
        required=True,
        # default="product",
        default="product",
        # help="The concept this rule applies to",
        help="El concepto al que se aplica esta regla",
    )
    cumulative = fields.Boolean(
        string="Acumulativo",
        help="Los puntos de esta regla se sumarán a los puntos ganados de otras reglas con el mismo concepto.",
        # help="The points from this rule will be added "
        # "to points won from other rules with "
        # "the same concept"
        #
    )
    pp_product = fields.Float(
        # string="Points per product", help="Amount of points earned per product"
        string="Puntos por producto",
        help="Cantidad de puntos ganados por producto.",
    )
    pp_currency = fields.Float(
        # string="Points per currency", help="Amount of points earned per currency"
        string="Moneda por punto",
        help="Cantidad de moneda vendida por punto ganado. \nEjemplo: 1000, es decir, por cada $1000 vendidos el cliente gana 1 punto.",
    )
    loyalty_program_id = fields.Many2one(
        comodel_name="loyalty.program",
        # string="Loyalty Program",
        string="Programa de fidelidad",
        # help="The Loyalty Program this rule " "belongs to",
        help="El Programa de Lealtad esta regla pertenece a:",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        domain=[("available_in_pos", "=", True)],
        # string="Target Product",
        # help="The product affected by this rule",
        string="Producto objetivo",
        help="El producto afectado por esta regla.",
    )
    category_id = fields.Many2one(
        comodel_name="pos.category",
        # string="Target Category",
        # help="The category affected by this rule",
        string="Categoria objetivo",
        help="La categoría afectada por esta regla.",
    )
