# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent consulting Services
# Copyright 2025 Patryk Pyczko (APSL-Nagarro)<ppyczko@apsl.net>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class FSMRouteDayRoute(models.Model):
    _name = "fsm.route.dayroute"
    _description = "Field Service Route Dayroute"

    name = fields.Char(required=True, copy=False, default=lambda self: _("New"))
    person_id = fields.Many2one(
        comodel_name="fsm.person",
        string="Person",
        compute="_compute_person_id",
        store=True,
        readonly=False,
    )
    route_id = fields.Many2one(comodel_name="fsm.route", string="Route")
    date = fields.Date(required=True)
    team_id = fields.Many2one(
        comodel_name="fsm.team",
        string="Team",
        default=lambda self: self._default_team_id(),
    )
    stage_id = fields.Many2one(
        comodel_name="fsm.stage",
        string="Stage",
        domain="[('stage_type', '=', 'route')]",
        index=True,
        copy=False,
        default=lambda self: self._default_stage_id(),
    )
    longitude = fields.Float()
    latitude = fields.Float()
    last_location_id = fields.Many2one(
        comodel_name="fsm.location", string="Last Location"
    )
    date_start_planned = fields.Datetime(
        string="Planned Start Time",
        compute="_compute_date_start_planned",
        store=True,
        readonly=False,
    )
    start_location_id = fields.Many2one(
        comodel_name="fsm.location", string="Start Location"
    )
    end_location_id = fields.Many2one(
        comodel_name="fsm.location", string="End Location"
    )
    work_time = fields.Float(string="Time before overtime (in hours)", default=8.0)
    max_allow_time = fields.Float(
        string="Maximal Allowable Time (in hours)", default=10.0
    )
    order_ids = fields.One2many(
        comodel_name="fsm.order", inverse_name="dayroute_id", string="Orders"
    )
    order_count = fields.Integer(
        compute="_compute_order_count", string="Number of Orders", store=True
    )
    order_remaining = fields.Integer(
        compute="_compute_order_count", string="Available Capacity", store=True
    )
    max_order = fields.Integer(
        related="route_id.max_order",
        string="Maximum Capacity",
        store=True,
        help="Maximum numbers of orders that can be added to this day route.",
    )

    def _default_team_id(self):
        teams = self.env["fsm.team"].search(
            [("company_id", "in", (self.env.user.company_id.id, False))],
            order="sequence asc",
            limit=1,
        )
        if teams:
            return teams
        else:
            raise ValidationError(_("You must create a FSM team first."))

    def _default_stage_id(self):
        return self.env["fsm.stage"].search(
            [("stage_type", "=", "route"), ("is_default", "=", True)], limit=1
        )

    @api.depends("route_id", "order_ids", "max_order")
    def _compute_order_count(self):
        for rec in self:
            rec.order_count = len(rec.order_ids)
            rec.order_remaining = rec.max_order - rec.order_count

    @api.depends("route_id", "route_id.fsm_person_id")
    def _compute_person_id(self):
        for rec in self:
            if not rec.route_id.fsm_person_id:
                rec.person_id = None
                continue

            rec.person_id = rec.route_id.fsm_person_id

    @api.depends("date")
    def _compute_date_start_planned(self):
        for rec in self:
            if not rec.date:
                rec.date_start_planned = None
                continue

            # TODO: Use the worker timezone and working schedule
            rec.date_start_planned = datetime.combine(
                rec.date, datetime.strptime("8:00:00", "%H:%M:%S").time()
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "fsm.route.dayroute"
                ) or _("New")
            if not vals.get("date_start_planned", False) and vals.get("date", False):
                # TODO: Use the worker timezone and working schedule
                date = vals.get("date")
                if isinstance(vals.get("date"), str):
                    date = datetime.strptime(
                        vals.get("date"), DEFAULT_SERVER_DATE_FORMAT
                    ).date()
                vals.update(
                    {
                        "date_start_planned": datetime.combine(
                            date, datetime.strptime("8:00:00", "%H:%M:%S").time()
                        )
                    }
                )
        return super().create(vals_list)

    @api.constrains("date", "route_id")
    def check_day(self):
        for rec in self:
            if rec.date and rec.route_id:
                # Get the day of the week: Monday -> 0, Sunday -> 6
                day_index = rec.date.weekday()
                day = self.env.ref("fieldservice_route.fsm_route_day_" + str(day_index))
                if day.id not in rec.route_id.day_ids.ids:
                    raise ValidationError(
                        _("The route %(route_name)s does not run on %(name)s!")
                        % {"route_name": rec.route_id.name, "name": day.name}
                    )

    @api.constrains("route_id", "max_order", "order_count")
    def check_capacity(self):
        for rec in self:
            if rec.route_id and rec.max_order and rec.order_count > rec.max_order:
                raise ValidationError(
                    _(
                        "The day route is exceeding the maximum number of "
                        "orders of the route."
                    )
                )

    # ---------------------------------------------------------
    # Extensible Hook Architecture for Day Route Sync & Fusion
    # ---------------------------------------------------------

    @api.constrains("date", "person_id", "route_id")
    def _check_dayroute_uniqueness(self):
        for rec in self:
            if rec.date and rec.person_id:
                domain = rec._get_dayroute_search_domain()
                if self.search_count(domain):
                    raise ValidationError(
                        _(
                            "A Day Route already exists for this Date, Person, "
                            "and Route combination."
                        )
                    )

    @api.model
    def _get_dayroute_key_fields(self):
        """Set of fields defining a unique dayroute key."""
        return {"date", "person_id", "route_id"}

    def _is_dayroute_complete(self, vals=None):
        """Check if all required key fields are set."""
        self.ensure_one()
        date_val = vals.get("date") if vals and "date" in vals else self.date
        person_val = (
            vals.get("person_id")
            if vals and "person_id" in vals
            else (self.person_id.id if self.person_id else False)
        )
        return bool(date_val and person_val)

    def _get_dayroute_search_domain(self, vals=None):
        """Build domain to search for overlapping dayroutes with available capacity."""
        self.ensure_one()
        date_val = vals.get("date") if vals and "date" in vals else self.date
        person_val = (
            vals.get("person_id")
            if vals and "person_id" in vals
            else (self.person_id.id if self.person_id else False)
        )
        route_val = (
            vals.get("route_id")
            if vals and "route_id" in vals
            else (self.route_id.id if self.route_id else False)
        )
        return [
            ("date", "=", date_val),
            ("person_id", "=", person_val),
            ("route_id", "=", route_val),
            ("id", "!=", self.id),
            "|",
            ("max_order", "=", 0),
            ("order_remaining", ">", 0),
        ]

    def _prepare_order_sync_vals(self, vals=None):
        """Prepare dict of values to push down to assigned orders."""
        self.ensure_one()
        res = {}
        if vals and "person_id" in vals:
            res["person_id"] = vals["person_id"]
        return res

    def write(self, vals):
        key_fields = self._get_dayroute_key_fields()
        if not key_fields.intersection(vals):
            return super(
                FSMRouteDayRoute, self.with_context(skip_unlink_removable=True)
            ).write(vals)

        fused_records = self.env["fsm.route.dayroute"]
        new_date_obj = fields.Date.to_date(vals["date"]) if "date" in vals else False

        for dayroute in self:
            sync_vals = dayroute._prepare_order_sync_vals(vals)

            # If key incomplete (e.g. person cleared), unassign orders without fusion
            if not dayroute._is_dayroute_complete(vals):
                if sync_vals:
                    dayroute.order_ids.with_context(
                        skip_dayroute_sync=True, skip_unlink_removable=True
                    ).write(sync_vals)
                continue

            # Check if another dayroute already exists matching the new parameters
            existing = self.search(dayroute._get_dayroute_search_domain(vals), limit=1)
            if existing:
                sync_vals["dayroute_id"] = existing.id
                fused_records |= dayroute

            # Push all changes (person, dayroute, and date) in a SINGLE pass per order
            for order in dayroute.order_ids:
                order_upd = dict(sync_vals)
                if new_date_obj and order.scheduled_date_start:
                    order_upd["scheduled_date_start"] = datetime.combine(
                        new_date_obj, order.scheduled_date_start.time()
                    )
                if order_upd:
                    order.with_context(
                        skip_dayroute_sync=True, skip_unlink_removable=True
                    ).write(order_upd)

        if fused_records:
            fused_records.unlink()

        recs_to_write = self - fused_records
        return (
            super(
                FSMRouteDayRoute, recs_to_write.with_context(skip_unlink_removable=True)
            ).write(vals)
            if recs_to_write
            else True
        )

    def unlink(self):
        for rec in self:
            if any(order.is_closed for order in rec.order_ids):
                raise UserError(
                    _(
                        "You cannot delete a Day Route that contains "
                        "completed or closed orders."
                    )
                )
            # Clear person_id on open orders so they return to unassigned pool cleanly
            rec.order_ids.with_context(skip_dayroute_sync=True).write(
                {"person_id": False, "dayroute_id": False}
            )
        return super().unlink()

    def _is_removable(self):
        """Whether this (now possibly empty) dayroute can be deleted."""
        self.ensure_one()
        return not self.order_ids

    def _unlink_removable(self):
        """Delete the subset of ``self`` that ``_is_removable()``."""
        return self.exists().filtered(lambda r: r._is_removable()).unlink()
