import datetime
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    identificacion = fields.Char(
        _("Identification"),
        help=_("Deprecated: use VAT instead. Kept hidden for migration."),
    )
    fecha_nac = fields.Date(_("Date of Birth"), help=_("Date of Birth"))
    mes_nac = fields.Integer(
        compute="_cacular_mes_nacimiento",
        string=_("Month of Birth"),
        help=_("Month of Birth"),
        store=True,
        readonly=True,
        search="_search_mes_nac",
    )
    edad = fields.Integer(compute="_cacular_edad", string=_("Age"), store=False)

    @api.depends("fecha_nac")
    def _cacular_mes_nacimiento(self):
        for record in self:
            try:
                if record.fecha_nac:
                    record.mes_nac = record.fecha_nac.month
                else:
                    record.mes_nac = 0
            except Exception as err:
                _logger.warning("error calculando mes_nac: %s", err)
                record.mes_nac = 0

    @api.depends("fecha_nac")
    def _cacular_edad(self):
        today = datetime.date.today()
        for record in self:
            try:
                if record.fecha_nac:
                    born = record.fecha_nac
                    record.edad = (
                        today.year
                        - born.year
                        - ((today.month, today.day) < (born.month, born.day))
                    )
                else:
                    record.edad = 0
            except Exception as err:
                _logger.warning("error calculando edad: %s", err)
                record.edad = 0

    def _search_mes_nac(self, operator, value):
        if operator == "like":
            operator = "ilike"
        return [("fecha_nac:month", operator, value)]

    @api.model
    def create(self, vals):
        if not vals.get("vat") and vals.get("identificacion"):
            vals["vat"] = vals["identificacion"]
        return super().create(vals)

    def write(self, vals):
        if "vat" not in vals and "identificacion" not in vals:
            return super().write(vals)
        for record in self:
            vat = vals.get("vat", record.vat)
            identificacion = vals.get("identificacion", record.identificacion)
            if not vat and identificacion:
                record_vals = dict(vals)
                record_vals["vat"] = identificacion
                super(ResPartner, record).write(record_vals)
            else:
                super(ResPartner, record).write(vals)
        return True
