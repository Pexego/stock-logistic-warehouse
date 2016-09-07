# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from datetime import date, datetime
from dateutil import relativedelta

import time

from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from openerp import SUPERUSER_ID
import openerp.addons.decimal_precision as dp
from openerp.addons.procurement import procurement
import logging


class stock_move(osv.osv):
    _inherit = 'stock.move'

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        ids = super(stock_move, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
        if isinstance(ids, (int, long)):
            ids = [ids]
        reserv_obj = self.pool.get('stock.reservation')
        reserve_ids = reserv_obj.search_read(cr, uid, [('move_id', 'in', ids)],
                                             ['move_id'], order='sequence asc')
        ordered_ids = [x['move_id'][0] for x in reserve_ids]
        not_ordered_ids = [p for p in ids if p not in ordered_ids]
        ids = not_ordered_ids + ordered_ids

        return ids
