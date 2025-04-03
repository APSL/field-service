# Copyright (C) 2025 Bernat Obrador (APSL - Nagarro) bobrador@apsl.net
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Field Service - Sale Stock From POS",
    "version": "17.0.1.0.0",
    "summary": "Sell stockable items linked to field service orders from POS.",
    "category": "Field Service",
    "author": "APSL- Nagarro, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/field-service",
    "depends": [
        "fieldservice_sale_stock",
        "point_of_sale",
        "pos_order_to_sale_order"
    ],
    "license": "AGPL-3",
    "maintainers": [
        "borbrador",
    ],
    "installable": True,
}
