# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    fsm_dayroute_id = fields.Many2one(
        "fsm.route.dayroute",
        related="fsm_order_id.dayroute_id",
        string="Day Route",
        store=True,
    )
