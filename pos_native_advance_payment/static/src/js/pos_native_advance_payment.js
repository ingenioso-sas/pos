odoo.define('pos_native_advance_payment.pos_native_advance_payment', function (require) {
    "use strict";

    var models = require('point_of_sale.models');
    var screens = require('point_of_sale.screens');
    var gui = require('point_of_sale.gui');
    var core = require('web.core');
    var rpc = require('web.rpc');
    var PopupWidget = require('point_of_sale.popups');
    var _t = core._t;

    models.load_fields('res.partner', [
        'pos_advance_balance',
        'advance_payment_allowed',
        'advance_overdraft_limit',
        'advance_credit_used',
        'advance_available',
        'advance_credit_remaining',
    ]);
    models.load_fields('pos.payment.method', ['is_advance_payment']);
    models.load_fields('pos.config', ['pos_deposit_product_id']);

    var original_orders = {}; // cid -> original order, keyed by deposit order cid

    // Custom popup for deposit amount
    var DepositAmountPopup = PopupWidget.extend({
        template: 'DepositAmountPopup',
        show: function (options) {
            options = options || {};
            var self = this;
            this._super(options);
            this.$('input').focus();
            this.$('input').on('keydown', function (e) {
                if (e.which === 13) self.click_confirm();
            });
        },
        click_confirm: function () {
            var value = parseFloat(this.$('input').val()) || 0;
            if (value > 0) {
                this.gui.close_popup();
                if (this.options.confirm) {
                    this.options.confirm(value);
                }
            } else {
                this.gui.show_popup('error', {
                    'title': _t('Monto Inválido'),
                    'body': _t('Debe ingresar un monto mayor a cero.'),
                });
            }
        },
    });

    // Register popup with GUI (use define_popup so it's created in build_widgets)
    gui.define_popup({name: 'deposit_amount', widget: DepositAmountPopup});

    // --- PaymentScreenWidget overrides ---
    screens.PaymentScreenWidget.include({
        init: function (parent, options) {
            this._super(parent, options);
            this.advance_balance = 0.0;
        },
        show: function () {
            var self = this;
            var order = this.pos.get_order();
            var client = order.get_client();

            if (client) {
                rpc.query({
                    model: 'res.partner',
                    method: 'read',
                    args: [[client.id], [
                        'pos_advance_balance',
                        'advance_payment_allowed',
                        'advance_overdraft_limit',
                        'advance_credit_used',
                        'advance_available',
                        'advance_credit_remaining',
                    ]]
                }).then(function (result) {
                    if (result && result.length) {
                        if (result[0].pos_advance_balance !== undefined) {
                            client.pos_advance_balance = result[0].pos_advance_balance;
                            self.advance_balance = result[0].pos_advance_balance;
                        }
                        if (result[0].advance_payment_allowed !== undefined) {
                            client.advance_payment_allowed = result[0].advance_payment_allowed;
                        }
                        if (result[0].advance_overdraft_limit !== undefined) {
                            client.advance_overdraft_limit = result[0].advance_overdraft_limit;
                        }
                        if (result[0].advance_credit_used !== undefined) {
                            client.advance_credit_used = result[0].advance_credit_used;
                        }
                        if (result[0].advance_available !== undefined) {
                            client.advance_available = result[0].advance_available;
                        }
                        if (result[0].advance_credit_remaining !== undefined) {
                            client.advance_credit_remaining = result[0].advance_credit_remaining;
                        }
                        self._refresh_advance_display();
                    }
                });
            }

            if (order.is_deposit_order) {
                this.$('.top-content h1').text(_t('Depósito a Saldo a Favor'));
                this.$('.back').text(_t('Cancelar'));
            }

            this._super();
            this._mark_advance_methods();
        },
        // Info compacta dentro de la casilla: favor y crédito por separado.
        // null sin cliente/datos (la plantilla no reserva altura entonces).
        advance_method_info: function (payment_method) {
            if (!payment_method || !payment_method.is_advance_payment) {
                return null;
            }
            var order = this.pos.get_order();
            var client = order ? order.get_client() : false;
            if (!client || client.pos_advance_balance === undefined ||
                    client.advance_available === undefined) {
                return null;
            }
            var favor = client.pos_advance_balance || 0;
            var remaining_credit = client.advance_credit_remaining;
            if (remaining_credit === undefined) {
                return null;
            }
            return {
                favor_text: _t('Favor: ') + this.format_currency(favor),
                credit_text: _t('Crédito: ') + this.format_currency(remaining_credit),
            };
        },
        _mark_advance_methods: function () {
            var self = this;
            this.$('.paymentmethods .paymentmethod').each(function () {
                var pm = self.pos.payment_methods_by_id[$(this).data('id')];
                if (pm && pm.is_advance_payment) {
                    $(this).addClass('advance-payment-method');
                }
            });
        },
        _advance_tendered: function (target_order) {
            var order = target_order || this.pos.get_order();
            if (!order) return 0;
            var sum = 0;
            var lines = order.get_paymentlines ? order.get_paymentlines() : [];
            for (var i = 0; i < lines.length; i++) {
                if (lines[i].payment_method &&
                    lines[i].payment_method.is_advance_payment) {
                    sum += lines[i].get_amount();
                }
            }
            return sum;
        },
        _refresh_advance_display: function () {
            var container = this.$('.paymentmethods-container');
            if (container.length) {
                container.empty().append(this.render_paymentmethods());
                this._mark_advance_methods();
            }
            this._update_advance_remaining();
        },
        _update_advance_remaining: function () {
            var order = this.pos.get_order();
            var client = order ? order.get_client() : false;
            var box = this.$('.advance-balance-info');
            if (box.length && client && client.advance_payment_allowed) {
                var avail = client.advance_available || 0;
                var remaining = avail - this._advance_tendered();
                box.find('.adv-avail-val').text(this.format_currency(avail));
                box.find('.adv-avail-val').css(
                    'color', avail > 0 ? '#28a745' : '#dc3545');
                var rem = box.find('.adv-remaining-val');
                rem.text(this.format_currency(remaining));
                rem.css('color', remaining >= -0.001 ? '#28a745' : '#dc3545');
            }
            // Semáforo en la casilla: verde normal, rojo si lo digitado
            // con Saldo supera el disponible. Texto en vivo sin re-render.
            var self = this;
            var tendered = this._advance_tendered();
            this.$('.paymentmethods .paymentmethod').each(function () {
                var pm = self.pos.payment_methods_by_id[$(this).data('id')];
                if (!pm || !pm.is_advance_payment) {
                    return;
                }
                var info = self.advance_method_info(pm);
                var small = $(this).find('.advance-method-avail');
                if (info) {
                    if (!small.length) {
                        $(this).append(
                            '<span class="advance-method-avail"></span>');
                        small = $(this).find('.advance-method-avail');
                    }
                    small.text(info.favor_text + ' · ' + info.credit_text);
                } else {
                    small.remove();
                }
                var exceeded = !!client && (tendered - (client.advance_available || 0) > 0.001);
                $(this).toggleClass('advance-exceeded', exceeded);
                $(this).toggleClass('advance-payment-method', !exceeded);
            });
        },
        order_is_valid: function (force_validation) {
            var order = this.pos.get_order();
            if (order.is_deposit_order) {
                var paid = order.get_total_paid();
                var total = order.get_total_with_tax();
                if (paid < total - 0.001) {
                    this.gui.show_popup('error', {
                        'title': _t('Pago Insuficiente'),
                        'body': _t('El monto depositado (') + this.format_currency(paid) +
                                _t(') es menor al monto del depósito (') +
                                this.format_currency(total) + _t(').'),
                    });
                    return false;
                }
                return true;
            }
            // Pre-chequeo local ANTES de encolar/enviar: si falla aquí, la
            // orden nunca entra a la cola de sincronización (nada pendiente,
            // el cajero la corrige en pantalla). El backend revalida todo.
            if (!this._advance_precheck(order)) {
                return false;
            }
            return this._super(force_validation);
        },
        // Valida el uso de Saldo con los datos en caché (sin red).
        // Devuelve false + popup si es inválido; true si pasa o no aplica.
        _advance_precheck: function (order) {
            var tendered = this._advance_tendered();
            if (tendered <= 0.001) {
                return true;
            }
            var client = order.get_client();
            if (!client) {
                this.gui.show_popup('error', {
                    'title': _t('Cliente Requerido'),
                    'body': _t('Debe seleccionar un cliente para usar el método de Saldo a Favor.'),
                });
                return false;
            }
            if (!client.advance_payment_allowed) {
                this.gui.show_popup('error', {
                    'title': _t('Saldo no Habilitado'),
                    'body': _t('El cliente no está habilitado para usar Saldo a Favor en TPV.'),
                });
                return false;
            }
            if (client.advance_available === undefined) {
                return true; // Sin datos frescos: decide el backend.
            }
            if (tendered - client.advance_available > 0.001) {
                this.gui.show_popup('error', {
                    'title': _t('Saldo a Favor Insuficiente'),
                    'body': _t('Solicitado: ') + this.format_currency(tendered) +
                            _t(' | Disponible: ') + this.format_currency(client.advance_available) +
                            _t('. Ajuste el pago o registre un abono.'),
                });
                return false;
            }
            return true;
        },
        // Red de seguridad: si el backend rechaza (lógica, código 200) una
        // orden con Saldo, se saca de la cola de reintentos para que no quede
        // "pendiente" eternamente bloqueando el cierre. Solo negocio, nunca red.
        _handleFailedPushForInvoice: function (order, refresh_screen, error) {
            this._super(order, refresh_screen, error);
            try {
                if (error && error.code === 200 && order &&
                        this._advance_tendered(order) > 0.001) {
                    this.pos.db.remove_order(order.uid);
                    if (!this.pos.db.get_orders().length) {
                        this.pos.set('failed', false);
                    }
                }
            } catch (e) {
                // Jamás romper el manejo de errores del núcleo.
            }
        },
        finalize_validation: function () {
            var order = this.pos.get_order();
            if (order.is_deposit_order) {
                var paymentlines = order.get_paymentlines();
                if (paymentlines.length > 0) {
                    this._finalize_deposit(paymentlines, order.get_client());
                }
                return;
            }
            this._super();
        },
        click_paymentmethods: function (id) {
            var order = this.pos.get_order();
            if (order.is_deposit_order) {
                var payment_method = this.pos.payment_methods_by_id[id];
                if (payment_method.is_advance_payment) {
                    this.gui.show_popup('error', {
                        'title': _t('Método no válido'),
                        'body': _t('No puede usar Saldo a Favor como método de pago para un depósito.'),
                    });
                    return;
                }
            }
            this._super(id);
            // Regla: toda venta con Saldo a Favor se factura (el backend lo
            // exige; se anticipa en UI para que el cajero lo vea).
            var used = this.pos.payment_methods_by_id[id];
            if (used && used.is_advance_payment && !order.is_deposit_order) {
                order.set_to_invoice(true);
            }
            this._update_advance_remaining();
        },
        render_paymentlines: function () {
            this._super();
            this._update_advance_remaining();
        },
        click_back: function () {
            var order = this.pos.get_order();
            if (order.is_deposit_order) {
                var self = this;
                self.gui.show_popup('confirm', {
                    'title': _t('Cancelar Depósito'),
                    'body': _t('¿Está seguro de cancelar este depósito?'),
                    'confirm': function () {
                        self._cancel_deposit(order);
                    },
                });
                return;
            }
            this._super();
        },
        _finalize_deposit: function (paymentlines, client) {
            var self = this;
            var order = this.pos.get_order();

            // Usar el JSON real de la orden (incluye la línea del producto
            // auxiliar): cuadra caja por método como una venta normal y evita
            // el 502 por órdenes con lines=[] y total en 0.
            var json = order.export_as_JSON();
            json.is_advance_deposit = true;
            json.to_invoice = false;
            var deposit_data = {
                data: json,
                to_invoice: false,
                uid: json.uid,
            };

            rpc.query({
                model: 'pos.order',
                method: 'create_from_ui',
                args: [[deposit_data]],
            }).then(function (result) {
                var paid = json.amount_paid || 0;
                self._restore_original_order(order);
                self.gui.show_popup('confirm', {
                    'title': _t('Depósito Exitoso'),
                    'body': _t('Depósito de ') + self.format_currency(paid) + _t(' registrado para ') + client.name,
                    'confirm': function () {
                        self.gui.show_screen('products');
                    },
                });
                rpc.query({
                    model: 'res.partner',
                    method: 'read',
                    args: [[client.id], ['pos_advance_balance']],
                }).then(function (result) {
                    if (result && result.length) {
                        client.pos_advance_balance = result[0].pos_advance_balance;
                    }
                });
            }).catch(function (error) {
                var msg = error;
                if (error && error.message) msg = error.message;
                if (error && error.data && error.data.message) msg = error.data.message;
                self.gui.show_popup('error', {
                    'title': _t('Error al Procesar Depósito'),
                    'body': msg,
                });
            });
        },
        _cancel_deposit: function (deposit_order) {
            this._restore_original_order(deposit_order);
            this.gui.show_screen('products');
        },
        _restore_original_order: function (deposit_order) {
            var orig = original_orders[deposit_order.cid];
            if (orig) {
                var orders = this.pos.get('orders');
                orders.remove(deposit_order);
                this.pos.set('selectedOrder', orig);
                delete original_orders[deposit_order.cid];
            } else {
                this.pos.delete_current_order();
            }
        },
    });

    // Deposit button — added inside ActionpadWidget (always visible area)
    screens.ActionpadWidget.include({
        renderElement: function () {
            this._super.apply(this, arguments);
            if (!this.$('.o_deposit_button').length) {
                this.$el.append(
                    $('<button/>', {
                        'class': 'button o_deposit_button',
                        'text': 'Abonar a Saldo a Favor',
                        'style': 'display: block; width: 100%; height: auto; margin-top: 5px; padding: 8px 5px; background: #17a2b8; border: 1px solid #138496; color: white; border-radius: 3px; font-size: 13px; cursor: pointer;',
                    })
                );
            }
            this.$('.o_deposit_button').off('click.deposit');
            this.$('.o_deposit_button').on('click.deposit', this.proxy('_on_deposit_click'));
        },
        _on_deposit_click: function () {
            var order = this.pos.get_order();
            var client = order.get_client();
            if (!client) {
                this.gui.show_popup('error', {
                    'title': _t('Cliente Requerido'),
                    'body': _t('Debe seleccionar un cliente antes de hacer un depósito a saldo a favor.'),
                });
                return;
            }
            if (order.get_orderlines().length > 0) {
                this.gui.show_popup('confirm', {
                    'title': _t('Orden con Productos'),
                    'body': _t('El depósito se procesará como una orden separada. La orden actual no se verá afectada. ¿Desea continuar?'),
                    'confirm': this.proxy('_show_deposit_popup'),
                });
                return;
            }
            this._show_deposit_popup();
        },
        _show_deposit_popup: function () {
            var self = this;
            var client = this.pos.get_order().get_client();
            var clientName = client ? client.name : '';
            this.gui.show_popup('deposit_amount', {
                'title': _t('Depósito a Saldo a Favor'),
                'body': _t('Monto a depositar para ') + clientName,
                'confirm': function (amount) {
                    self._process_deposit(amount);
                },
            });
        },
        _process_deposit: function (amount) {
            var order = this.pos.get_order();
            var client = order.get_client();

            // Producto auxiliar: la orden lleva 1 línea (servicio, sin stock)
            // para cuadrar caja por método como venta normal.
            var cfg_product = this.pos.config.pos_deposit_product_id;
            var product_id = cfg_product && cfg_product[0] ? cfg_product[0] : cfg_product;
            var product = product_id ? this.pos.db.get_product_by_id(product_id) : false;
            if (!product) {
                this.gui.show_popup('error', {
                    'title': _t('Sin Producto de Depósito'),
                    'body': _t('No se cargó el producto auxiliar de depósito. Configure Ajustes > Punto de Venta > Anticipos y recargue el TPV.'),
                });
                return;
            }

            var deposit_order = this.pos.add_new_order();
            deposit_order.set_client(client);
            deposit_order.is_deposit_order = true;
            deposit_order.temporary = true;

            deposit_order.add_product(product, {quantity: 1, merge: false});
            var line = deposit_order.get_last_orderline();
            if (line) {
                line.set_unit_price(amount);
            }

            // Store reference to original order so we can restore it later
            original_orders[deposit_order.cid] = order;

            // Go to payment screen so user can select payment method
            // (efectivo/banco: queda en caja/extracto de la sesión)
            this.gui.show_screen('payment');
        },
    });

    // Open advance history in backend when button clicked
    $(document).on('click', '.o_advance_history_btn', function () {
        var partnerId = $(this).data('partner-id');
        if (!partnerId) return;
        rpc.query({
            model: 'res.partner',
            method: 'action_pos_advance_history',
            args: [[partnerId]],
        }).then(function (result) {
            if (!result) return;
            var url = '/web#action=' + encodeURIComponent(JSON.stringify(result));
            window.open(url, '_blank');
        });
    });

    // Highlight advance payment methods in the payment screen
    var _PaymentMethodButton = screens.PaymentMethodButton;
    if (_PaymentMethodButton) {
        _PaymentMethodButton.include({
            render: function () {
                this._super();
                if (this.payment_method.is_advance_payment) {
                    this.$el.addClass('advance-payment-method');
                }
            }
        });
    }
});
