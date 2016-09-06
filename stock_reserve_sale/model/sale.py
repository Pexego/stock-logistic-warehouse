# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Guewen Baconnier
#    Copyright 2013 Camptocamp SA
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import orm, fields
from openerp.tools.translate import _


class sale_order(orm.Model):
    _inherit = 'sale.order'

    def _stock_reservation(self, cr, uid, ids, fields, args, context=None):
        result = {}
        for order_id in ids:
            result[order_id] = {'has_stock_reservation': False,
                                'is_stock_reservable': False}
        for sale in self.browse(cr, uid, ids, context=context):
            for line in sale.order_line:
                if line.reservation_ids:
                    result[sale.id]['has_stock_reservation'] = True
                if line.is_stock_reservable:
                    result[sale.id]['is_stock_reservable'] = True
            if sale.state not in ('draft', 'sent'):
                result[sale.id]['is_stock_reservable'] = False
        return result

    _columns = {

        'state': fields.selection([
            ('draft', 'Draft Quotation'),
            ('sent', 'Quotation Sent'),
            ('reserve', 'Reserved'),
            ('cancel', 'Cancelled'),
            ('waiting_date', 'Waiting Schedule'),
            ('progress', 'Sales Order'),
            ('manual', 'Sale to Invoice'),
            ('shipping_except', 'Shipping Exception'),
            ('invoice_except', 'Invoice Exception'),
            ('done', 'Done'),
            ], 'Status', readonly=True, help="Gives the status of the quotation or sales order.\
              \nThe exception status is automatically set when a cancel operation occurs \
              in the invoice validation (Invoice Exception) or in the picking list process (Shipping Exception).\nThe 'Waiting Schedule' status is set when the invoice is confirmed\
               but waiting for the scheduler to run on the order date.", select=True),
        'reservation_paused': fields.boolean('Reservation paused'),
        'order_line': fields.one2many('sale.order.line', 'order_id', 'Order Lines', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'reserve': [('readonly', False)]}, copy=True),
        'partner_id': fields.many2one('res.partner', 'Customer', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'reserve': [('readonly', False)]}, required=True, change_default=True, select=True, track_visibility='always'),
        'partner_invoice_id': fields.many2one('res.partner', 'Invoice Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'reserve': [('readonly', False)]}, help="Invoice address for current sales order."),
        'partner_shipping_id': fields.many2one('res.partner', 'Delivery Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'reserve': [('readonly', False)]}, help="Delivery address for current sales order."),
        'picking_policy': fields.selection([('direct', 'Deliver each product when available'), ('one', 'Deliver all products at once')],
            'Shipping Policy', required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'reserve': [('readonly', False)]},
            help="""Pick 'Deliver each product when available' if you allow partial delivery."""),
        'order_policy': fields.selection([
                ('manual', 'On Demand'),
                ('picking', 'On Delivery Order'),
                ('prepaid', 'Before Delivery'),
            ], 'Create Invoice', required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'reserve': [('readonly', False)]},
            help="""On demand: A draft invoice can be created from the sales order when needed. \nOn delivery order: A draft invoice can be created from the delivery order when the products have been delivered. \nBefore delivery: A draft invoice is created from the sales order and must be paid before the products can be delivered."""),
    }

    def create(self, cr, uid, vals, context=None):
        id = super(sale_order, self).create(cr, uid, vals, context=context)
        if self.browse(cr, uid, id,
                       context=context).state in ['reserve', ]:
            self.order_reserve(cr, uid, [id])
        return id

    def order_reserve(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'reserve'})
        line_ids = [line.id for order in self.browse(cr, uid, ids, context=context) for line in order.order_line if line.product_id and line.product_id.type != "service"]
        self.pool.get('sale.order.line').stock_reserve(cr, uid, line_ids, context=context)
        return True

    def release_all_stock_reservation(self, cr, uid, ids, context=None):
        sales = self.browse(cr, uid, ids, context=context)
        line_ids = [line.id for sale in sales for line in sale.order_line]
        line_obj = self.pool.get('sale.order.line')
        line_obj.release_stock_reservation(cr, uid, line_ids, context=context)
        return True

    def action_ship_create(self, cr, uid, ids, context=None):
        res = super(sale_order, self).action_ship_create(
            cr, uid, ids, context=context)
        sale_obj = self.browse(cr, uid, ids[0])
        sale_obj.release_all_stock_reservation()
        picking_ids = [pick.id for pick in sale_obj.picking_ids
                       if pick.picking_type_code == "outgoing"
                       and pick.state != "cancel"]
        if picking_ids:
            self.pool.get('stock.picking').action_assign(cr, uid, picking_ids)
        return res

    def get_reservations(self, cr, uid, ids, context=None):
        sales = self.browse(cr, uid, ids, context=context)
        line_ids = [line.id for sale in sales for line in sale.order_line]
        lines = self.pool.get('sale.order.line').browse(cr, uid, line_ids, context=context)
        reserv_ids = [reserv.id for line in lines
                      for reserv in line.reservation_ids]
        return reserv_ids

    def action_cancel(self, cr, uid, ids, context=None):
        self.release_all_stock_reservation(cr, uid, ids, context=context)
        return super(sale_order, self).action_cancel(
            cr, uid, ids, context=context)


    def get_product_ids(self, cr, uid, ids, context=None):
        sales = self.browse(cr, uid, ids, context=context)
        product_ids = [line.product_id.id for sale in sales for line in sale.order_line]
        return  product_ids


    def open_stock_reservation(self, cr, uid, ids, context=None):
        assert len(ids) == 1, "Expected 1 ID, got %r" % ids
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        get_ref = mod_obj.get_object_reference
        __, action_id = get_ref(cr, uid, 'stock_reserve',
                                'action_stock_reservation')
        product_ids = self.get_product_ids(cr, uid, ids)
        action = act_obj.read(cr, uid, action_id, context=context)
        action['domain'] = [('sale_id', 'in', ids)]
        action['context'] = {'search_default_draft': 1,
                             'search_default_reserved': 1,
                             'search_default_waiting': 1,
                            }
        return action

    def print_quotation(self, cr, uid, ids, context=None):
        sale = self.browse(cr, uid, ids[0], context=context)
        if sale.state == 'draft':
            self.signal_workflow(cr, uid, ids, 'quotation_sent')
        return self.pool['report'].get_action(cr, uid, ids, 'sale.report_saleorder', context=context)

    def _prepare_order_line_procurement(self, cr, uid, order, line, group_id=False, context=None):
        vals = super(sale_order, self)._prepare_order_line_procurement(cr, uid, order, line, group_id=group_id, context=context)
        vals['reservation_paused'] = order.reservation_paused
        return vals

    def write(self, cr, uid, ids, vals, context=None):
        res = super(sale_order, self).write(cr, uid, ids, vals, context=context)
        if 'reservation_paused' in vals:
            procurements = {}
            for order in self.browse(cr, uid, ids):
                if order.procurement_group_id:
                    self.pool.get('procurement.order').\
                        write(cr, uid, [x.id for x in order.procurement_group_id.procurement_ids], {'reservation_paused': vals['reservation_paused']})
        return res


