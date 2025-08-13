/*
    Copyright (C) 2025-Today: Ing.Factura S.L
    @author: Ing.Factura S.L
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
                'commission_account_id'
            );
            return _super_posmodel.initialize.call(this, session, attributes);
        },
    });

    var _super_paymentline = models.Paymentline.prototype;
    models.Paymentline = models.Paymentline.extend({
        initialize: function(attributes, options) {
            _super_paymentline.initialize.apply(this, arguments);
            this.commission = 0;
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
                if (payment_method.commission_rate) {
                    var rate = payment_method.commission_rate / 100;
                    percentage_commission = amount * rate;
                }
                var fixed_commission = payment_method.commission_fixed_amount || 0;
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