odoo.define('pos_partner.models',
    function(require, factory) {
        'use strict';
        var models = require('point_of_sale.models');
        models.load_fields('res.partner', ['fecha_nac','identificacion']);
    }
);
