from openerp.osv import orm, fields
from openerp.tools.translate import _

from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp import SUPERUSER_ID
from dateutil.relativedelta import relativedelta
from datetime import datetime
import openerp

class procurement_order(orm.Model):

    _inherit = "procurement.order"

    _columns = {
        'reservation_paused': fields.boolean('Reservation paused')
    }


class stock_move(orm.Model):

    _inherit = "stock.move"

    def action_assign(self, cr, uid, ids, context=None):
        valid_ids = []
        res = False
        for move in self.browse(cr, uid, ids, context=context):
            if not move.procurement_id or not move.procurement_id.reservation_paused:
                valid_ids.append(move.id)

        if valid_ids:
            res = super(stock_move, self).action_assign(cr, uid, valid_ids, context=context)
        return res

