/* Copyright 2018 GRAP - Sylvain LE GAL
   Copyright 2018 Tecnativa - David Vidal
   Copyright 2019 Druidoo - Ivan Todorovich
   License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl). */

odoo.define("pos_order_mgmt.widgets", function (require) {
    "use strict";

    var core = require("web.core");
    var _t = core._t;
    var PosBaseWidget = require("point_of_sale.BaseWidget");
    var screens = require("point_of_sale.screens");
    var gui = require("point_of_sale.gui");
    var chrome = require("point_of_sale.chrome");
    var models = require("point_of_sale.models");

    var QWeb = core.qweb;
    var ScreenWidget = screens.ScreenWidget;
    var DomCache = screens.DomCache;

    screens.ReceiptScreenWidget.include({
        render_receipt: function () {
            if (!this.pos.reloaded_order) {
                return this._super();
            }
            var order = this.pos.reloaded_order;
            this.$(".pos-receipt-container").html(
                QWeb.render("OrderReceipt", {
                    widget: this,
                    pos: this.pos,
                    order: order,
                    receipt: order.export_for_printing(),
                    orderlines: order.get_orderlines(),
                    paymentlines: order.get_paymentlines(),
                })
            );
            this.pos.from_loaded_order = true;
        },
        click_next: function () {
            if (!this.pos.from_loaded_order) {
                return this._super();
            }
            this.pos.from_loaded_order = false;
            // When reprinting a loaded order we temporarily set it as the
            // active one. When we get out from the printing screen, we set
            // it back to the one that was active
            if (this.pos.current_order) {
                this.pos.set_order(this.pos.current_order);
                this.pos.current_order = false;
            }
            return this.gui.show_screen(this.gui.startup_screen);
        },
    });

    var OrderListScreenWidget = ScreenWidget.extend({
        template: "OrderListScreenWidget",

        init: function (parent, options) {
            this._super(parent, options);
            this.order_cache = new DomCache();
            this.orders = [];
            this.unknown_products = [];
            this.search_query = false;
            this.page = 0;
            this.pagination = {};
            this.perform_search();
        },

        auto_back: true,

        show: function () {
            var self = this;
            var previous_screen = false;
            if (this.pos.get_order()) {
                previous_screen = this.pos
                    .get_order()
                    .get_screen_data("previous-screen");
            }
            if (previous_screen === "receipt") {
                this.gui.screen_instances.receipt.click_next();
                this.gui.show_screen("orderlist");
            }
            this._super();
            this.renderElement();
            this.old_order = this.pos.get_order();
            this.$(".back").click(function () {
                return self.gui.show_screen(self.gui.startup_screen);
            });

            if (this.pos.config.iface_vkeyboard && this.chrome.widget.keyboard) {
                this.chrome.widget.keyboard.connect(this.$(".searchbox input"));
            }

            var search_timeout = null;
            this.$(".searchbox input").on("keyup", function () {
                self.page = 0;
                self.search_query = this.value;
                clearTimeout(search_timeout);
                search_timeout = setTimeout(function () {
                    self.perform_search();
                }, 70);
            });

            this.$(".searchbox .search-clear").click(function () {
                self.clear_search();
            });

            this.$el.off('click', '.previous-page-order').on('click', '.previous-page-order', function () {
                if (self.page > 0) {
                    self.page -= 1;
                    self.perform_search();
                }
            });
            this.$el.off('click', '.next-page-order').on('click', '.next-page-order', function () {
                if (self.page < self.pagination.total_pages - 1) {
                    self.page += 1;
                    self.perform_search();
                }
            });

            this.$el.off('click', '.first-page-order').on('click', '.first-page-order', function () {
                if (self.page > 0) {
                    self.page = 0;
                    self.perform_search();
                }
            });

            this.$el.off('click', '.order-line').on('click', '.order-line', function (event) {
                self.click_order_line(event);
            });

            this.perform_search();
        },

        click_order_line: function (event) {
            var self = this;
            var $line = $(event.currentTarget);
            var order_id = parseInt($line.data('order-id'), 10);
            var $details = $line.next('.order-line-details');

            if ($details.hasClass('o_hidden')) {
                // Hide all other details
                this.$('.order-line-details').addClass('o_hidden');
                this.$('.order-line').removeClass('highlight');

                $details.removeClass('o_hidden');
                $line.addClass('highlight');

                // Load details if not loaded
                var $container = $details.find('.order-details-container');
                if (!$container.children().length) {
                    $container.html('<div class="loader"><i class="fa fa-spinner fa-spin" /> Loading...</div>');
                    this.load_order_data(order_id).then(function (order_data) {
                        var details_html = QWeb.render('OrderDetails', {
                            widget: self,
                            order: order_data,
                        });
                        $container.html(details_html);
                    });
                }
            } else {
                $details.addClass('o_hidden');
                $line.removeClass('highlight');
            }
        },

        render_list: function () {
            var self = this;
            var orders = this.orders;
            var contents = this.$el[0].querySelector(".order-list-contents");
            contents.innerHTML = "";
            for (var i = 0, len = Math.min(orders.length, 1000); i < len; i++) {
                var order = orders[i];
                var orderline_nodes = this.order_cache.get_node(order.id || order.uid);
                if (!orderline_nodes) {
                    var orderline_html = QWeb.render("OrderLine", {
                        widget: this,
                        order: order,
                    });
                    var el = document.createElement("tbody");
                    el.innerHTML = orderline_html;
                    orderline_nodes = _.filter(el.childNodes, function (node) {
                        return node.nodeType === Node.ELEMENT_NODE;
                    });
                    this.order_cache.cache_node(order.id || order.uid, orderline_nodes);
                }
                var main_line = orderline_nodes[0];
                if (order === this.old_order) {
                    main_line.classList.add("highlight");
                } else {
                    main_line.classList.remove("highlight");
                }
                _.each(orderline_nodes, function (node) {
                    contents.appendChild(node);
                });
            }

            if (this.pagination.total_pages > 0) {
                this.$('.page-indicator').text('Page ' + (this.pagination.current_page + 1) + ' / ' + this.pagination.total_pages);
            } else {
                this.$('.page-indicator').text('No orders found');
            }

            if (this.pagination.prev_page !== null) {
                this.$('.first-page-order').show();
                this.$('.previous-page-order').show();
            } else {
                this.$('.first-page-order').hide();
                this.$('.previous-page-order').hide();
            }
            if (this.pagination.next_page !== null) {
                this.$('.next-page-order').show();
            } else {
                this.$('.next-page-order').hide();
            }

            // FIXME: Everytime the list is rendered we need to reassing the
            // button events.
            this.$(".order-list-return").off("click");
            this.$(".order-list-reprint").off("click");
            this.$(".order-list-copy").off("click");
            this.$(".order-list-reprint").click(function (event) {
                self.order_list_actions(event, "print");
            });
            this.$(".order-list-copy").click(function (event) {
                self.order_list_actions(event, "copy");
            });
            this.$(".order-list-return").click(function (event) {
                self.order_list_actions(event, "return");
            });

        },

        order_list_actions: function (event, action) {
            var self = this;
            var dataset = event.target.parentNode.dataset;
            self.load_order_data(parseInt(dataset.orderId, 10)).then(function (
                order_data
            ) {
                self.order_action(order_data, action);
            });
        },

        order_action: function (order_data, action) {
            if (this.old_order !== null) {
                this.gui.back();
            }
            var order = this.load_order_from_data(order_data, action);
            if (!order) {
                // The load of the order failed. (products not found, ...
                // We cancel the action
                return;
            }
            this["action_" + action](order_data, order);
        },

        action_print: function (order_data, order) {
            // We store temporarily the current order so we can safely compute
            // taxes based on fiscal position
            this.pos.current_order = this.pos.get_order();

            this.pos.set_order(order);

            this.pos.reloaded_order = order;
            var skip_screen_state = this.pos.config.iface_print_skip_screen;
            // Disable temporarily skip screen if set
            this.pos.config.iface_print_skip_screen = false;
            this.gui.show_screen("receipt");
            this.pos.reloaded_order = false;
            // Set skip screen to whatever previous state
            this.pos.config.iface_print_skip_screen = skip_screen_state;

            // If it's invoiced, we also print the invoice
            // if (order_data.to_invoice) {
            //     this.pos.chrome.do_action("point_of_sale.pos_invoice_report", {
            //         additional_context: {active_ids: [order_data.id]},
            //     });
            // }

            // Destroy the order so it's removed from localStorage
            // Otherwise it will stay there and reappear on browser refresh
            order.destroy();
        },

        action_copy: function (order_data, order) {
            order.trigger("change");
            this.pos.get("orders").add(order);
            this.pos.set("selectedOrder", order);
            return order;
        },

        action_return: function (order_data, order) {
            order.trigger("change");
            this.pos.get("orders").add(order);
            this.pos.set("selectedOrder", order);
            return order;
        },

        _prepare_order_from_order_data: function (order_data, action) {
            var self = this;
            var order = new models.Order(
                {},
                {
                    pos: this.pos,
                }
            );

            // Get Customer
            if (order_data.partner_id) {
                order.set_client(this.pos.db.get_partner_by_id(order_data.partner_id));
            }

            // Get fiscal position
            if (order_data.fiscal_position && this.pos.fiscal_positions) {
                var fiscal_positions = this.pos.fiscal_positions;
                order.fiscal_position = fiscal_positions.filter(function (p) {
                    return p.id === order_data.fiscal_position;
                })[0];
                order.trigger("change");
            }

            // Get order lines
            self._prepare_orderlines_from_order_data(order, order_data, action);

            // Get Name
            if (["print"].indexOf(action) !== -1) {
                order.name = order_data.pos_reference;
            } else if (["return"].indexOf(action) !== -1) {
                order.name = _t("Refund ") + order.uid;
            }

            // Get to invoice
            if (["return", "copy"].indexOf(action) !== -1) {
                // If previous order was invoiced, we need a refund too
                order.set_to_invoice(order_data.to_invoice);
            }

            // Get Salesperson
            if (["return"].indexOf(action) !== -1) {
                var cashier = false;
                if (order_data.employee_id && this.pos.employees) {
                    cashier = _.find(this.pos.employees, function (e) {
                        return e.id === order_data.employee_id;
                    });
                }
                if (!cashier && order_data.user_id) {
                    if (this.pos.employees) {
                        cashier = _.find(this.pos.employees, function (e) {
                            return e.user_id && e.user_id[0] === order_data.user_id;
                        });
                    }
                }
                if (cashier) {
                    order.employee_id = cashier.id;
                    if (cashier.user_id) {
                        order.user_id = cashier.user_id[0];
                    }
                } else if (order_data.user_id) {
                    order.user_id = order_data.user_id;
                }
            }

            // Get returned Order
            if (["print"].indexOf(action) !== -1) {
                // Get the same value as the original
                order.returned_order_id = order_data.returned_order_id;
                order.returned_order_reference = order_data.returned_order_reference;
            } else if (["return"].indexOf(action) !== -1) {
                order.returned_order_id = order_data.id;
                order.returned_order_reference = order_data.pos_reference;
                order.original_payments = order_data.statement_ids;
            }

            // Get Date
            if (["print"].indexOf(action) !== -1) {
                order.formatted_validation_date = moment(order_data.date_order).format(
                    "YYYY-MM-DD HH:mm:ss"
                );
            }

            // Get Payment lines
            if (["print"].indexOf(action) !== -1) {
                var paymentLines = order_data.statement_ids || [];
                _.each(paymentLines, function (paymentLine) {
                    var line = paymentLine;
                    // In case of local data
                    if (line.length === 3) {
                        line = line[2];
                    }
                    _.each(self.pos.payment_methods, function (cashregister) {
                        if (cashregister.id === line.payment_method_id) {
                            if (line.amount > 0) {
                                // If it is not change
                                order.add_paymentline(cashregister);
                                order.selected_paymentline.set_amount(line.amount);
                            }
                        }
                    });
                });
            }
            return order;
        },

        _prepare_orderlines_from_order_data: function (order, order_data, action) {
            var orderLines = order_data.line_ids || order_data.lines || [];

            var self = this;
            _.each(orderLines, function (orderLine) {
                var line = orderLine;
                // In case of local data
                if (line.length === 3) {
                    line = line[2];
                }
                var product = self.pos.db.get_product_by_id(line.product_id);
                // Check if product are available in pos
                if (_.isUndefined(product)) {
                    self.unknown_products.push(String(line.product_id));
                } else {
                    // Create a new order line
                    order.add_product(
                        product,
                        self._prepare_product_options_from_orderline_data(
                            order,
                            line,
                            action
                        )
                    );
                    // Restore lot information.
                    if (["return"].indexOf(action) !== -1) {
                        var orderline = order.get_selected_orderline();
                        if (orderline.pack_lot_lines) {
                            _.each(orderline.return_pack_lot_names, function (lot_name) {
                                orderline.pack_lot_lines.add(
                                    new models.Packlotline(
                                        { lot_name: lot_name },
                                        { order_line: orderline }
                                    )
                                );
                            });
                            orderline.trigger("change", orderline);
                        }
                    }
                }
            });
        },

        _prepare_product_options_from_orderline_data: function (order, line, action) {
            var qty = line.qty;
            if (["return"].indexOf(action) !== -1) {
                // Invert line quantities
                qty *= -1;
            }
            return {
                price: line.price_unit,
                quantity: qty,
                discount: line.discount,
                merge: false,
                extras: {
                    return_pack_lot_names: line.pack_lot_names,
                },
            };
        },

        load_order_data: function (order_id) {
            var self = this;
            return this._rpc({
                model: "pos.order",
                method: "load_done_order_for_pos",
                args: [order_id],
            }).catch(function (error) {
                if (parseInt(error.code, 10) === 200) {
                    // Business Logic Error, not a connection problem
                    self.gui.show_popup("error-traceback", {
                        title: error.data.message,
                        body: error.data.debug,
                    });
                } else {
                    self.gui.show_popup("error", {
                        title: _t("Connection error"),
                        body: _t(
                            "Can not execute this action because the POS" +
                            " is currently offline"
                        ),
                    });
                }
            });
        },

        load_order_from_data: function (order_data, action) {
            var self = this;
            this.unknown_products = [];
            var order = self._prepare_order_from_order_data(order_data, action);
            // Forbid POS Order loading if some products are unknown
            if (self.unknown_products.length > 0) {
                self.gui.show_popup("error-traceback", {
                    title: _t("Unknown Products"),
                    body:
                        _t(
                            "Unable to load some order lines because the " +
                            "products are not available in the POS cache.\n\n" +
                            "Please check that lines :\n\n  * "
                        ) + self.unknown_products.join("; \n  *"),
                });
                return false;
            }
            return order;
        },

        // Search Part 
        search_done_orders: function (query) {
            var self = this;
            return this._rpc({
                model: "pos.order",
                method: "search_done_orders_for_pos",
                args: [query || "", this.pos.pos_session.id, this.page],
            })
                .then(function (result) {
                    self.orders = result.items;
                    self.pagination = {
                        current_page: result.current_page,
                        next_page: result.nex_page,
                        prev_page: result.prev_page,
                        total_items: result.total_items,
                        total_pages: result.total_pages,
                        page_size: result.page_size,
                    };

                    // Get the date in local time
                    _.each(self.orders, function (order) {
                        if (order.date_order) {
                            order.date_order = moment
                                .utc(order.date_order)
                                .local()
                                .format("YYYY-MM-DD HH:mm:ss");
                        }
                    });
                })
                .catch(function (error, event) {
                    if (parseInt(error.code, 10) === 200) {
                        // Business Logic Error, not a connection problem
                        self.gui.show_popup("error-traceback", {
                            title: error.data.message,
                            body: error.data.debug,
                        });
                    } else {
                        self.gui.show_popup("error", {
                            title: _t("Connection error"),
                            body: _t(
                                "Can not execute this action because the POS" +
                                " is currently offline"
                            ),
                        });
                    }
                    event?.preventDefault();
                });
        },

        perform_search: function () {
            var self = this;
            return this.search_done_orders(self.search_query).then(function () {
                self.render_list();
            });
        },

        clear_search: function () {
            var self = this;
            self.$(".searchbox input")[0].value = "";
            self.$(".searchbox input").focus();
            self.search_query = false;
            self.page = 0;
            self.perform_search();
        },
    });

    gui.define_screen({
        name: "orderlist",
        widget: OrderListScreenWidget,
    });

    var ListOrderButtonWidget = PosBaseWidget.extend({
        template: "ListOrderButtonWidget",
        init: function (parent, options) {
            var opts = options || {};
            this._super(parent, opts);
            this.action = opts.action;
            this.label = opts.label;
        },

        button_click: function () {
            this.gui.show_screen("orderlist");
        },

        renderElement: function () {
            var self = this;
            this._super();
            this.$el.click(function () {
                self.button_click();
            });
        },
    });

    var widgets = chrome.Chrome.prototype.widgets;
    widgets.push({
        name: "list_orders",
        widget: ListOrderButtonWidget,
        prepend: ".pos-rightheader",
        args: {
            label: "All Orders",
        },
    });

    chrome.Chrome.include({
        renderElement: function () {
            this._super();
            var self = this;
            this.pos.on(
                "change:selectedOrder",
                function () {
                    var order = self.pos.get_order();
                    var $username = self.$(".username");
                    if (order && order.returned_order_id) {
                        $username.css({ "pointer-events": "none", opacity: "0.5" });
                    } else {
                        $username.css({ "pointer-events": "auto", opacity: "1" });
                    }
                },
                this
            );
        },
    });

    screens.PaymentScreenWidget.include({
        renderElement: function () {
            this._super();
            var order = this.pos.get_order();
            if (order && order.returned_order_id) {
                // Disable Invoice button
                this.$(".js_invoice").css({
                    "pointer-events": "none",
                    opacity: "0.5",
                });
                // Disable Electronic Invoice button (if exists)
                this.$(".js_electronic_invoice").css({
                    "pointer-events": "none",
                    opacity: "0.5",
                });
                // Disable Cashier button in Payment Screen (some custom layouts have it)
                this.$(".js_cashier").css({
                    "pointer-events": "none",
                    opacity: "0.5",
                });
            }
        },
        click_paymentmethods: function (id) {
            var order = this.pos.get_order();
            if (order.returned_order_id && order.original_payments) {
                var is_allowed = _.find(order.original_payments, function (p) {
                    return p.payment_method_id === id;
                });
                if (!is_allowed) {
                    this.gui.show_popup("error", {
                        title: _t("Payment Method Not Allowed"),
                        body: _t(
                            "You can only use payment methods used in the original order."
                        ),
                    });
                    return;
                }
            }
            this._super(id);
        },
        order_is_valid: function (force_validation) {
            var order = this.pos.get_order();
            var orderlines = order.get_orderlines();
            for (var i = 0; i < orderlines.length; i++) {
                var line = orderlines[i];
                if (line.get_quantity() === 0) {
                    this.gui.show_popup("error", {
                        title: _t("Zero Quantity Line"),
                        body: _.str.sprintf(
                            _t("Product %s has zero quantity. You cannot have order lines with a quantity of zero (0)."),
                            line.get_product().display_name
                        ),
                    });
                    return false;
                }
            }
            if (order.returned_order_id && order.original_payments) {
                var paymentlines = order.get_paymentlines();
                var amounts_by_method = {};
                for (var i = 0; i < paymentlines.length; i++) {
                    var line = paymentlines[i];
                    var mid = line.payment_method.id;
                    amounts_by_method[mid] =
                        (amounts_by_method[mid] || 0) + line.get_amount();
                }

                for (var mid in amounts_by_method) {
                    var original = _.find(order.original_payments, function (p) {
                        return p.payment_method_id === parseInt(mid, 10);
                    });
                    if (
                        original &&
                        Math.abs(amounts_by_method[mid]) >
                            Math.abs(original.amount) + 0.0001
                    ) {
                        var payment_method = this.pos.payment_methods_by_id[mid];
                        this.gui.show_popup("error", {
                            title: _t("Amount Too High"),
                            body: _.str.sprintf(
                                _t(
                                    "The refunded amount for %s (%s) cannot exceed the original amount (%s)."
                                ),
                                payment_method.name,
                                this.format_currency(Math.abs(amounts_by_method[mid])),
                                this.format_currency(original.amount)
                            ),
                        });
                        return false;
                    }
                }
            }
            if (order.returned_order_id && order.get_due() !== 0) {
                this.gui.show_popup("error", {
                    title: _t("Incomplete Refund"),
                    body: _t(
                        "The total amount of the refund must be exactly the same as the total of the products returned."
                    ),
                });
                return false;
            }
            return this._super(force_validation);
        },
    });

    return {
        ListOrderButtonWidget: ListOrderButtonWidget,
        OrderListScreenWidget: OrderListScreenWidget,
    };
});
