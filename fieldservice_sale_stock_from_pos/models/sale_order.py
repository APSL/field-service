from odoo import models, api


class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    def _link_pickings_to_fsm(self):
        # If the sale order is not linked to a POS order, we proceed as usual
        if not any(rec.pos_order_line_ids for rec in self):
            return super()._link_pickings_to_fsm()
    
        for rec in self:
            fsm_order = self.env["fsm.order"].search(
                [
                    ("sale_id", "=", rec.id),
                    ("sale_line_id", "=", False),
                ]
            )
            if rec.procurement_group_id:
                rec.procurement_group_id.fsm_order_id = fsm_order.id or False
            # Link the pos_order pickings to the fsm_order
            for picking in rec.pos_order_line_ids[0].order_id.picking_ids:
                picking.write(rec.prepare_fsm_values_for_stock_picking(fsm_order))
                picking.action_confirm()
                for move in picking.move_ids:
                    move.write(rec.prepare_fsm_values_for_stock_move(fsm_order))

    @api.depends("partner_id", "partner_shipping_id")
    def _compute_fsm_location_id(self):
        res = super()._compute_fsm_location_id()
        for so in self:
            # Create the partner location automatically if it does not exist
            if not so.fsm_location_id:
                if not so.partner_id.fsm_location:
                    self.env["fsm.wizard"].action_convert_location(self.partner_id)
                so.fsm_location_id = self.partner_id.fsm_location_id
        return res
