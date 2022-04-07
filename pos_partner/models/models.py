# -*- coding: utf-8 -*-
from odoo import models, fields, api
import datetime

class ResPartner(models.Model):
    _inherit = ["res.partner"]
    _name = "res.partner"


    identificacion = fields.Char("Identificacion", help="Identificacion del Cliente" )
    fecha_nac = fields.Date("Fecha de nacimiento", help="Fecha de nacimiento" )
    mes_nac = fields.Integer(compute='_cacular_mes_nacimiento',
                             string="Mes nacimiento", help="Mes de nacimiento",
                             store=True, readonly=True,
                             search='_search_mes_nac')
    edad = fields.Integer(compute='_cacular_edad', string="Edad", store=False)

    @api.depends('fecha_nac')
    def _cacular_mes_nacimiento(self):
        try:
            for record in self:
                if (not record.fecha_nac is False):
                    record.mes_nac = record.fecha_nac.month
                else:
                    record.mes_nac = None
        except Exception as err:
            print("error calculando mes_nac: "+str(err))


    @api.depends('fecha_nac')
    def _cacular_edad(self):
        try:
            #for record in self: # store:True
            if(not self.fecha_nac is False):
                today_date = datetime.date.today()
                self.edad = str((int)((today_date - self.fecha_nac).days / 365))
            else:
                self.edad = None
        except Exception as err:
            print("error calculando edad: "+str(err))


    @api.depends('fecha_nac')
    def _search_mes_nac(self, operator, value):
        if operator == 'like':
            operator = 'ilike'
        return [('fecha_nac:month', operator, value)]
