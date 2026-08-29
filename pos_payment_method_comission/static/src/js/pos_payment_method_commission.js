/*
    Copyright (C) 2025-Today: Ingenioso Co
    @author: Ingenioso Co
    License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
*/

odoo.define('pos_payment_method_comission.pos', function (require) {
    "use strict";

    var models = require('point_of_sale.models');
    var screens = require('point_of_sale.screens');
    var core = require('web.core');
    var _t = core._t;

    var _super_posmodel = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        initialize: function (session, attributes) {
            var payment_method_model = _.find(this.models, function (model) {
                return model.model === 'pos.payment.method';
            });
            payment_method_model.fields.push(
                'has_commission',
                'commission_rate',
                'commission_fixed_amount',
                'commission_journal_id',
                'commission_account_id',
                'commission_tax_ids',
                'require_approval_reference',
                'reverse_commission_on_refund',
                'refund_policy'
            );
            return _super_posmodel.initialize.call(this, session, attributes);
        },
    });

    var _super_paymentline = models.Paymentline.prototype;
    models.Paymentline = models.Paymentline.extend({
        initialize: function(attributes, options) {
            _super_paymentline.initialize.apply(this, arguments);
            this.commission = 0;
            this.approval_reference = '';
        },
        set_approval_reference: function(ref){
            this.approval_reference = ref;
            this.trigger('change', this);
        },
        get_approval_reference: function(){
            return this.approval_reference;
        },
        // sets the amount of the payment line
        set_amount: function(value){
            _super_paymentline.set_amount.apply(this, arguments);
            this.calculate_commission();
        },

        calculate_commission: function() {
            var payment_method = this.payment_method;
            var amount = this.get_amount();
            var commission = 0;
            if (payment_method.has_commission) {
                var percentage_commission = 0;
                var fixed_commission = payment_method.commission_fixed_amount || 0;
                
                if (payment_method.commission_rate) {
                    var rate = payment_method.commission_rate / 100;
                    percentage_commission = amount * rate;
                }
                
                // Refund logic
                if (amount < 0) {
                    if (!payment_method.reverse_commission_on_refund) {
                        this.commission = 0;
                        this.trigger('change', this);
                        return;
                    }
                    fixed_commission = -Math.abs(fixed_commission);
                }

                commission = percentage_commission + fixed_commission;
            }
            this.commission = commission;
            this.trigger('change', this);
        },

        get_commission: function() {
            return this.commission;
        },

        export_as_JSON: function() {
            var json = _super_paymentline.export_as_JSON.apply(this, arguments);
            json.commission = this.get_commission();
            json.approval_reference = this.get_approval_reference();
            return json;
        },

        export_for_printing: function() {
            var json = _super_paymentline.export_for_printing.apply(this, arguments);
            json.commission = this.get_commission();
            return json;
        },
    });

    var _super_order = models.Order.prototype;
    models.Order = models.Order.extend({
        add_paymentline: function(payment_method) {
            _super_order.add_paymentline.apply(this, arguments);
            this.selected_paymentline.calculate_commission();
        },

        get_total_commission: function() {
            return this.paymentlines.reduce(function(sum, paymentLine) {
                return sum + paymentLine.get_commission();
            }, 0);
        },

        export_for_printing: function() {
            var receipt = _super_order.export_for_printing.apply(this, arguments);
            receipt.total_commission = this.get_total_commission();
            return receipt;
        },
    });

    screens.PaymentScreenWidget.include({
        renderElement: function() {
            var self = this;
            this._super();
            this.$('.paymentlines-container').on('change', '.paymentline-ref-input', function(ev) {
                var cid = $(this).closest('.paymentline').data('cid');
                var line = self.pos.get_order().get_paymentline(cid);
                if (line) {
                    line.set_approval_reference($(this).val());
                }
            });
        },
        validate_order: function(force_validation) {
            var order = this.pos.get_order();
            var lines = order.get_paymentlines();
            var is_refund = order.get_total_with_tax() < 0;
            
            for (var i = 0; i < lines.length; i++) {
                var method = lines[i].payment_method;
                // Refund policy check
                if (is_refund && method.refund_policy === 'wallet' && lines[i].get_amount() < 0) {
                    this.gui.show_popup('error',{
                        'title': _t('Método de Pago No Permitido'),
                        'body':  _t('El método ' + method.name + ' no permite devoluciones de dinero. Por favor, use "Saldo a Favor" o similar.'),
                    });
                    return;
                }
                // Approval reference check
                if (method.require_approval_reference && !lines[i].get_approval_reference() && lines[i].get_amount() > 0) {
                    this.gui.show_popup('error',{
                        'title': _t('Referencia de Aprobación Requerida'),
                        'body':  _t('Debe ingresar el código/referencia de aprobación para el método: ' + method.name),
                    });
                    return;
                }
            }
            this._super(force_validation);
        },
        // We need to recompute the commission when the payment line amount is changed
        payment_input: function(input) {
            var res = this._super.apply(this, arguments);
            var order = this.pos.get_order();
            var selected_paymentline = order.selected_paymentline;
            if (selected_paymentline) {
                selected_paymentline.calculate_commission();
            }
            return res;
        },
    });

});