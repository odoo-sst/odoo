# -*- coding: utf-8 -*-
{
    'name': 'Multiple Invoice Payment (Multi Currency Support) | '
            'Mass Register Payment for Multiple Vendors & Customers',
    'summary': '''
        Multiple invoices full / partial payment on single payment screen with 
        Multi Currency Support''',
    'description': '''
        Module allows you to select multiple invoices to pay on payment form. 
        Invoices can be selcted on customer payments and vendor payments. 
        This modules supports partial payment for multiple invoices on single payment screen.
        Multi invoice , easy payment , like version 8 , 9 
        Multiple Invoice Multiple Currency Payment
        Invoice Multi Payment
        Mass Register Payment for Multiple Vendors & Customers | Mass Payment | 
        Multiple Vendor Payment | Multiple Invoice Payment | Batch Invoice
    ''',
    'version': '12.0.0.1',
    'author': 'Geo Technosoft',
    'website': 'http://www.geotechnosoft.com',
    'company': 'Geo Technosoft',
    'sequence': 1,
    "category": "Accounting",
    'depends': ['account'],
    'data': [
        "security/ir.model.access.csv",
        'views/account_payment_view.xml',
    ],
    'images': ['static/description/banner.png'],
    'price': 29.99,
    'currency':'EUR',
    'license': 'OPL-1',
    'installable': True,
    'application': True,
}
