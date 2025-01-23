# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    commitment_date_end = fields.Datetime(
        string="Delivery End Date",
        copy=False,
        states={"done": [("readonly", True)], "cancel": [("readonly", True)]},
        help="This is the delivery deadline date promised to the customer. "
        "If set, the delivery order will be scheduled based on "
        "this date rather than product lead times.",
    )

    @api.onchange("partner_shipping_id", "partner_id", "company_id")
    def onchange_partner_shipping_id(self):
        super().onchange_partner_shipping_id()

        if self.partner_shipping_id.fsm_location_id:
            self.sudo().write(
                {"fsm_location_id": self.partner_shipping_id.fsm_location_id}
            )

        return {}

    def action_confirm(self):
        res = super().action_confirm()

        for order in self:
            if order.commitment_date_end:
                order.order_line.move_ids.date_deadline = order.commitment_date_end

        return res

    def _prepare_fsm_values(self, **kwargs):
        res = super()._prepare_fsm_values(**kwargs)

        fsm_date_values = {
            "request_early": self.commitment_date or self.expected_date,
            "scheduled_date_start": self.commitment_date or self.expected_date,
            "scheduled_date_end": self.commitment_date_end
            or self.commitment_date
            or self.expected_date,
        }

        res.update(fsm_date_values)

        return res

    def write(self, values):
        res = super().write(values)

        for picking in self.picking_ids.filtered(
            lambda r: r.state not in ["done", "cancel"]
        ):
            picking.write(
                {
                    "scheduled_date": self.commitment_date or self.expected_date,
                    "date_deadline": self.commitment_date_end
                    or self.commitment_date
                    or self.expected_date,
                }
            )
            picking.move_lines.date_deadline = (
                self.commitment_date_end or self.commitment_date or self.expected_date
            )

        for fsm_order in self.fsm_order_ids.filtered(lambda r: not r.is_closed):
            fsm_order.write(
                {
                    "request_early": self.commitment_date or self.expected_date,
                    "scheduled_date_start": self.commitment_date or self.expected_date,
                    "scheduled_date_end": self.commitment_date_end
                    or self.commitment_date
                    or self.expected_date,
                }
            )

        return res
