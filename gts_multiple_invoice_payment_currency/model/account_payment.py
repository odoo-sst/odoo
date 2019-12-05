
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PaymentInvoiceLine(models.Model):
    _name = 'payment.invoice.line'
    _description = 'Payment Invoice Lines'

    invoice_id = fields.Many2one('account.move', 'Invoice')
    payment_id = fields.Many2one('account.payment', 'Related Payment')
    partner_id = fields.Many2one('res.partner', related='invoice_id.partner_id', string='Partner')
    amount_total = fields.Monetary('Amount Total')
    residual = fields.Monetary('Amount Due')
    amount = fields.Monetary('Amount To Pay',
        help="Enter amount to pay for this invoice, supports partial payment")
    actual_amount = fields.Float(compute='compute_actual_amount',
                                 string='Actual amount paid',
                                 help="Actual amount paid in journal currency")
    date_invoice = fields.Date(related='invoice_id.invoice_date', string='Invoice Date')
    currency_id = fields.Many2one(related='invoice_id.currency_id', string='Currency')
    company_id = fields.Many2one(related='payment_id.company_id', string='Company')

    @api.depends('amount', 'payment_id.payment_date')
    def compute_actual_amount(self):
        for line in self:
            if line.amount > 0:
                line.actual_amount = line.currency_id._convert(
                    line.amount, line.payment_id.currency_id, line.company_id, line.payment_id.payment_date,
                    round=False)
            else:
                line.actual_amount = 0.0


    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount < 0:
                raise UserError(_('Amount to pay can not be less than 0! (Invoice code: %s)')
                    % line.invoice_id.name)
            if line.amount > line.residual:
                raise UserError(_('"Amount to pay" can not be greater than than "Amount '
                                  'Due" ! (Invoice code: %s)')
                                % line.invoice_id.name)

    @api.onchange('invoice_id')
    def onchange_invoice(self):
        if self.invoice_id:
            self.amount_total = self.invoice_id.amount_total
            self.residual = self.invoice_id.residual
        else:
            self.amount_total = 0.0
            self.residual = 0.0


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    invoice_lines = fields.One2many('payment.invoice.line', 'payment_id', 'Invoice Lines',
        help='Please select invoices for this partner for the payment')
    selected_inv_total = fields.Float(compute='compute_selected_invoice_total',
        store=True, string='Assigned Amount')
    balance = fields.Float(compute='_compute_balance', string='Balance')

    @api.depends('invoice_lines', 'invoice_lines.amount', 'amount')
    def _compute_balance(self):
        for payment in self:
            total = 0.0
            for line in payment.invoice_lines:
                total += line.actual_amount
            if payment.amount > total:
                balance = payment.amount - total
            else:
                balance = payment.amount - total
            if payment.company_id:
                payment.balance = payment.currency_id._convert(
                    balance, payment.currency_id, payment.company_id, payment.payment_date,
                    round=False)
            else:
                payment.balance = 0.0

    @api.depends('invoice_lines', 'invoice_lines.amount', 'invoice_lines.actual_amount')
    def compute_selected_invoice_total(self):
        for payment in self:
            total = 0.0
            for line in payment.invoice_lines:
                total += line.actual_amount
            payment.selected_inv_total = total

    @api.constrains('amount', 'selected_inv_total', 'invoice_lines')
    def _check_invoice_amount(self):
        ''' Function to validate if user has selected more amount invoices than payment '''
        for payment in self:
            if payment.invoice_lines:
                if (payment.selected_inv_total - payment.amount) > 0.05:
                    raise UserError(_('You cannot select more value invoices than the payment amount'))

    @api.onchange('partner_id', 'payment_type')
    def onchange_partner_id(self):
        Invoice = self.env['account.move']
        PaymentLine = self.env['payment.invoice.line']
        context = self.env.context
        print ('context....', context)
        if context.get('active_model', '') == 'account.move':
            self.invoice_lines = []
            print ('here....')
            return
        print ('Now also....')
        if self.partner_id and not self.invoice_ids:
            partners_list = self.partner_id.child_ids.ids
            partners_list.append(self.partner_id.id)
            line_ids = []
            type = ''
            if self.payment_type == 'outbound':
                type = 'in_invoice'
            elif self.payment_type == 'inbound':
                type = 'out_invoice'
            invoices = Invoice.search([('partner_id', 'in', partners_list),
                                       ('state', 'in', ('posted',)), ('type', '=', type),
                                       ('amount_residual', '>', 0.0)], order="invoice_date")
            for invoice in invoices:
                data = {
                    'invoice_id': invoice.id,
                    'amount_total': invoice.amount_total,
                    'residual': invoice.amount_residual,
                    'amount': 0.0,
                    'date_invoice': invoice.invoice_date,
                }
                line = PaymentLine.create(data)
                line_ids.append(line.id)
            self.invoice_lines = [(6, 0, line_ids)]
        else:
            if self.invoice_lines:
                for line in self.invoice_lines:
                    line.unlink()
            self.invoice_lines = []

    @api.onchange('amount')
    def onchange_amount(self):
        ''' Function to reset/select invoices on the basis of invoice date '''
        if self.amount > 0 and self.invoice_lines:
            print ('here....2.')
            total_amount = self.amount
            for line in self.invoice_lines:
                if total_amount > 0:
                    conv_amount = self.currency_id._convert(
                        total_amount, line.currency_id, self.company_id, self.payment_date, round=False)
                    if line.residual < conv_amount:
                        line.amount = line.residual
                        if line.currency_id.id == self.currency_id.id:
                            total_amount -= line.residual
                        else:
                            spend_amount = line.currency_id._convert(
                                line.residual, self.currency_id, self.company_id, self.payment_date, round=False)
                            total_amount -= spend_amount
                    else:
                        line.amount = self.currency_id._convert(
                            total_amount, line.currency_id, self.company_id, self.payment_date, round=False)
                        total_amount = 0
                else:
                    line.amount = 0.0
        if (self.amount <= 0):
            for line in self.invoice_lines:
                line.amount = 0.0

    def post(self):
        """ Function reconcile selected invoices """
        reconcile_obj = self.env['account.partial.reconcile']
        move_line_obj = self.env['account.move.line']
        res = super(AccountPayment, self).post()
        for rec in self:
            invoice_lines = rec.invoice_lines.filtered(lambda line: line.amount > 0.0)
            if not invoice_lines:
                return res
            company_currency = rec.company_id.currency_id
            move_lines = move_line_obj.search([('payment_id', '=', rec.id)])
            for line in invoice_lines:
                if rec.payment_type == 'outbound':
                    credit_lines = move_lines.filtered(lambda line: line.debit > 0.0)
                    if not credit_lines:
                        continue
                    for credit_line in credit_lines:
                        invoice_debit_line = line.invoice_id.line_ids.filtered(
                            lambda line: line.account_id.id == credit_line.account_id.id)
                        if not invoice_debit_line:
                            continue
                        for debit_line in invoice_debit_line:
                            if rec.currency_id == company_currency:
                                amount_currency = 0.0
                                currency_id = False
                                amount = line.actual_amount
                            else:
                                amount_currency = line.actual_amount
                                currency_id = rec.currency_id.id
                                amount = rec.currency_id._convert(
                                    line.actual_amount, company_currency, rec.company_id,
                                    rec.payment_date, round=False)
                            data = {
                                'debit_move_id': debit_line.id,
                                'credit_move_id': credit_line.id,
                                'amount': -amount,
                                'amount_currency': -amount_currency or 0.0,
                                'currency_id': currency_id or False,
                            }
                            reconcile_obj.create(data)
                if rec.payment_type == 'inbound':
                    credit_lines = move_lines.filtered(lambda line: line.credit > 0.0)
                    if not credit_lines:
                        continue
                    for credit_line in credit_lines:
                        invoice_debit_line = line.invoice_id.line_ids.filtered(
                            lambda line: line.account_id.id == credit_line.account_id.id)
                        if not invoice_debit_line:
                            continue
                        for debit_line in invoice_debit_line:
                            if rec.currency_id == company_currency:
                                amount_currency = 0.0
                                currency_id = False
                                amount = line.actual_amount
                            else:
                                amount_currency = line.actual_amount
                                currency_id = rec.currency_id.id
                                amount = rec.currency_id._convert(
                                    line.actual_amount, company_currency, rec.company_id,
                                    rec.payment_date, round=False)
                            reconcile_obj.create({
                                'debit_move_id': debit_line.id,
                                'credit_move_id': credit_line.id,
                                'amount': amount,
                                'amount_currency': amount_currency,
                                'currency_id': currency_id or False,
                            })
        return res

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        default.update(invoice_lines=[], invoice_total=0.0)
        return super(AccountPayment, self).copy(default)
