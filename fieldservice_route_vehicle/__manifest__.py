# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Field Service - Route Vehicle (Triple Key)",
    "version": "18.0.1.0.0",
    "summary": "Enforces Day Route creation using Date, Person, and Vehicle.",
    "category": "Field Service",
    "website": "https://github.com/OCA/field-service",
    "author": "APSL-Nagarro, Odoo Community Association (OCA)",
    "maintainers": ["ppyczko"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "fieldservice_route",
        "fieldservice_vehicle",
    ],
    "data": [
        "views/fsm_route_dayroute_view.xml",
    ],
}
