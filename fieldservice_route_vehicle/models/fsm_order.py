# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class FSMOrder(models.Model):
    _inherit = "fsm.order"

    @api.model
    def _dayroute_trigger_fields(self):
        """Fields whose write must re-evaluate the order's dayroute."""
        return super()._dayroute_trigger_fields() | {"vehicle_id"}

    def prepare_dayroute_values(self, values):
        """Include vehicle_id when preparing values to create a new Day Route."""
        vals = super().prepare_dayroute_values(values)
        vals["vehicle_id"] = values.get("vehicle_id", False)
        return vals

    def _get_dayroute_values(self, vals):
        """Resolve vehicle_id from write/create vals or order record."""
        res = super()._get_dayroute_values(vals)
        vehicle_id = vals.get("vehicle_id")
        if vehicle_id is None:
            vehicle_id = self.vehicle_id.id if self.vehicle_id else False
        res["vehicle_id"] = vehicle_id
        return res

    def _get_dayroute_domain(self, values):
        """Include vehicle_id in the Day Route lookup domain."""
        domain = super()._get_dayroute_domain(values)
        domain.append(("vehicle_id", "=", values.get("vehicle_id", False)))
        return domain

    def _can_create_dayroute(self, values):
        """Require vehicle_id in addition to person_id and date"""
        res = super()._can_create_dayroute(values)
        return res and bool(values.get("vehicle_id"))
