# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent consulting Services
# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import datetime

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class FSMOrder(models.Model):
    _inherit = "fsm.order"

    dayroute_id = fields.Many2one(
        comodel_name="fsm.route.dayroute", string="Day Route", index=True
    )
    fsm_route_id = fields.Many2one(related="location_id.fsm_route_id", string="Route")

    person_id = fields.Many2one(
        comodel_name="fsm.person",
        string="Assigned To",
        index=True,
        compute="_compute_person_id",
        store=True,
        readonly=False,
    )

    @api.depends("fsm_route_id")
    def _compute_person_id(self):
        for item in self.filtered("fsm_route_id"):
            item.person_id = item.fsm_route_id.fsm_person_id

    def prepare_dayroute_values(self, values):
        return {
            "person_id": values["person_id"],
            "date": values["date"],
            "route_id": values["route_id"],
        }

    def _get_dayroute_values(self, vals):
        date = False
        if vals.get("scheduled_date_start"):
            if isinstance(vals.get("scheduled_date_start"), str):
                date = datetime.strptime(
                    vals.get("scheduled_date_start"), DEFAULT_SERVER_DATETIME_FORMAT
                ).date()
            elif isinstance(vals.get("scheduled_date_start"), datetime):
                date = vals.get("scheduled_date_start").date()
        return {
            "person_id": vals.get("person_id")
            or self.person_id.id
            or self.fsm_route_id.fsm_person_id.id,
            "date": date or self.scheduled_date_start.date(),
            "route_id": vals.get("fsm_route_id") or self.fsm_route_id.id,
        }

    def _get_dayroute_domain(self, values):
        return [
            ("person_id", "=", values["person_id"]),
            ("date", "=", values["date"]),
            ("route_id", "=", values["route_id"]),
            "|",
            ("max_order", "=", 0),
            ("order_remaining", ">", 0),
        ]

    def _can_create_dayroute(self, values):
        return values["person_id"] and values["date"]

    def _manage_fsm_route(self, vals):
        dayroute_obj = self.env["fsm.route.dayroute"]
        values = self._get_dayroute_values(vals)
        domain = self._get_dayroute_domain(values)
        dayroute = dayroute_obj.search(domain, limit=1)
        if dayroute:
            vals.update({"dayroute_id": dayroute.id})
        else:
            if self._can_create_dayroute(values):
                dayroute = dayroute_obj.create(self.prepare_dayroute_values(values))
                vals.update({"dayroute_id": dayroute.id})
        return vals

    @api.model
    def _dayroute_trigger_fields(self):
        """Fields whose write must re-evaluate the order's dayroute."""
        return {"person_id", "scheduled_date_start"}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("fsm_route_id") and vals.get("location_id"):
                location = self.env["fsm.location"].browse(vals["location_id"])
                vals.update({"fsm_route_id": location.fsm_route_id.id})

            if vals.get("person_id") and vals.get("scheduled_date_start"):
                vals = self._manage_fsm_route(vals)
        return super().create(vals_list)

    def write(self, vals):
        skip_sync = self.env.context.get("skip_dayroute_sync")

        # Top-down sync: Manually setting or clearing dayroute_id on an order
        if "dayroute_id" in vals and not skip_sync:
            if vals["dayroute_id"]:
                dayroute = self.env["fsm.route.dayroute"].browse(vals["dayroute_id"])
                vals["person_id"] = (
                    dayroute.person_id.id if dayroute.person_id else False
                )
            else:
                vals["person_id"] = False

        if (
            not self._dayroute_trigger_fields() & vals.keys()
            and "dayroute_id" not in vals
        ):
            return super().write(vals)

        old_dayroutes = self.dayroute_id
        for rec in self:
            rec_vals = dict(vals)

            # Case A: Manual attachment to a Day Route -> Synchronize schedule date
            if "dayroute_id" in rec_vals and not skip_sync:
                if rec_vals["dayroute_id"]:
                    dayroute = self.env["fsm.route.dayroute"].browse(
                        rec_vals["dayroute_id"]
                    )
                    if dayroute.date:
                        old_time = (
                            rec.scheduled_date_start or fields.Datetime.now()
                        ).time()
                        rec_vals["scheduled_date_start"] = datetime.combine(
                            dayroute.date, old_time
                        )

            # Case B: Bottom-up automatic Day Route management when person or
            # date changes
            elif not skip_sync:
                unassigning = any(
                    field in rec_vals and not rec_vals[field]
                    for field in self._dayroute_trigger_fields()
                )
                if unassigning:
                    rec_vals["dayroute_id"] = False
                elif (rec_vals.get("person_id") or rec.person_id) and (
                    rec_vals.get("scheduled_date_start") or rec.scheduled_date_start
                ):
                    rec_vals = rec._manage_fsm_route(rec_vals)

            super(FSMOrder, rec).write(rec_vals)

        if not self.env.context.get("skip_unlink_removable"):
            old_dayroutes._unlink_removable()

        return True
