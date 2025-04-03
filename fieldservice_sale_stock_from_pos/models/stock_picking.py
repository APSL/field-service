from odoo import models

from itertools import groupby
from collections import defaultdict


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _create_move_from_pos_order_lines(self, lines):
        """
        Create picking for POS orders with Field Service Management (FSM) products.

        This method handles stock moves for POS orders with FSM products, considering two scenarios:
        1. Non-real-time stock quantity updates: Create separate pickings for each order
        2. Real-time stock quantity updates: Create stock moves directly

        Key considerations:
        - Splits lines by order ID
        - Handles products requiring field service tracking
        - Creates pickings or stock moves based on configuration
        
        TODO:
        Now does not take in account if the product has to Create one FSM order per sale order line
        """
        self.ensure_one()

        orders_dict = defaultdict(list)
        for line in lines:
            orders_dict[line.order_id.id].append(line)

        processed_lines = set()

        for _, order_lines in orders_dict.items():
            pos_order = order_lines[0].order_id
            
            # Check if any product in the order requires field service tracking
            fsm_products = any(
                line.product_id.field_service_tracking != "no" for line in pos_order.lines
            )
            sale_order = order_lines[0].sale_order_origin_id if order_lines else None

            if (
                fsm_products
                and sale_order
                and not self._is_update_stock_quantities_real_time(
                    pos_order.config_id.id
                )
            ):
                # Create separate picking for non-real-time stock updates
                picking = self._create_picking_for_pos_order(pos_order, order_lines)
                # Link picking to FSM order if exists
                fsm_order = self._get_fsm_order_from_sale_order(sale_order)
                if fsm_order:
                    self._link_picking_to_fsm_order(picking, fsm_order)

                processed_lines.update(order_lines)
            elif fsm_products and sale_order:
                # For real-time stock updates, create stock moves directly
                lines_by_product = groupby(
                    sorted(order_lines, key=lambda l: l.product_id.id),
                    key=lambda l: l.product_id.id,
                )
                move_vals = []
                for dummy, olines in lines_by_product:
                    pos_order_lines = self.env["pos.order.line"].concat(*olines)
                    move_vals.append(
                        self._prepare_stock_move_vals(pos_order_lines[0], pos_order_lines)
                    )

                # Create moves without immediate validation (to be validated by FSM order)
                moves = self.env["stock.move"].create(move_vals)
                moves._add_mls_related_to_order(pos_order_lines, are_qties_done=True)
                self._link_owner_on_return_picking(pos_order_lines)
                processed_lines.update(order_lines)

        remaining_lines = [line for line in lines if line not in processed_lines]
        # Process remaining lines using the parent method
        if remaining_lines:
            return super()._create_move_from_pos_order_lines(remaining_lines)

        return None

    def _create_picking_for_pos_order(self, pos_order, order_lines):
        """
        Create a stock picking for a specific POS order.

        Args:
            pos_order (pos.order): The POS order to create picking for
            order_lines (recordset): Order lines to include in the picking

        Returns:
            stock.picking: Created stock picking
        """
        picking = self.env["stock.picking"].create(
            {
                "partner_id": pos_order.partner_id.id,
                "origin": pos_order.name,
                "location_id": self.location_id.id,
                "location_dest_id": self.location_dest_id.id,
                "picking_type_id": self.picking_type_id.id,
                "pos_order_id": pos_order.id,
                "company_id": pos_order.company_id.id,
            }
        )

        for line in order_lines:
            if line.product_id.type == "service":
                continue
            self.env["stock.move"].create(
                {
                    "name": line.product_id.name,
                    "picking_id": picking.id,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.qty,
                    "product_uom": line.product_id.uom_id.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                    "company_id": pos_order.company_id.id,
                }
            )

        return picking

    def _get_fsm_order_from_sale_order(self, sale_order):
        if not sale_order:
            return None
        return self.env["fsm.order"].search([("sale_id", "=", sale_order.id)], limit=1)

    def _link_picking_to_fsm_order(self, picking, fsm_order):
        picking.write({"fsm_order_id": fsm_order.id})
        for move in picking.move_ids:
            move.write({"fsm_order_id": fsm_order.id})

    def _is_update_stock_quantities_real_time(self, config_id):
        """
        Check if stock quantities are updated in real-time for a given POS configuration.
        """
        return (
            self.env["res.config.settings"]
            .sudo()
            .search([("pos_config_id", "=", config_id)], limit=1)
            .update_stock_quantities
            == "real"
        )