class sale_order_line(orm.Model):
    _inherit = 'sale.order.line'

    def _is_stock_reservable(self, cr, uid, ids, fields, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context):
            if line.product_id and \
                    line.product_id.type in ['consu', 'service']:
                res[line.id] = False
                continue
            res[line.id] = True
        return res


    _columns = {
        'reservation_ids': fields.one2many(
            'stock.reservation',
            'sale_line_id',
            string='Stock Reservation'),
        'is_stock_reservable': fields.function(
            _is_stock_reservable,
            type='boolean',
            readonly=True,
            string='Can be reserved'),
    }

    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default['reservation_ids'] = False
        return super(sale_order_line, self).copy_data(
            cr, uid, id, default=default, context=context)

    def release_stock_reservation(self, cr, uid, ids, context=None):
        lines = self.browse(cr, uid, ids, context=context)
        reserv_ids = [reserv.id for line in lines
                      for reserv in line.reservation_ids]
        reserv_obj = self.pool.get('stock.reservation')
        reserv_obj.release(cr, uid, reserv_ids, context=context)
        return True

    # def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
    #                       uom=False, qty_uos=0, uos=False, name='', partner_id=False,
    #                       lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False, context=None):
    #     result = super(sale_order_line, self).product_id_change(
    #         cr, uid, ids, pricelist, product, qty=qty, uom=uom,
    #         qty_uos=qty_uos, uos=uos, name=name, partner_id=partner_id,
    #         lang=lang, update_tax=update_tax, date_order=date_order,
    #         packaging=packaging, fiscal_position=fiscal_position,
    #         flag=flag, context=context)
    #     if not ids:  # warn only if we change an existing line
    #         return result
    #     assert len(ids) == 1, "Expected 1 ID, got %r" % ids
    #     line = self.browse(cr, uid, ids[0], context=context)
    #     if qty != line.product_uom_qty and line.reservation_ids:
    #         msg = _("As you changed the quantity of the line, "
    #                 "the quantity of the stock reservation will "
    #                 "be automatically adjusted to %.2f.") % qty
    #         msg += "\n\n"
    #         result.setdefault('warning', {})
    #         if result['warning'].get('message'):
    #             result['warning']['message'] += msg
    #         else:
    #             result['warning'] = {
    #                 'title': _('Configuration Error!'),
    #                 'message': msg,
    #             }
    #     return result

    def write(self, cr, uid, ids, vals, context=None):
        update_on_reserve = ('product_id', 'product_uom', 'price_unit', 'product_uom_qty')
        keys = set(vals.keys())
        test_update = keys.intersection(update_on_reserve)
        reserve = False
        res = super(sale_order_line, self).write(cr, uid, ids, vals, context=context)
        if test_update:
            for line in self.browse(cr, uid, ids, context=context):
                if line.order_id.state in ['reserve', ]:
                    reserve = True
                    if line.reservation_ids:
                        wrote = False
                        for reservation in line.reservation_ids:
                            if not wrote:
                                reservation.write(
                                    {'product_id': line.product_id.id,
                                     'name': line.name,
                                     'product_uom': line.product_uom.id,
                                     'price_unit': line.price_unit,
                                     'product_uom_qty': line.product_uom_qty,
                                     })
                                wrote = True
                            else:
                                reservation.unlink()
            if reserve:
                self.stock_reserve(cr, uid, ids, context=context)
        return res

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        context2 = dict(context)
        context2.pop('default_state', False)
        return super(sale_order_line, self).create(cr, uid, vals,
                                                   context=context2)

    def _prepare_stock_reservation(self, cr, uid, line, context=None):
        product_uos = line.product_uos.id if line.product_uos else False
        return {'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'product_uom_qty': line.product_uom_qty,
                'date_validity': False,
                'name': u"{} ({})".format(line.order_id.name, line.name),
                'location_id': line.order_id.warehouse_id.lot_stock_id.id,
                'price_unit': line.price_unit,
                'sale_line_id': line.id,
                'origin': line.order_id.name
                }

    def stock_reserve(self, cr, uid, ids, context=None):
        reserv_obj = self.pool.get('stock.reservation')
        line_obj = self.pool.get('sale.order.line')

        lines = line_obj.browse(cr, uid, ids, context=context)
        for line in lines:
            if not line.is_stock_reservable:
                continue
            if line.reservation_ids:
                for reserve in line.reservation_ids:
                    reserve.reassign()
            else:
                vals = self._prepare_stock_reservation(cr, uid, line,
                                                   context=context)
                reserv_id = reserv_obj.create(cr, uid, vals, context=context)
                reserv_obj.reserve(cr, uid, [reserv_id], context=context)
                reserv = reserv_obj.browse(cr, uid, reserv_id, context=context)
                #follower_ids = [line.order_id.user_id.partner_id.id]
                #reserv_obj.message_subscribe(cr, uid, [reserv_id],
                #                             follower_ids, context=context)
        return True
