# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import api, models


class FSMOrder(models.Model):
    _inherit = "fsm.order"

    @api.model
    def create(self, vals):
        location = self.env["fsm.location"].browse(vals.get("location_id"))

        # Check if a person_id is provided and assign one to generate dayroute
        if not vals.get("person_id") and location.fsm_route_id.fsm_person_id:
            vals.update({"person_id": location.fsm_route_id.fsm_person_id.id})

        return super().create(vals)
