odoo.define('pos_pending_orders_mgmt.custom_screen', function (require) {
    "use strict";

    var core = require('web.core');
    var _t = core._t;
    var QWeb = core.qweb;
    var screens = require('point_of_sale.screens');
    var gui = require('point_of_sale.gui');
    var ScreenWidget = screens.ScreenWidget;

    var chrome = require('point_of_sale.chrome');
    var models = require('point_of_sale.models');

    var DomCache = screens.DomCache;

    chrome.SynchNotificationWidget.include({
        start: function () {
            var self = this;
            this._super();
            this.$el.on('contextmenu', function (event) {
                event.preventDefault();
                self.gui.show_screen('pending_orders');
            });
        },
    });

    // Si esto falla, screens es undefined
    if (!screens || !screens.ScreenWidget) {
        console.error("No se pudo cargar ScreenWidget. Verifica las dependencias.");
        return;
    }

    var PendingOrderListScreenWidget = ScreenWidget.extend({
        template: 'PendingOrderListScreenWidget',

        init: function (parent, options) {
            this._super(parent, options);
            this.order_cache = new DomCache();
        },

        auto_back: true,

        show: function () {
            this._super();
            this.renderElement();
            this.$('.back').click(() => this.gui.back());
            this.render_list();
        },

        render_list: function () {
            var self = this;
            var orders = this.pos.db.get_orders();
            var contents = this.$('.pending-order-list-contents');
            contents.empty();

            orders.forEach(function (order_data) {
                var partner_name = _t('Unknown Customer');
                if (order_data.data.partner_id) {
                    var partner = self.pos.db.get_partner_by_id(order_data.data.partner_id);
                    if (partner) {
                        partner_name = partner.name;
                    }
                }

                var orderline = QWeb.render('PendingOrderLine', {
                    widget: self,
                    order: order_data,
                    partner_name: partner_name,
                });
                var $orderline = $(orderline);

                $orderline.find('.retry-order').click(function () {
                    self.pos.push_order(order_data.data).then(function () {
                        self.render_list();
                    });
                });

                $orderline.find('.remove-order').click(function () {
                    self.pos.db.remove_order(order_data.id);
                    self.render_list();
                });

                $orderline.find('.load-order').click(function () {
                    var order = new models.Order({}, { pos: self.pos });
                    order.init_from_JSON(order_data.data);
                    self.pos.get('orders').add(order);
                    self.pos.set('selectedOrder', order);
                    self.gui.show_screen('products');
                });

                contents.append($orderline);
            });
        },
    });

    gui.define_screen({
        name: 'pending_orders',
        widget: PendingOrderListScreenWidget,
    });

    return PendingOrderListScreenWidget;

});
