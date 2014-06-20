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

from openerp import SUPERUSER_ID
from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
import openerp



class stock_reservation(osv.osv):
    """ Allow to reserve products.

    The fields mandatory for the creation of a reservation are:

    * product_id
    * product_uom_qty
    * product_uom
    * name

    The following fields are required but have default values that you may
    want to override:

    * company_id
    * location_id
    * dest_location_id

    Optionally, you may be interested to define:

    * date_validity  (once passed, the reservation will be released)
    * note
    """
    _name = 'stock.reservation'
    _description = 'Stock Reservation'
    _inherits = {'stock.move': 'move_id'}
    _order = "sequence asc"

    def _new_sequence (self, cr, uid, context=None):
        query = "SELECT MAX(sequence)  FROM stock_reservation "
        cr.execute(query, ())
        regs = cr.fetchall()
        for reg in regs:
             sequence = reg[0] + 1
        return sequence

    _columns = {
        'sequence': fields.integer('Sequence', help="Gives the priority in reservation."),
        'move_id': fields.many2one('stock.move',
                                   'Reservation Move',
                                   required=True,
                                   readonly=True,
                                   ondelete='cascade',
                                   select=1),
        'date_validity': fields.date('Validity Date'),

        'reservation_id': fields.many2one('stock.reservation',
                                   'Parent reservation',
                                   required=False,
                                   readonly=True,
                                   ondelete='cascade',
                                   select=1),
        'splitted_reservations': fields.one2many('stock.reservation',
                                                 'reservation_id',
                                                 'Reservation splitted',
                                                 readonly=True,),
    }

    def get_location_from_ref(self, cr, uid, ref, context=None):
        """ Get a location from a xmlid if allowed
        :param ref: tuple (module, xmlid)
        """
        location_obj = self.pool.get('stock.location')
        data_obj = self.pool.get('ir.model.data')
        get_ref = data_obj.get_object_reference
        try:
            __, location_id = get_ref(cr, uid, *ref)
            location_obj.check_access_rule(cr, uid, [location_id],
                                           'read', context=context)
        except (osv.except_osv, ValueError):
            location_id = False
        return location_id

    def _default_location_id(self, cr, uid, context=None):
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        context['picking_type'] = 'internal'
        return move_obj._default_location_source(cr, uid, context=context)

    def _default_location_dest_id(self, cr, uid, context=None):
        ref = ('stock_reserve', 'stock_location_reservation')
        return self.get_location_from_ref(cr, uid, ref, context=context)

    _defaults = {
        'location_id': _default_location_id,
        'location_dest_id': _default_location_dest_id,
        'product_uom_qty': 1.0,
        'sequence': _new_sequence,
    }

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        print context
        res =  super(stock_reservation, self).write(cr, uid, ids, vals, context=context)
        if vals.get('sequence', False):
            if context.get('first', False) and context['first'] == True:
                print "REASIGNA"
                print vals['sequence']

                self.reassign(cr, uid, ids, context)
        return res

    def reassign(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        reservations = self.browse(cr, uid, ids, context=context)
        reserv_to_release=[]
        for reservation in reservations:
            reserv_ids = self.search(cr, uid, [('sequence', '>=', reservation.sequence), ('product_id', '=', reservation.product_id.id), ('state', 'in', ['draft', 'confirmed', 'assigned'])])

            reserv_to_release += (reserv_ids)
            #Undo all reserves in reservations under the first sequence
        print reserv_to_release
        reserves = self.browse(cr, uid, reserv_to_release)
        move_ids = [reserv['move_id'].id for reserv in reserves]
        print move_ids
        move_obj.do_unreserve(cr, uid, move_ids)

        res_unlinked = []
        for res in reserves:
            # We try to regroup if someone has a related reserve
            if res.splitted_reservations:
                res_unlinked += res.regroup()

        new_res = [x for x in reserves if x not in res_unlinked]

        self.reserve(cr, uid, new_res)

        return True

    def regroup (self, cr, uid,ids, context=None):
        reservations = self.browse(cr, uid, ids, context=context)
        res_to_unlink = []
        for reservation in reservations:
            new_qty = reservation.product_uom_qty
            for related in reservation.splitted_reservations:
                new_qty += related.product_uom_qty
                res_to_unlink.append(related.id)
            reservation.write({'product_uom_qty': new_qty})
        if (res_to_unlink):
            self.unlink(cr, uid, res_to_unlink)
        return res_to_unlink

    def reserve(self, cr, uid, ids, context=None):
        """ Confirm a reservation

        The reservation is done using the default UOM of the product.
        A date until which the product is reserved can be specified.
        """
        move_obj = self.pool.get('stock.move')
        reservations = self.browse(cr, uid, ids, context=context)

        move_confirm_ids =[]
        reservation_split_ids = []

        for reservation in reservations:
            if reservation.product_id.virtual_available >= 0:
                move_confirm_ids.append(reservation.move_id.id)
            else:
                if reservation.product_id.virtual_available + reservation.product_uom_qty > 0:
                    reservation_split_ids.append(reservation.id)
                else:
                    move_obj.write(cr, uid,reservation.move_id.id,
                           {'date_expected': fields.datetime.now()},
                           context=context)
                    move_obj.action_confirm(cr, uid, reservation.move_id.id, context=context)
        if move_confirm_ids:
            move_obj.action_confirm(cr, uid, move_confirm_ids, context=context)
            move_obj.action_assign(cr, uid, move_confirm_ids, context=context)

            move_obj.write(cr, uid, move_confirm_ids,
                           {'date_expected': fields.datetime.now()},
                           context=context)
        if reservation_split_ids:
            self.split_reserve(cr, uid, reservation_split_ids)

        return True



    def split_reserve(self, cr, uid,ids, context=None):
        reservations = self.browse(cr, uid, ids, context=context)
        for reservation in reservations:
            qty_not_confirmed = -reservation.product_id.virtual_available
            reservation.write({'product_uom_qty': reservation.product_uom_qty - qty_not_confirmed},
                           context=context)
            reservation.reserve()

            # New reservation for the quantity not assigned
            new_vals = {
                'product_id': reservation.product_id.id,
                'product_uom_qty': qty_not_confirmed,
                'date_validity': reservation.date_validity,
                'location_id': reservation.location_id.id,
                'location_dest_id': reservation.location_dest_id.id,
                'note ': reservation.note,
                'name': reservation.name,
                'product_uom': reservation.product_uom.id,
                'reservation_id': reservation.id,
            }
            split_reservation_id = self.create(cr, uid, new_vals, context)
            self.reserve(cr, uid, [split_reservation_id])



    def release(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        reservations = self.read(cr, uid, ids, ['move_id'],
                                 context=context, load='_classic_write')
        move_obj = self.pool.get('stock.move')
        move_ids = [reserv['move_id'] for reserv in reservations]
        #Unreserve the quant

        move_obj.action_cancel(cr, uid, move_ids, context=context)
        return True

    def release_validity_exceeded(self, cr, uid, ids=None, context=None):
        """ Release all the reservation having an exceeded validity date """
        domain = [('date_validity', '<', fields.date.today()),
                  ('state', '=', 'assigned')]
        if ids:
            domain.append(('id', 'in', ids))
        reserv_ids = self.search(cr, uid, domain, context=context)
        self.release(cr, uid, reserv_ids, context=context)
        return True

    def unlink(self, cr, uid, ids, context=None):
        """ Release the reservation before the unlink """

        reservations = self.read(cr, uid, ids, ['move_id'],
                                 context=context, load='_classic_write')
        move_obj = self.pool.get('stock.move')
        move_ids = [reserv['move_id'] for reserv in reservations]
        move_obj.do_unreserve (cr, uid, move_ids)
        #self.release(cr, uid, ids, context=context)
        return super(stock_reservation, self).unlink(cr, uid, ids,
                                                     context=context)

    def onchange_product_id(self, cr, uid, ids, product_id=False, context=None):
        move_obj = self.pool.get('stock.move')
        if ids:
            reserv = self.read(cr, uid, ids, ['move_id'], context=context,
                               load='_classic_write')
            move_ids = [rv['move_id'] for rv in reserv]
        else:
            move_ids = []
        result = move_obj.onchange_product_id(
            cr, uid, move_ids, prod_id=product_id, loc_id=False,
            loc_dest_id=False, partner_id=False)
        if result.get('value'):
            vals = result['value']
            # only keep the existing fields on the view
            keep = ('product_uom', 'name')
            result['value'] = dict((key, value) for key, value in
                                   result['value'].iteritems() if
                                   key in keep)
        return result

    def onchange_quantity(self, cr, uid, ids, product_id, product_qty, context=None):
        """ On change of product quantity avoid negative quantities """
        if not product_id or product_qty <= 0.0:
            return {'value': {'product_qty': 0.0}}
        return {}

    def open_move(self, cr, uid, ids, context=None):
        assert len(ids) == 1, "1 ID expected, got %r" % ids
        reserv = self.read(cr, uid, ids[0], ['move_id'], context=context,
                           load='_classic_write')
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        get_ref = mod_obj.get_object_reference
        __, action_id = get_ref(cr, uid, 'stock', 'action_move_form2')
        action = act_obj.read(cr, uid, action_id, context=context)
        action['name'] = _('Reservation Move')
        # open directly in the form view
        __, view_id = get_ref(cr, uid, 'stock', 'view_move_form')
        action['views'] = [(view_id, 'form')]
        action['res_id'] = reserv['move_id']
        return action
