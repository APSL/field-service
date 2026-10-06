# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FSMRouteDayRoute(models.Model):
    _inherit = "fsm.route.dayroute"

    vehicle_id = fields.Many2one(
        comodel_name="fsm.vehicle",
        string="Vehicle",
        index=True,
    )

    @api.model
    def _get_dayroute_key_fields(self):
        """Extend dayroute key fields to include vehicle_id."""
        return super()._get_dayroute_key_fields() | {"vehicle_id"}

    def _is_dayroute_complete(self, vals=None):
        """Require date, person_id, AND vehicle_id for key completeness (Model 2)."""
        complete = super()._is_dayroute_complete(vals)
        vehicle_val = (
            vals.get("vehicle_id")
            if vals and "vehicle_id" in vals
            else (self.vehicle_id.id if self.vehicle_id else False)
        )
        return complete and bool(vehicle_val)

    def _get_dayroute_search_domain(self, vals=None):
        """Include vehicle_id in overlapping Day Route search domain."""
        domain = super()._get_dayroute_search_domain(vals)
        self.ensure_one()
        vehicle_val = (
            vals.get("vehicle_id")
            if vals and "vehicle_id" in vals
            else (self.vehicle_id.id if self.vehicle_id else False)
        )
        domain.append(("vehicle_id", "=", vehicle_val))
        return domain

    def _prepare_order_sync_vals(self, vals=None):
        """Prepare vehicle_id to push down to assigned orders."""
        res = super()._prepare_order_sync_vals(vals)
        if vals and "vehicle_id" in vals:
            res["vehicle_id"] = vals["vehicle_id"]
        return res
