# from odoo import http


# class PartnerPos(http.Controller):
#     @http.route('/partner_pos/partner_pos/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/partner_pos/partner_pos/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('partner_pos.listing', {
#             'root': '/partner_pos/partner_pos',
#             'objects': http.request.env['partner_pos.partner_pos'].search([]),
#         })

#     @http.route('/partner_pos/partner_pos/objects/<model("partner_pos.partner_pos"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('partner_pos.object', {
#             'object': obj
#         })
