{
    "name": "Partner Info in POS",
    "summary": """Campos adicionales de los clientes en el punto de venta""",
    "description": """
        Este módulo fue escrito para extender la funcionalidad de Odoo para los datos de los cleintes, por ejemplo de fecha de nacimiento y la identificación de los clientes, en el formulario de cliente convencional y en el punto de venta.
    """,
    "author": "Anderson Buitron",
    "website": "https://github.com/OCA/pos",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Point of Sale",
    "version": "1.0",
    # any module necessary for this one to work correctly
    "depends": ["account", "point_of_sale"],
    # always loaded
    "data": ["views/views.xml", "views/assets.xml",],
    "qweb": ["static/src/xml/pos.xml"],
}
