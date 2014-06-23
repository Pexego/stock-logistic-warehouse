from openerp.osv import fields, osv
from openerp.tools.translate import _

from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp import SUPERUSER_ID
from dateutil.relativedelta import relativedelta
from datetime import datetime
import openerp

class procurement_order(osv.osv):
    _inherit = "procurement.order"

    # def _run(self, cr, uid, procurement, context=None):
    #
    #     if procurement.sale_line_id and procurement.sale_line_id.reservation_ids:
    #         move_obj = self.pool.get('stock.move')
    #         reserve_obj = self.pool.get('stock.reservation')
    #
    #         # Release previous reservation in that sale order line
    #         for reservation in procurement.sale_line_id.reservation_ids:
    #             reservation.release()
    #             reservation.refresh()
    #     #Execute the procurement
    #     res = super(procurement_order, self)._run(cr, uid, procurement, context=context)
    #     return res