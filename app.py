import os
import sys
import sqlite3
import shutil
import hashlib
import base64
import webbrowser
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from datetime import datetime, date, timedelta
from decimal import Decimal
import json

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    TEMPLATE_DIR = os.path.join(sys._MEIPASS, 'templates')
    STATIC_DIR = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
    DB_PATH = os.path.join(BASE_DIR, 'cherry_inventory.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'cherry-inventory-secret-key-2024')
if not getattr(sys, 'frozen', False):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///cherry_inventory.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

CURRENCY_SYMBOL = 'C$'
TAX_RATE = 15.0

# ===================== MODELOS =====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='cashier')
    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = simple_hash(password)

    def check_password(self, password):
        return check_simple_hash(self.password_hash, password)

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50), nullable=False)
    detail = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    user = db.relationship('User', backref='logs')

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    ruc = db.Column(db.String(20))
    loyalty_points = db.Column(db.Integer, default=0)
    credit_limit = db.Column(db.Numeric(10, 2), default=0)
    current_credit = db.Column(db.Numeric(10, 2), default=0)
    is_vip = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    invoices = db.relationship('Invoice', backref='customer', lazy=True)

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    ruc = db.Column(db.String(20))
    balance = db.Column(db.Numeric(10, 2), default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    purchase_orders = db.relationship('PurchaseOrder', backref='supplier', lazy=True)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    purchase_price = db.Column(db.Numeric(10, 2), nullable=False)
    sale_price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    min_stock = db.Column(db.Integer, default=5)
    category = db.Column(db.String(50))
    unit = db.Column(db.String(20), default='Unidad')
    has_batch = db.Column(db.Boolean, default=False)
    has_expiry = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    batches = db.relationship('ProductBatch', backref='product', lazy=True)
    supplier = db.relationship('Supplier', backref='products')

class ProductBatch(db.Model):
    __tablename__ = 'product_batches'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    batch_number = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    expiry_date = db.Column(db.Date)
    purchase_price = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=datetime.now)

class ProductKit(db.Model):
    __tablename__ = 'product_kits'
    id = db.Column(db.Integer, primary_key=True)
    kit_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    component_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    kit = db.relationship('Product', foreign_keys=[kit_product_id], backref='kit_components')
    component = db.relationship('Product', foreign_keys=[component_product_id], backref='used_in_kits')

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(20), default='cash')
    reference = db.Column(db.String(100))
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    user = db.relationship('User', backref='transactions')

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    commission_rate = db.Column(db.Numeric(5, 2), default=0)
    base_salary = db.Column(db.Numeric(10, 2), default=0)
    is_active = db.Column(db.Boolean, default=True)
    hire_date = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.now)
    user = db.relationship('User', backref='employee_profile')

class InventoryMovement(db.Model):
    __tablename__ = 'inventory_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    type = db.Column(db.String(20), nullable=False)  # entry, exit, adjustment, transfer
    quantity = db.Column(db.Integer, nullable=False)
    before_stock = db.Column(db.Integer)
    after_stock = db.Column(db.Integer)
    reference_type = db.Column(db.String(20))  # purchase, sale, return, adjustment, kit
    reference_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    product = db.relationship('Product', backref='movements')
    user = db.relationship('User', backref='movements')

class InstallmentPlan(db.Model):
    __tablename__ = 'installment_plans'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid_amount = db.Column(db.Numeric(10, 2), default=0)
    remaining_amount = db.Column(db.Numeric(10, 2))
    num_installments = db.Column(db.Integer, default=1)
    installment_amount = db.Column(db.Numeric(10, 2))
    frequency = db.Column(db.String(20), default='monthly')
    status = db.Column(db.String(20), default='active')
    start_date = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.now)
    invoice = db.relationship('Invoice', backref='installment_plan')
    customer = db.relationship('Customer', backref='installment_plans')
    payments = db.relationship('InstallmentPayment', backref='plan', lazy=True)

class InstallmentPayment(db.Model):
    __tablename__ = 'installment_payments'
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('installment_plans.id'))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date, default=date.today)
    installment_number = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Alert(db.Model):
    __tablename__ = 'alerts'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(30), nullable=False)  # low_stock, expiring, pending_payment, credit_due, daily_summary
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    severity = db.Column(db.String(10), default='info')  # info, warning, danger
    is_read = db.Column(db.Boolean, default=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)

class CashReconciliation(db.Model):
    __tablename__ = 'cash_reconciliations'
    id = db.Column(db.Integer, primary_key=True)
    register_id = db.Column(db.Integer, db.ForeignKey('cash_registers.id'))
    counted_cash = db.Column(db.Numeric(10, 2))
    expected_cash = db.Column(db.Numeric(10, 2))
    difference = db.Column(db.Numeric(10, 2))
    denomination_1 = db.Column(db.Integer, default=0)
    denomination_5 = db.Column(db.Integer, default=0)
    denomination_10 = db.Column(db.Integer, default=0)
    denomination_25 = db.Column(db.Integer, default=0)
    denomination_50 = db.Column(db.Integer, default=0)
    denomination_100 = db.Column(db.Integer, default=0)
    denomination_500 = db.Column(db.Integer, default=0)
    denomination_1000 = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    reconciled_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)

class WhatsAppConfig(db.Model):
    __tablename__ = 'whatsapp_config'
    id = db.Column(db.Integer, primary_key=True)
    api_key = db.Column(db.String(200))
    phone_number_id = db.Column(db.String(50))
    business_phone = db.Column(db.String(20))
    welcome_message = db.Column(db.Text, default='¡Gracias por su compra en {business_name}!')
    invoice_message = db.Column(db.Text, default='Hola {customer_name}, su factura {invoice_number} por {total} está lista. ¡Gracias!')
    is_active = db.Column(db.Boolean, default=False)

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)
    status = db.Column(db.String(20), default='pending')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    received_at = db.Column(db.DateTime)
    items = db.relationship('PurchaseOrderItem', backref='order', lazy=True)
    user = db.relationship('User', backref='purchase_orders')

class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    product = db.relationship('Product', backref='purchase_items')

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=15.00)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    discount_percent = db.Column(db.Numeric(5, 2), default=0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)
    paid_amount = db.Column(db.Numeric(10, 2), default=0)
    change_amount = db.Column(db.Numeric(10, 2), default=0)
    tip_amount = db.Column(db.Numeric(10, 2), default=0)
    payment_method = db.Column(db.String(20), default='cash')
    status = db.Column(db.String(20), default='completed')
    is_credit = db.Column(db.Boolean, default=False)
    credit_paid = db.Column(db.Numeric(10, 2), default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True)
    payments = db.relationship('Payment', backref='invoice', lazy=True)
    user = db.relationship('User', backref='invoices')

class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    batch_id = db.Column(db.Integer, db.ForeignKey('product_batches.id'))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(5, 2), default=0)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    product = db.relationship('Product', backref='invoice_items')

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(20), default='cash')
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Return(db.Model):
    __tablename__ = 'returns'
    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(20), unique=True, nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    total = db.Column(db.Numeric(10, 2), default=0)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.now)
    items = db.relationship('ReturnItem', backref='return_doc', lazy=True)
    invoice = db.relationship('Invoice', backref='returns')
    customer = db.relationship('Customer', backref='returns')
    user = db.relationship('User', backref='returns')

class ReturnItem(db.Model):
    __tablename__ = 'return_items'
    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('returns.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    product = db.relationship('Product', backref='return_items')

class Quotation(db.Model):
    __tablename__ = 'quotations'
    id = db.Column(db.Integer, primary_key=True)
    quotation_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)
    status = db.Column(db.String(20), default='pending')
    valid_until = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    items = db.relationship('QuotationItem', backref='quotation', lazy=True)
    customer = db.relationship('Customer', backref='quotations')
    user = db.relationship('User', backref='quotations')

class QuotationItem(db.Model):
    __tablename__ = 'quotation_items'
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    product = db.relationship('Product', backref='quotation_items')

class CashRegister(db.Model):
    __tablename__ = 'cash_registers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    opening_amount = db.Column(db.Numeric(10, 2), default=0)
    closing_amount = db.Column(db.Numeric(10, 2))
    actual_amount = db.Column(db.Numeric(10, 2))
    difference = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(20), default='open')
    opened_at = db.Column(db.DateTime, default=datetime.now)
    closed_at = db.Column(db.DateTime)
    user = db.relationship('User', backref='cash_registers')
    entries = db.relationship('CashRegisterEntry', backref='register', lazy=True)

class CashRegisterEntry(db.Model):
    __tablename__ = 'cash_register_entries'
    id = db.Column(db.Integer, primary_key=True)
    register_id = db.Column(db.Integer, db.ForeignKey('cash_registers.id'))
    type = db.Column(db.String(20))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.Text)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))

class InvoiceSettings(db.Model):
    __tablename__ = 'invoice_settings'
    id = db.Column(db.Integer, primary_key=True)
    business_name = db.Column(db.String(200), default='Cherry Inventario')
    business_ruc = db.Column(db.String(20))
    business_address = db.Column(db.Text)
    business_phone = db.Column(db.String(20))
    business_email = db.Column(db.String(120))
    business_website = db.Column(db.String(120))
    logo_path = db.Column(db.String(200))
    invoice_footer = db.Column(db.Text, default='¡Gracias por su compra!')
    invoice_note = db.Column(db.Text)
    default_tax_rate = db.Column(db.Numeric(5, 2), default=15.00)
    invoice_prefix = db.Column(db.String(10), default='INV')
    show_logo = db.Column(db.Boolean, default=True)
    show_ruc = db.Column(db.Boolean, default=True)
    show_address = db.Column(db.Boolean, default=True)
    show_phone = db.Column(db.Boolean, default=True)
    show_email = db.Column(db.Boolean, default=True)
    show_website = db.Column(db.Boolean, default=False)
    show_customer = db.Column(db.Boolean, default=True)
    show_cashier = db.Column(db.Boolean, default=True)
    show_barcode = db.Column(db.Boolean, default=True)
    show_tax_breakdown = db.Column(db.Boolean, default=True)
    show_payment_method = db.Column(db.Boolean, default=True)
    thermal_width = db.Column(db.Integer, default=80)
    paper_size = db.Column(db.String(20), default='80mm')

# ===================== UTILIDADES =====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def format_currency(amount):
    return f'{CURRENCY_SYMBOL} {amount:,.2f}'

def simple_hash(password):
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return base64.b64encode(salt + h).decode()

def check_simple_hash(stored, password):
    try:
        decoded = base64.b64decode(stored)
        salt = decoded[:16]
        h = decoded[16:]
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000) == h
    except:
        return False

def log_action(action, detail=''):
    if current_user.is_authenticated:
        log = ActivityLog(
            user_id=current_user.id,
            action=action,
            detail=detail,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

app.jinja_env.globals.update(format_currency=format_currency)
app.jinja_env.globals.update(now=datetime.now)

UPDATE_VERSION = "1.0.0"
GITHUB_REPO = "DELIVERYEXPRESS25/CHERRY"

# ===================== AUTO-ACTUALIZADOR =====================

@app.route('/api/update/check')
@login_required
def check_update():
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    try:
        import urllib.request
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={
            "User-Agent": "CherryInventario",
            "Accept": "application/vnd.github.v3+json"
        })
        response = urllib.request.urlopen(req, timeout=15)
        data = json.loads(response.read())
        
        version = data.get("tag_name", "").lstrip("v")
        has_update = version > UPDATE_VERSION
        
        download_url = None
        for asset in data.get("assets", []):
            if asset["name"].endswith(".zip"):
                download_url = asset["browser_download_url"]
                break
        
        return jsonify({
            'current_version': UPDATE_VERSION,
            'latest_version': version,
            'has_update': has_update,
            'description': data.get('body', ''),
            'published_at': data.get('published_at', ''),
            'download_url': download_url,
            'html_url': data.get('html_url', ''),
            'mandatory': False
        })
    except Exception as e:
        return jsonify({
            'current_version': UPDATE_VERSION,
            'has_update': False,
            'error': str(e)
        })

@app.route('/admin/updates')
@login_required
def admin_updates():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    return render_template('admin_updates.html', current_version=UPDATE_VERSION, github_repo=GITHUB_REPO)

@app.route('/admin/updates/check')
@login_required
def admin_check_update():
    if current_user.role != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    try:
        import urllib.request
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={
            "User-Agent": "CherryInventario",
            "Accept": "application/vnd.github.v3+json"
        })
        response = urllib.request.urlopen(req, timeout=15)
        data = json.loads(response.read())
        
        version = data.get("tag_name", "").lstrip("v")
        has_update = version > UPDATE_VERSION
        
        download_url = None
        for asset in data.get("assets", []):
            if asset["name"].endswith(".zip"):
                download_url = asset["browser_download_url"]
                break
        
        return jsonify({
            'current_version': UPDATE_VERSION,
            'latest_version': version,
            'has_update': has_update,
            'description': data.get('body', ''),
            'published_at': data.get('published_at', ''),
            'download_url': download_url,
            'html_url': data.get('html_url', ''),
            'mandatory': False
        })
    except Exception as e:
        return jsonify({
            'current_version': UPDATE_VERSION,
            'has_update': False,
            'error': str(e)
        })

# ===================== RUTAS PRINCIPALES =====================

@app.route('/')
@login_required
def dashboard():
    total_products = Product.query.filter_by(is_active=True).count()
    total_customers = Customer.query.count()
    total_suppliers = Supplier.query.filter_by(is_active=True).count()
    low_stock = Product.query.filter(Product.stock <= Product.min_stock, Product.is_active == True).count()
    
    today = date.today()
    today_sales = db.session.query(db.func.sum(Invoice.total)).filter(
        db.func.date(Invoice.created_at) == today,
        Invoice.status == 'completed'
    ).scalar() or 0
    
    month_start = today.replace(day=1)
    month_sales = db.session.query(db.func.sum(Invoice.total)).filter(
        db.func.date(Invoice.created_at) >= month_start,
        Invoice.status == 'completed'
    ).scalar() or 0
    
    pending_credits = db.session.query(db.func.sum(Invoice.total - Invoice.credit_paid)).filter(
        Invoice.is_credit == True,
        Invoice.status == 'completed',
        Invoice.credit_paid < Invoice.total
    ).scalar() or 0
    
    recent_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(5).all()
    low_stock_products = Product.query.filter(
        Product.stock <= Product.min_stock,
        Product.is_active == True
    ).limit(5).all()
    
    expiring_batches = ProductBatch.query.filter(
        ProductBatch.expiry_date <= date.today() + timedelta(days=30),
        ProductBatch.expiry_date >= date.today(),
        ProductBatch.quantity > 0
    ).limit(5).all()

    return render_template('dashboard.html',
        total_products=total_products,
        total_customers=total_customers,
        total_suppliers=total_suppliers,
        low_stock=low_stock,
        today_sales=today_sales,
        month_sales=month_sales,
        pending_credits=pending_credits,
        recent_invoices=recent_invoices,
        low_stock_products=low_stock_products,
        expiring_batches=expiring_batches
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST' and request.form.get('password'):
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user, remember=True)
            log_action('login', 'Inicio de sesión exitoso')
            return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_action('logout', 'Cierre de sesión')
    logout_user()
    return redirect(url_for('login'))

# ===================== PRODUCTOS =====================

@app.route('/products')
@login_required
def products():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    supplier = request.args.get('supplier', '')
    query = Product.query.filter_by(is_active=True)
    if search:
        query = query.filter(db.or_(Product.name.ilike(f'%{search}%'), Product.code.ilike(f'%{search}%')))
    if category:
        query = query.filter_by(category=category)
    if supplier:
        query = query.filter_by(supplier_id=supplier)
    products = query.order_by(Product.name).all()
    categories = db.session.query(Product.category).distinct().filter(Product.category.isnot(None), Product.category != '').all()
    categories = [c[0] for c in categories]
    suppliers_list = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    return render_template('products.html', products=products, categories=categories, suppliers=suppliers_list, search=search, selected_category=category, selected_supplier=supplier)

@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        product = Product(
            code=request.form['code'],
            name=request.form['name'],
            description=request.form.get('description', ''),
            purchase_price=Decimal(request.form['purchase_price']),
            sale_price=Decimal(request.form['sale_price']),
            stock=int(request.form['stock']),
            min_stock=int(request.form.get('min_stock', 5)),
            category=request.form.get('category', ''),
            unit=request.form.get('unit', 'Unidad'),
            has_batch='has_batch' in request.form,
            has_expiry='has_expiry' in request.form,
            supplier_id=int(request.form['supplier_id']) if request.form.get('supplier_id') else None
        )
        db.session.add(product)
        db.session.commit()
        log_action('product_add', f'Producto: {product.name}')
        flash('Producto agregado exitosamente', 'success')
        return redirect(url_for('products'))
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    return render_template('product_form.html', product=None, suppliers=suppliers)

@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.code = request.form['code']
        product.name = request.form['name']
        product.description = request.form.get('description', '')
        product.purchase_price = Decimal(request.form['purchase_price'])
        product.sale_price = Decimal(request.form['sale_price'])
        product.stock = int(request.form['stock'])
        product.min_stock = int(request.form.get('min_stock', 5))
        product.category = request.form.get('category', '')
        product.unit = request.form.get('unit', 'Unidad')
        product.has_batch = 'has_batch' in request.form
        product.has_expiry = 'has_expiry' in request.form
        product.supplier_id = int(request.form['supplier_id']) if request.form.get('supplier_id') else None
        db.session.commit()
        log_action('product_edit', f'Producto: {product.name}')
        flash('Producto actualizado exitosamente', 'success')
        return redirect(url_for('products'))
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    return render_template('product_form.html', product=product, suppliers=suppliers)

@app.route('/products/delete/<int:id>')
@login_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    product.is_active = False
    db.session.commit()
    log_action('product_delete', f'Producto: {product.name}')
    flash('Producto eliminado exitosamente', 'success')
    return redirect(url_for('products'))

@app.route('/products/batches/<int:id>')
@login_required
def product_batches(id):
    product = Product.query.get_or_404(id)
    batches = ProductBatch.query.filter_by(product_id=id).order_by(ProductBatch.expiry_date).all()
    return render_template('product_batches.html', product=product, batches=batches)

@app.route('/products/batches/add/<int:product_id>', methods=['POST'])
@login_required
def add_batch(product_id):
    batch = ProductBatch(
        product_id=product_id,
        batch_number=request.form['batch_number'],
        quantity=int(request.form['quantity']),
        expiry_date=datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date() if request.form.get('expiry_date') else None,
        purchase_price=Decimal(request.form['purchase_price']) if request.form.get('purchase_price') else None
    )
    product = Product.query.get(product_id)
    product.stock += batch.quantity
    db.session.add(batch)
    db.session.commit()
    log_action('batch_add', f'Lote: {batch.batch_number} - {product.name}')
    flash('Lote agregado exitosamente', 'success')
    return redirect(url_for('product_batches', id=product_id))

# ===================== PRODUCTOS KIT/COMBO =====================

@app.route('/products/<int:id>/kit')
@login_required
def product_kit(id):
    product = Product.query.get_or_404(id)
    kit_items = ProductKit.query.filter_by(kit_product_id=id).all()
    all_products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template('product_kit.html', product=product, kit_items=kit_items, all_products=all_products)

@app.route('/products/<int:id>/kit/add', methods=['POST'])
@login_required
def add_kit_component(id):
    component_id = int(request.form['component_id'])
    quantity = int(request.form['quantity'])
    
    existing = ProductKit.query.filter_by(kit_product_id=id, component_product_id=component_id).first()
    if existing:
        existing.quantity += quantity
    else:
        kit_item = ProductKit(kit_product_id=id, component_product_id=component_id, quantity=quantity)
        db.session.add(kit_item)
    
    db.session.commit()
    log_action('kit_add', f'Componente agregado al kit')
    flash('Componente agregado al kit', 'success')
    return redirect(url_for('product_kit', id=id))

@app.route('/products/kit/remove/<int:kit_id>')
@login_required
def remove_kit_component(kit_id):
    kit_item = ProductKit.query.get_or_404(kit_id)
    product_id = kit_item.kit_product_id
    db.session.delete(kit_item)
    db.session.commit()
    log_action('kit_remove', f'Componente removido del kit')
    flash('Componente removido del kit', 'success')
    return redirect(url_for('product_kit', id=product_id))

@app.route('/products/kit/build/<int:id>', methods=['POST'])
@login_required
def build_kit(id):
    product = Product.query.get_or_404(id)
    kit_items = ProductKit.query.filter_by(kit_product_id=id).all()
    
    if not kit_items:
        flash('Este producto no tiene componentes definidos', 'error')
        return redirect(url_for('product_kit', id=id))
    
    quantity_to_build = int(request.form.get('quantity', 1))
    
    for item in kit_items:
        component = Product.query.get(item.component_product_id)
        needed = item.quantity * quantity_to_build
        if component.stock < needed:
            flash(f'Stock insuficiente de {component.name} (necesita {needed}, tiene {component.stock})', 'error')
            return redirect(url_for('product_kit', id=id))
    
    for item in kit_items:
        component = Product.query.get(item.component_product_id)
        component.stock -= item.quantity * quantity_to_build
    
    product.stock += quantity_to_build
    db.session.commit()
    log_action('kit_build', f'{quantity_to_build}x {product.name} construido')
    flash(f'{quantity_to_build} unidades de {product.name} construidas', 'success')
    return redirect(url_for('product_kit', id=id))

# ===================== CONTABILIDAD =====================

@app.route('/accounting')
@login_required
def accounting():
    if current_user.role not in ['admin', 'manager']:
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    today = date.today()
    month_start = today.replace(day=1)
    
    income = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.type == 'income',
        db.func.date(Transaction.created_at) >= month_start
    ).scalar() or 0
    
    expenses = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.type == 'expense',
        db.func.date(Transaction.created_at) >= month_start
    ).scalar() or 0
    
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(50).all()
    return render_template('accounting.html', income=income, expenses=expenses, transactions=transactions, month_start=month_start)

@app.route('/accounting/transaction', methods=['POST'])
@login_required
def add_transaction():
    if current_user.role not in ['admin', 'manager']:
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    transaction = Transaction(
        type=request.form['type'],
        category=request.form.get('category', ''),
        description=request.form.get('description', ''),
        amount=Decimal(request.form['amount']),
        payment_method=request.form.get('payment_method', 'cash'),
        reference=request.form.get('reference', ''),
        user_id=current_user.id
    )
    db.session.add(transaction)
    db.session.commit()
    log_action('transaction_add', f'{transaction.type}: C$ {transaction.amount:.2f}')
    flash('Movimiento registrado', 'success')
    return redirect(url_for('accounting'))

@app.route('/reports/dgi')
@login_required
def dgi_report():
    if current_user.role not in ['admin', 'manager']:
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start', date.today().replace(day=1).isoformat())
    end_date = request.args.get('end', date.today().isoformat())
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    invoices = Invoice.query.filter(
        db.func.date(Invoice.created_at) >= start,
        db.func.date(Invoice.created_at) <= end,
        Invoice.status == 'completed'
    ).all()
    
    total_ventas = sum(float(inv.total) for inv in invoices)
    total_isv = sum(float(inv.tax_amount) for inv in invoices)
    total_subtotal = sum(float(inv.subtotal) for inv in invoices)
    
    ventas_por_tipo = {
        'contado': sum(float(inv.total) for inv in invoices if inv.payment_method == 'cash'),
        'credito': sum(float(inv.total) for inv in invoices if inv.payment_method == 'credit'),
        'tarjeta': sum(float(inv.total) for inv in invoices if inv.payment_method == 'card'),
        'transferencia': sum(float(inv.total) for inv in invoices if inv.payment_method == 'transfer')
    }
    
    return render_template('dgi_report.html', 
        invoices=invoices, total_ventas=total_ventas, total_isv=total_isv,
        total_subtotal=total_subtotal, ventas_por_tipo=ventas_por_tipo,
        start_date=start_date, end_date=end_date)

# ===================== EMPLEADOS/VENDEDORES =====================

@app.route('/employees')
@login_required
def employees():
    if current_user.role not in ['admin', 'manager']:
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    return render_template('employees.html', employees=employees)

@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    if current_user.role not in ['admin', 'manager']:
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        employee = Employee(
            name=request.form['name'],
            position=request.form.get('position', ''),
            phone=request.form.get('phone', ''),
            email=request.form.get('email', ''),
            commission_rate=Decimal(request.form.get('commission_rate', 0)),
            base_salary=Decimal(request.form.get('base_salary', 0)),
            hire_date=datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date() if request.form.get('hire_date') else date.today()
        )
        db.session.add(employee)
        db.session.commit()
        log_action('employee_add', f'Empleado: {employee.name}')
        flash('Empleado agregado', 'success')
        return redirect(url_for('employees'))
    return render_template('employee_form.html', employee=None)

@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_employee(id):
    if current_user.role not in ['admin', 'manager']:
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    employee = Employee.query.get_or_404(id)
    if request.method == 'POST':
        employee.name = request.form['name']
        employee.position = request.form.get('position', '')
        employee.phone = request.form.get('phone', '')
        employee.email = request.form.get('email', '')
        employee.commission_rate = Decimal(request.form.get('commission_rate', 0))
        employee.base_salary = Decimal(request.form.get('base_salary', 0))
        db.session.commit()
        log_action('employee_edit', f'Empleado: {employee.name}')
        flash('Empleado actualizado', 'success')
        return redirect(url_for('employees'))
    return render_template('employee_form.html', employee=employee)

@app.route('/employees/<int:id>')
@login_required
def employee_detail(id):
    employee = Employee.query.get_or_404(id)
    month_start = date.today().replace(day=1)
    sales = Invoice.query.filter(
        Invoice.user_id == employee.user_id,
        db.func.date(Invoice.created_at) >= month_start,
        Invoice.status == 'completed'
    ).all() if employee.user_id else []
    
    total_sales = sum(float(inv.total) for inv in sales)
    commission = total_sales * float(employee.commission_rate) / 100
    
    return render_template('employee_detail.html', employee=employee, sales=sales, total_sales=total_sales, commission=commission, month_start=month_start)

# ===================== KARDEX/INVENTARIO =====================

@app.route('/kardex')
@login_required
def kardex():
    product_id = request.args.get('product', '')
    movements = InventoryMovement.query
    
    if product_id:
        movements = movements.filter_by(product_id=int(product_id))
    
    movements = movements.order_by(InventoryMovement.created_at.desc()).limit(200).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template('kardex.html', movements=movements, products=products, selected_product=product_id)

@app.route('/kardex/adjustment', methods=['POST'])
@login_required
def inventory_adjustment():
    product_id = int(request.form['product_id'])
    adjustment = int(request.form['adjustment'])
    reason = request.form.get('reason', '')
    
    product = Product.query.get_or_404(product_id)
    before = product.stock
    product.stock += adjustment
    
    movement = InventoryMovement(
        product_id=product_id,
        type='adjustment' if adjustment > 0 else 'exit',
        quantity=abs(adjustment),
        before_stock=before,
        after_stock=product.stock,
        reference_type='adjustment',
        description=reason,
        user_id=current_user.id
    )
    db.session.add(movement)
    db.session.commit()
    log_action('inventory_adjustment', f'{product.name}: {adjustment:+d} unidades')
    flash('Ajuste de inventario registrado', 'success')
    return redirect(url_for('kardex'))

# ===================== CRÉDITO A PLAZOS =====================

@app.route('/installments')
@login_required
def installments():
    plans = InstallmentPlan.query.order_by(InstallmentPlan.created_at.desc()).all()
    return render_template('installments.html', plans=plans)

@app.route('/installments/new/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
def new_installment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    if request.method == 'POST':
        plan = InstallmentPlan(
            invoice_id=invoice_id,
            customer_id=invoice.customer_id,
            total_amount=invoice.total,
            paid_amount=0,
            remaining_amount=invoice.total,
            num_installments=int(request.form['num_installments']),
            installment_amount=invoice.total / int(request.form['num_installments']),
            frequency=request.form.get('frequency', 'monthly'),
            status='active',
            start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d').date() if request.form.get('start_date') else date.today()
        )
        
        invoice.is_credit = True
        invoice.payment_method = 'credit'
        
        db.session.add(plan)
        db.session.commit()
        log_action('installment_create', f'Plan de cuotas: {invoice.invoice_number}')
        flash('Plan de cuotas creado', 'success')
        return redirect(url_for('view_installment', id=plan.id))
    
    return render_template('installment_form.html', invoice=invoice)

@app.route('/installments/<int:id>')
@login_required
def view_installment(id):
    plan = InstallmentPlan.query.get_or_404(id)
    payments = InstallmentPayment.query.filter_by(plan_id=id).order_by(InstallmentPayment.payment_date).all()
    return render_template('installment_detail.html', plan=plan, payments=payments)

@app.route('/installments/<int:id>/pay', methods=['POST'])
@login_required
def pay_installment(id):
    plan = InstallmentPlan.query.get_or_404(id)
    amount = Decimal(request.form['amount'])
    
    if amount > 0 and plan.remaining_amount > 0:
        payment_amount = min(amount, plan.remaining_amount)
        
        payment = InstallmentPayment(
            plan_id=id,
            amount=payment_amount,
            installment_number=len(plan.payments) + 1,
            notes=request.form.get('notes', '')
        )
        
        plan.paid_amount += payment_amount
        plan.remaining_amount -= payment_amount
        
        if plan.remaining_amount <= 0:
            plan.status = 'completed'
        
        if plan.customer_id:
            customer = Customer.query.get(plan.customer_id)
            if customer:
                customer.current_credit -= payment_amount
        
        db.session.add(payment)
        db.session.commit()
        log_action('installment_pay', f'Pago C$ {payment_amount:.2f} - Plan #{id}')
        flash(f'Pago de C$ {payment_amount:.2f} registrado', 'success')
    
    return redirect(url_for('view_installment', id=id))

# ===================== SISTEMA DE ALERTAS =====================

@app.route('/alerts')
@login_required
def alerts():
    alerts = Alert.query.filter_by(user_id=current_user.id).order_by(Alert.created_at.desc()).limit(100).all()
    unread_count = Alert.query.filter_by(user_id=current_user.id, is_read=False).count()
    return render_template('alerts.html', alerts=alerts, unread_count=unread_count)

@app.route('/alerts/mark-read/<int:id>')
@login_required
def mark_alert_read(id):
    alert = Alert.query.get_or_404(id)
    alert.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/alerts/mark-all-read')
@login_required
def mark_all_alerts_read():
    Alert.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    flash('Todas las alertas marcadas como leídas', 'success')
    return redirect(url_for('alerts'))

@app.route('/alerts/generate')
@login_required
def generate_alerts():
    if current_user.role not in ['admin', 'manager']:
        return redirect(url_for('dashboard'))
    
    Alert.query.filter_by(user_id=current_user.id).delete()
    
    low_stock = Product.query.filter(Product.stock <= Product.min_stock, Product.is_active == True).all()
    for p in low_stock:
        db.session.add(Alert(type='low_stock', title=f'Stock bajo: {p.name}', message=f'Stock actual: {p.stock} | Mínimo: {p.min_stock}', severity='danger', product_id=p.id, user_id=current_user.id))
    
    expiring = ProductBatch.query.filter(ProductBatch.expiry_date <= date.today() + timedelta(days=30), ProductBatch.expiry_date > date.today(), ProductBatch.quantity > 0).all()
    for b in expiring:
        db.session.add(Alert(type='expiring', title=f'Por vencer: {b.product.name}', message=f'Lote {b.batch_number} vence el {b.expiry_date.strftime("%d/%m/%Y")}', severity='warning', product_id=b.product_id, user_id=current_user.id))
    
    credit_plans = InstallmentPlan.query.filter_by(status='active').all()
    for plan in credit_plans:
        overdue = InstallmentPayment.query.filter_by(plan_id=plan.id).count()
        if overdue == 0 or (plan.installments and max(p.payment_date for p in plan.payments) < date.today() - timedelta(days=35)):
            db.session.add(Alert(type='credit_due', title=f'Cuota pendiente: Plan #{plan.id}', message=f'Cliente: {plan.customer.name if plan.customer else "-"} | Pendiente: C$ {plan.remaining_amount}', severity='warning', customer_id=plan.customer_id, user_id=current_user.id))
    
    db.session.commit()
    flash(f'Alertas generadas', 'success')
    return redirect(url_for('alerts'))

@app.route('/api/alerts/count')
@login_required
def alert_count():
    count = Alert.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

# ===================== DASHBOARD MEJORADO =====================

@app.route('/api/dashboard-data')
@login_required
def dashboard_data():
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    
    daily_sales = db.session.query(db.func.sum(Invoice.total)).filter(db.func.date(Invoice.created_at) == today, Invoice.status == 'completed').scalar() or 0
    monthly_sales = db.session.query(db.func.sum(Invoice.total)).filter(db.func.date(Invoice.created_at) >= month_start, Invoice.status == 'completed').scalar() or 0
    yearly_sales = db.session.query(db.func.sum(Invoice.total)).filter(db.func.date(Invoice.created_at) >= year_start, Invoice.status == 'completed').scalar() or 0
    
    monthly_expenses = db.session.query(db.func.sum(Transaction.amount)).filter(Transaction.type == 'expense', db.func.date(Transaction.created_at) >= month_start).scalar() or 0
    
    last_12_months = []
    for i in range(11, -1, -1):
        d = today - timedelta(days=i*30)
        m_start = d.replace(day=1)
        if d.month == 12:
            m_end = d.replace(year=d.year+1, month=1, day=1)
        else:
            m_end = d.replace(month=d.month+1, day=1)
        sales = db.session.query(db.func.sum(Invoice.total)).filter(Invoice.created_at >= m_start, Invoice.created_at < m_end, Invoice.status == 'completed').scalar() or 0
        last_12_months.append({'month': d.strftime('%b'), 'sales': float(sales)})
    
    top_products = db.session.query(Product.name, db.func.sum(InvoiceItem.quantity).label('total_qty')).join(InvoiceItem).join(Invoice).filter(Invoice.status == 'completed', db.func.date(Invoice.created_at) >= month_start).group_by(Product.name).order_by(db.desc('total_qty')).limit(5).all()
    
    low_stock = Product.query.filter(Product.stock <= Product.min_stock, Product.is_active == True).count()
    expiring_count = ProductBatch.query.filter(ProductBatch.expiry_date <= today + timedelta(days=30), ProductBatch.expiry_date > today, ProductBatch.quantity > 0).count()
    
    return jsonify({
        'daily_sales': float(daily_sales),
        'monthly_sales': float(monthly_sales),
        'yearly_sales': float(yearly_sales),
        'monthly_expenses': float(monthly_expenses),
        'monthly_profit': float(monthly_sales - monthly_expenses),
        'last_12_months': last_12_months,
        'top_products': [{'name': p[0], 'qty': p[1]} for p in top_products],
        'low_stock_alerts': low_stock,
        'expiring_alerts': expiring_count
    })

# ===================== CAJA AVANZADA =====================

@app.route('/cash-reconciliation/<int:register_id>', methods=['GET', 'POST'])
@login_required
def cash_reconciliation(register_id):
    if current_user.role not in ['admin', 'manager']:
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    register = CashRegister.query.get_or_404(register_id)
    
    if register.status != 'open':
        flash('La caja ya está cerrada', 'error')
        return redirect(url_for('cash_register'))
    
    entries = CashRegisterEntry.query.filter_by(register_id=register_id).all()
    expected = float(register.openning_amount) + sum(float(e.amount) for e in entries if e.type == 'in') - sum(float(e.amount) for e in entries if e.type == 'out')
    
    if request.method == 'POST':
        recon = CashReconciliation(
            register_id=register_id,
            counted_cash=Decimal(request.form['counted_cash']),
            expected_cash=expected,
            difference=Decimal(request.form['counted_cash']) - Decimal(str(expected)),
            denomination_1=int(request.form.get('denomination_1', 0)),
            denomination_5=int(request.form.get('denomination_5', 0)),
            denomination_10=int(request.form.get('denomination_10', 0)),
            denomination_25=int(request.form.get('denomination_25', 0)),
            denomination_50=int(request.form.get('denomination_50', 0)),
            denomination_100=int(request.form.get('denomination_100', 0)),
            denomination_500=int(request.form.get('denomination_500', 0)),
            denomination_1000=int(request.form.get('denomination_1000', 0)),
            notes=request.form.get('notes', ''),
            reconciled_by=current_user.id
        )
        db.session.add(recon)
        
        register.closing_amount = Decimal(request.form['counted_cash'])
        register.difference = recon.difference
        register.status = 'closed'
        register.closed_by = current_user.id
        register.closed_at = datetime.now()
        
        db.session.commit()
        log_action('cash_reconciliation', f'Caja #{register_id} cuadrada. Diferencia: C$ {recon.difference}')
        flash(f'Caja cerrada. Diferencia: C$ {recon.difference}', 'success' if abs(float(recon.difference)) < 1 else 'warning')
        return redirect(url_for('cash_register'))
    
    return render_template('cash_reconciliation.html', register=register, expected=expected, entries=entries)

@app.route('/cash-reconciliation/history')
@login_required
def reconciliation_history():
    reconciliations = CashReconciliation.query.order_by(CashReconciliation.created_at.desc()).limit(50).all()
    return render_template('reconciliation_history.html', reconciliations=reconciliations)

# ===================== IMPORTAR/EXPORTAR DATOS =====================

@app.route('/export/products')
@login_required
def export_products():
    if current_user.role not in ['admin', 'manager']:
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Código', 'Nombre', 'Categoría', 'Precio Compra', 'Precio Venta', 'Stock', 'Stock Mínimo', 'Unidad', 'Activo'])
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    for p in products:
        writer.writerow([p.code, p.name, p.category.name if p.category else '', p.purchase_price, p.sale_price, p.stock, p.min_stock, p.unit, p.is_active])
    
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name=f'productos_{date.today().strftime("%Y%m%d")}.csv')

@app.route('/export/customers')
@login_required
def export_customers():
    if current_user.role not in ['admin', 'manager']:
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Nombre', 'RUC', 'Teléfono', 'Email', 'Dirección', 'Crédito Disponible', 'Puntos', 'Activo'])
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    for c in customers:
        writer.writerow([c.name, c.ruc, c.phone, c.email, c.address, c.credit_limit, c.loyalty_points, c.is_active])
    
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name=f'clientes_{date.today().strftime("%Y%m%d")}.csv')

@app.route('/export/invoices')
@login_required
def export_invoices():
    if current_user.role not in ['admin', 'manager']:
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end', date.today().strftime('%Y-%m-%d'))
    
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Factura', 'Fecha', 'Cliente', 'RUC', 'Subtotal', 'ISV', 'Descuento', 'Total', 'Estado', 'Método Pago', 'Vendedor'])
    invoices = Invoice.query.filter(db.func.date(Invoice.created_at) >= start_date, db.func.date(Invoice.created_at) <= end_date).order_by(Invoice.created_at.desc()).all()
    for inv in invoices:
        writer.writerow([inv.invoice_number, inv.created_at.strftime('%Y-%m-%d %H:%M'), inv.customer.name if inv.customer else 'Público', inv.customer.ruc if inv.customer else '', inv.subtotal, inv.tax_amount, inv.discount_amount, inv.total, inv.status, inv.payment_method, inv.user.username if inv.user else ''])
    
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name=f'facturas_{start_date}_{end_date}.csv')

@app.route('/import/products', methods=['POST'])
@login_required
def import_products():
    if current_user.role != 'admin':
        flash('Solo admin puede importar', 'error')
        return redirect(url_for('products'))
    
    file = request.files.get('file')
    if not file or not file.filename.endswith('.csv'):
        flash('Seleccione un archivo CSV válido', 'error')
        return redirect(url_for('products'))
    
    import csv, io
    content = file.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))
    
    imported = 0
    for row in reader:
        cat = Category.query.filter_by(name=row.get('Categoría', '')).first()
        product = Product(
            code=row.get('Código', f'P{Product.query.count()+1:04d}'),
            name=row.get('Nombre', ''),
            category_id=cat.id if cat else None,
            purchase_price=Decimal(row.get('Precio Compra', 0)),
            sale_price=Decimal(row.get('Precio Venta', 0)),
            stock=int(row.get('Stock', 0)),
            min_stock=int(row.get('Stock Mínimo', 5)),
            unit=row.get('Unidad', 'und'),
            is_active=True
        )
        db.session.add(product)
        imported += 1
    
    db.session.commit()
    flash(f'{imported} productos importados', 'success')
    return redirect(url_for('products'))

@app.route('/import/customers', methods=['POST'])
@login_required
def import_customers():
    if current_user.role != 'admin':
        flash('Solo admin puede importar', 'error')
        return redirect(url_for('customers'))
    
    file = request.files.get('file')
    if not file or not file.filename.endswith('.csv'):
        flash('Seleccione un archivo CSV válido', 'error')
        return redirect(url_for('customers'))
    
    import csv, io
    content = file.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))
    
    imported = 0
    for row in reader:
        customer = Customer(
            name=row.get('Nombre', ''),
            ruc=row.get('RUC', ''),
            phone=row.get('Teléfono', ''),
            email=row.get('Email', ''),
            address=row.get('Dirección', ''),
            credit_limit=Decimal(row.get('Límite Crédito', 0)),
            is_active=True
        )
        db.session.add(customer)
        imported += 1
    
    db.session.commit()
    flash(f'{imported} clientes importados', 'success')
    return redirect(url_for('customers'))

# ===================== EXPORTAR PDF =====================

@app.route('/invoices/<int:id>/pdf')
@login_required
def invoice_pdf(id):
    invoice = Invoice.query.get_or_404(id)
    settings = InvoiceSettings.query.first()
    if not settings:
        settings = InvoiceSettings()
    return render_template('invoice_pdf.html', invoice=invoice, settings=settings)

# ===================== SISTEMA DE SOPORTE =====================

@app.route('/help')
@login_required
def help_center():
    return render_template('help_center.html')

@app.route('/help/<module>')
@login_required
def help_module(module):
    guides = {
        'products': {'title': 'Productos', 'icon': 'fas fa-box', 'sections': [
            {'title': 'Crear Producto', 'content': 'Ir a Productos → Agregar Producto. Completar nombre, código, precio de compra y venta. El código es único para identificar el producto.'},
            {'title': 'Categorías', 'content': 'Organizar productos por categorías (Bebidas, Snacks, Limpieza, etc.). Se crean automáticamente al agregar un producto.'},
            {'title': 'Lotes y Vencimiento', 'content': 'Activar "Rastrear por lote" para productos con fecha de vencimiento. Permite gestionar lotes individuales y recibir alertas de vencimiento.'},
            {'title': 'Kits/Combos', 'content': 'Crear productos compuestos por otros. Ejemplo: "Combo Almuerzo" = Arroz + Frijol + Carne. Al vender el kit, se descuentan los componentes.'},
            {'title': 'Stock Mínimo', 'content': 'Definir el stock mínimo para recibir alertas cuando el inventario baje de ese nivel.'},
            {'title': 'Importar Productos', 'content': 'Preparar archivo CSV con columnas: Código, Nombre, Categoría, Precio Compra, Precio Venta, Stock, Stock Mínimo, Unidad. Subir desde el botón "Importar CSV".'}
        ]},
        'invoices': {'title': 'Facturación', 'icon': 'fas fa-file-invoice-dollar', 'sections': [
            {'title': 'Crear Factura', 'content': 'Ir a Facturas → Nueva Factura. Seleccionar cliente (opcional), agregar productos con cantidad y precio. Aplicar descuento si es necesario.'},
            {'title': 'Métodos de Pago', 'content': 'Contado (efectivo), Tarjeta, Transferencia, o Crédito. Para crédito, el sistema creará un plan de cuotas automáticamente.'},
            {'title': 'ISV', 'content': 'El Impuesto Sobre Ventas (15%) se calcula automáticamente según la configuración. Se puede ajustar en Configuración.'},
            {'title': 'Propina', 'content': 'Agregar propina opcional en la factura. Se suma al total.'},
            {'title': 'Imprimir', 'content': 'Dos formatos: Recibo térmico (80mm) para tickets, o Factura Normal (tamaño carta) para facturas oficiales.'},
            {'title': 'Enviar por WhatsApp', 'content': 'Desde la factura, presionar botón verde de WhatsApp. Configurar primero en Menú → WhatsApp Settings.'},
            {'title': 'Exportar PDF', 'content': 'Desde la factura, presionar botón "PDF". Se abre vista imprimible. Usar "Imprimir/Guardar PDF" del navegador para guardar como archivo.'}
        ]},
        'customers': {'title': 'Clientes', 'icon': 'fas fa-users', 'sections': [
            {'title': 'Crear Cliente', 'content': 'Ir a Clientes → Agregar Cliente. Nombre y RUC son obligatorios. El RUC es necesario para facturas fiscales.'},
            {'title': 'Puntos de Lealtad', 'content': 'Los clientes acumulan 1 punto por cada C$ 10 en compras. Puedes canjear puntos en la facturación.'},
            {'title': 'Límite de Crédito', 'content': 'Establecer el monto máximo de crédito que un cliente puede tener pendiente.'},
            {'title': 'Nivel VIP', 'content': 'Marcar clientes frecuentes como VIP para identificarlos fácilmente.'},
            {'title': 'Importar Clientes', 'content': 'Preparar CSV con: Nombre, RUC, Teléfono, Email, Dirección. Subir desde botón "Importar CSV".'}
        ]},
        'cash': {'title': 'Caja', 'icon': 'fas fa-cash-register', 'sections': [
            {'title': 'Abrir Caja', 'content': 'Al iniciar turno, presionar "Abrir Caja" e ingresar el monto inicial. Este es el fondo de caja con el que empiezas.'},
            {'title': 'Registros de Caja', 'content': 'Cada venta, gasto o movimiento se registra automáticamente. También puedes agregar entradas o salidas manuales.'},
            {'title': 'Cuadrar Caja', 'content': 'Al cerrar turno, usar "Cuadrar Caja (Detalle)". Contar el efectivo por denominaciones. El sistema calcula la diferencia automáticamente.'},
            {'title': 'Historial', 'content': 'Ver todos los cuadres anteriores en "Cuadres de Caja". Útil para auditorías.'}
        ]},
        'reports': {'title': 'Reportes', 'icon': 'fas fa-chart-bar', 'sections': [
            {'title': 'Reporte Diario', 'content': 'Resumen del día: ventas, devoluciones, gastos, ganancia neta. Ideal para el cierre del día.'},
            {'title': 'Reporte de Ganancias', 'content': 'Utilidad bruta, gastos operativos, ganancia neta. Filtrable por rango de fechas.'},
            {'title': 'Reporte de Inventario', 'content': 'Valorización del inventario actual, productos con stock bajo, productos por vencer.'},
            {'title': 'Reporte DGI', 'content': 'Reporte oficial para la Dirección General de Ingresos de Nicaragua. Incluye ISV cobrado y desglose por tipo de venta.'},
            {'title': 'Exportar', 'content': 'Todos los reportes se pueden exportar a CSV para abrir en Excel.'}
        ]},
        'credits': {'title': 'Crédito a Plazos', 'icon': 'fas fa-calendar-alt', 'sections': [
            {'title': 'Crear Plan', 'content': 'Desde una factura con pago a crédito, presionar "Plan de Cuotas". Definir número de cuotas y frecuencia.'},
            {'title': 'Registrar Pagos', 'content': 'Desde el plan, ingresar el monto del pago. El sistema actualiza el saldo automáticamente.'},
            {'title': 'Seguimiento', 'content': 'Ver todos los planes activos y completados. Alertas automáticas para cuotas vencidas.'}
        ]},
        'employees': {'title': 'Empleados', 'icon': 'fas fa-user-tie', 'sections': [
            {'title': 'Registrar Empleado', 'content': 'Ir a Personal → Empleados → Agregar. Incluir nombre, cargo, teléfono y tasa de comisión.'},
            {'title': 'Comisiones', 'content': 'La comisión se calcula automáticamente sobre las ventas del mes. Ejemplo: 5% de C$ 10,000 = C$ 500.'},
            {'title': 'Dashboard del Empleado', 'content': 'Cada empleado tiene su página con ventas del mes, comisión y total a recibir.'}
        ]},
        'settings': {'title': 'Configuración', 'icon': 'fas fa-cog', 'sections': [
            {'title': 'Datos del Negocio', 'content': 'Nombre, RUC, dirección, teléfono, email. Aparecen en las facturas impresas.'},
            {'title': 'Configuración de Impuestos', 'content': 'Tasa de ISV (15% por defecto). Se aplica a todas las ventas.'},
            {'title': 'Formato de Factura', 'content': 'Seleccionar tamaño de papel: 80mm (térmico), 58mm, Carta o Medio Carta.'},
            {'title': 'Secciones de Factura', 'content': 'Activar/desactivar: información del negocio, datos del cliente, propina, mensaje personalizado.'},
            {'title': 'WhatsApp', 'content': 'Configurar API de WhatsApp Business y mensaje predeterminado para envío de facturas.'}
        ]}
    }
    
    guide = guides.get(module)
    if not guide:
        flash('Módulo de ayuda no encontrado', 'error')
        return redirect(url_for('help_center'))
    
    return render_template('help_guide.html', guide=guide, module=module)

@app.route('/support/contact', methods=['GET', 'POST'])
@login_required
def support_contact():
    if request.method == 'POST':
        flash('Mensaje de soporte enviado. Responderemos pronto.', 'success')
        return redirect(url_for('help_center'))
    return render_template('support_contact.html')

@app.route('/support/faq')
@login_required
def support_faq():
    faqs = [
        {'q': '¿Cómo cambio la contraseña de un usuario?', 'a': 'Ir a Usuarios → Editar usuario → Cambiar contraseña. Solo los administradores pueden hacer esto.'},
        {'q': '¿Cómo registro una devolución?', 'a': 'Ir a Devoluciones → Nueva Devolución. Seleccionar la factura original y los productos a devolver. El stock se restaura automáticamente.'},
        {'q': '¿Cómo creo un presupuesto/cotización?', 'a': 'Ir a Presupuestos → Nuevo. Agregar productos y guardar. Luego puedes convertirlo en factura desde la vista del presupuesto.'},
        {'q': '¿Cómo funciona el sistema de lotes?', 'a': 'Activar "Rastrear por lote" en el producto. Luego ir a Productos → Icono de capas para agregar lotes con número y fecha de vencimiento.'},
        {'q': '¿Cómo configuro los datos de mi negocio?', 'a': 'Ir a Configuración. Ahí puedes cambiar nombre, RUC, dirección, teléfono, logo, y configuración de facturas.'},
        {'q': '¿Cómo exporto datos a Excel?', 'a': 'Ir a Configuración → Exportar (Productos, Clientes o Facturas). Se descarga un archivo CSV que se abre en Excel.'},
        {'q': '¿Cómo registro gastos del negocio?', 'a': 'Ir a Contabilidad → Nuevo Registro. Seleccionar tipo "Gasto", categoría, monto y descripción.'},
        {'q': '¿Cómo creo un producto kit/combo?', 'a': 'Primero crear los productos individuales. Luego ir a Productos → Icono de puzzle (🧩) del producto kit. Agregar componentes con cantidades.'},
        {'q': '¿Cómo configuro WhatsApp para enviar facturas?', 'a': 'Ir a WhatsApp Settings. Configurar API Key, número de teléfono, y mensaje personalizado. Luego usar el botón verde en cada factura.'},
        {'q': '¿Cómo cuadro la caja al cerrar?', 'a': 'Ir a Caja → "Cuadrar Caja (Detalle)". Contar el efectivo por denominaciones. El sistema calcula la diferencia automáticamente.'},
        {'q': '¿Cómo genero alertas de stock bajo?', 'a': 'Ir a Alertas → "Generar Alertas". El sistema busca productos por debajo del stock mínimo automáticamente.'},
        {'q': '¿Cómo veo el kardex de un producto?', 'a': 'Ir a Kardex. Seleccionar el producto. Se muestra todo el historial de entradas, salidas y ajustes.'}
    ]
    return render_template('support_faq.html', faqs=faqs)

# ===================== WHATSAPP =====================

@app.route('/whatsapp/settings')
@login_required
def whatsapp_settings():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    config = WhatsAppConfig.query.first()
    if not config:
        config = WhatsAppConfig()
        db.session.add(config)
        db.session.commit()
    return render_template('whatsapp_settings.html', config=config)

@app.route('/whatsapp/settings/save', methods=['POST'])
@login_required
def save_whatsapp_settings():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    config = WhatsAppConfig.query.first()
    if not config:
        config = WhatsAppConfig()
        db.session.add(config)
    
    config.api_key = request.form.get('api_key', '')
    config.phone_number_id = request.form.get('phone_number_id', '')
    config.business_phone = request.form.get('business_phone', '')
    config.welcome_message = request.form.get('welcome_message', '')
    config.invoice_message = request.form.get('invoice_message', '')
    config.is_active = 'is_active' in request.form
    
    db.session.commit()
    log_action('whatsapp_settings_save', 'Configuración WhatsApp guardada')
    flash('Configuración guardada', 'success')
    return redirect(url_for('whatsapp_settings'))

@app.route('/api/whatsapp/send-invoice/<int:invoice_id>')
@login_required
def send_whatsapp_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    config = WhatsAppConfig.query.first()
    
    if not config or not config.is_active:
        return jsonify({'success': False, 'message': 'WhatsApp no está configurado'})
    
    customer_phone = invoice.customer.phone if invoice.customer else None
    if not customer_phone:
        return jsonify({'success': False, 'message': 'El cliente no tiene teléfono'})
    
    business_name = InvoiceSettings.query.first().business_name if InvoiceSettings.query.first() else 'Cherry Inventario'
    message = config.invoice_message.format(
        customer_name=invoice.customer.name if invoice.customer else 'Cliente',
        invoice_number=invoice.invoice_number,
        total=format_currency(invoice.total),
        business_name=business_name
    )
    
    phone = customer_phone.replace('-', '').replace(' ', '')
    if not phone.startswith('+'):
        phone = '+505' + phone
    
    whatsapp_url = f"https://wa.me/{phone}?text={message}"
    
    log_action('whatsapp_send', f'Factura {invoice.invoice_number} enviada por WhatsApp')
    return jsonify({'success': True, 'url': whatsapp_url})

# ===================== CLIENTES =====================

@app.route('/customers')
@login_required
def customers():
    search = request.args.get('search', '')
    query = Customer.query
    if search:
        query = query.filter(db.or_(Customer.name.ilike(f'%{search}%'), Customer.ruc.ilike(f'%{search}%'), Customer.email.ilike(f'%{search}%')))
    customers = query.order_by(Customer.name).all()
    return render_template('customers.html', customers=customers, search=search)

@app.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        customer = Customer(
            name=request.form['name'],
            email=request.form.get('email', ''),
            phone=request.form.get('phone', ''),
            address=request.form.get('address', ''),
            ruc=request.form.get('ruc', ''),
            credit_limit=Decimal(request.form.get('credit_limit', 0)),
            is_vip='is_vip' in request.form
        )
        db.session.add(customer)
        db.session.commit()
        log_action('customer_add', f'Cliente: {customer.name}')
        flash('Cliente agregado exitosamente', 'success')
        return redirect(url_for('customers'))
    return render_template('customer_form.html', customer=None)

@app.route('/customers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    if request.method == 'POST':
        customer.name = request.form['name']
        customer.email = request.form.get('email', '')
        customer.phone = request.form.get('phone', '')
        customer.address = request.form.get('address', '')
        customer.ruc = request.form.get('ruc', '')
        customer.credit_limit = Decimal(request.form.get('credit_limit', 0))
        customer.is_vip = 'is_vip' in request.form
        db.session.commit()
        log_action('customer_edit', f'Cliente: {customer.name}')
        flash('Cliente actualizado exitosamente', 'success')
        return redirect(url_for('customers'))
    return render_template('customer_form.html', customer=customer)

@app.route('/customers/delete/<int:id>')
@login_required
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    db.session.delete(customer)
    db.session.commit()
    log_action('customer_delete', f'Cliente: {customer.name}')
    flash('Cliente eliminado exitosamente', 'success')
    return redirect(url_for('customers'))

@app.route('/customers/<int:id>')
@login_required
def customer_detail(id):
    customer = Customer.query.get_or_404(id)
    invoices = Invoice.query.filter_by(customer_id=id).order_by(Invoice.created_at.desc()).all()
    payments = Payment.query.filter_by(customer_id=id).order_by(Payment.created_at.desc()).all()
    return render_template('customer_detail.html', customer=customer, invoices=invoices, payments=payments)

@app.route('/customers/<int:id>/add-credit', methods=['POST'])
@login_required
def add_customer_credit(id):
    customer = Customer.query.get_or_404(id)
    amount = Decimal(request.form.get('amount', 0))
    if amount > 0:
        customer.current_credit += amount
        payment = Payment(customer_id=id, amount=amount, payment_method='credit', notes='Abono a crédito')
        db.session.add(payment)
        db.session.commit()
        log_action('credit_add', f'Crédito C$ {amount:.2f} - {customer.name}')
        flash(f'Se agregaron C$ {amount:.2f} de crédito', 'success')
    return redirect(url_for('customer_detail', id=id))

# ===================== PROVEEDORES =====================

@app.route('/suppliers')
@login_required
def suppliers():
    search = request.args.get('search', '')
    query = Supplier.query.filter_by(is_active=True)
    if search:
        query = query.filter(db.or_(Supplier.name.ilike(f'%{search}%'), Supplier.ruc.ilike(f'%{search}%')))
    suppliers = query.order_by(Supplier.name).all()
    return render_template('suppliers.html', suppliers=suppliers, search=search)

@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if request.method == 'POST':
        supplier = Supplier(
            name=request.form['name'],
            contact_name=request.form.get('contact_name', ''),
            email=request.form.get('email', ''),
            phone=request.form.get('phone', ''),
            address=request.form.get('address', ''),
            ruc=request.form.get('ruc', '')
        )
        db.session.add(supplier)
        db.session.commit()
        log_action('supplier_add', f'Proveedor: {supplier.name}')
        flash('Proveedor agregado exitosamente', 'success')
        return redirect(url_for('suppliers'))
    return render_template('supplier_form.html', supplier=None)

@app.route('/suppliers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    if request.method == 'POST':
        supplier.name = request.form['name']
        supplier.contact_name = request.form.get('contact_name', '')
        supplier.email = request.form.get('email', '')
        supplier.phone = request.form.get('phone', '')
        supplier.address = request.form.get('address', '')
        supplier.ruc = request.form.get('ruc', '')
        db.session.commit()
        log_action('supplier_edit', f'Proveedor: {supplier.name}')
        flash('Proveedor actualizado exitosamente', 'success')
        return redirect(url_for('suppliers'))
    return render_template('supplier_form.html', supplier=supplier)

@app.route('/suppliers/delete/<int:id>')
@login_required
def delete_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    supplier.is_active = False
    db.session.commit()
    log_action('supplier_delete', f'Proveedor: {supplier.name}')
    flash('Proveedor eliminado exitosamente', 'success')
    return redirect(url_for('suppliers'))

@app.route('/suppliers/<int:id>')
@login_required
def supplier_detail(id):
    supplier = Supplier.query.get_or_404(id)
    orders = PurchaseOrder.query.filter_by(supplier_id=id).order_by(PurchaseOrder.created_at.desc()).all()
    return render_template('supplier_detail.html', supplier=supplier, orders=orders)

# ===================== ÓRDENES DE COMPRA =====================

@app.route('/purchase-orders')
@login_required
def purchase_orders():
    orders = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
    return render_template('purchase_orders.html', orders=orders)

@app.route('/purchase-orders/new', methods=['GET', 'POST'])
@login_required
def new_purchase_order():
    if request.method == 'POST':
        last_order = PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).first()
        order_number = f'OC-{(last_order.id + 1 if last_order else 1):06d}'
        
        order = PurchaseOrder(
            order_number=order_number,
            supplier_id=int(request.form['supplier_id']),
            user_id=current_user.id,
            notes=request.form.get('notes', ''),
            status='pending'
        )
        
        items_data = json.loads(request.form.get('items', '[]'))
        subtotal = Decimal('0')
        for item in items_data:
            product = Product.query.get(item['product_id'])
            if product:
                item_subtotal = Decimal(str(item['quantity'])) * Decimal(str(item['unit_price']))
                po_item = PurchaseOrderItem(
                    product_id=product.id,
                    quantity=item['quantity'],
                    unit_price=Decimal(str(item['unit_price'])),
                    subtotal=item_subtotal
                )
                order.items.append(po_item)
                subtotal += item_subtotal
        
        tax_amount = subtotal * Decimal('0.15')
        order.subtotal = subtotal
        order.tax_amount = tax_amount
        order.total = subtotal + tax_amount
        
        db.session.add(order)
        db.session.commit()
        log_action('purchase_order_create', f'Orden: {order_number}')
        flash(f'Orden de compra {order_number} creada', 'success')
        return redirect(url_for('purchase_order_detail', id=order.id))
    
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    products_data = [{'id': p.id, 'code': p.code, 'name': p.name, 'purchase_price': float(p.purchase_price), 'stock': p.stock} for p in products]
    return render_template('purchase_order_form.html', suppliers=suppliers, products=products_data)

@app.route('/purchase-orders/<int:id>')
@login_required
def purchase_order_detail(id):
    order = PurchaseOrder.query.get_or_404(id)
    return render_template('purchase_order_detail.html', order=order)

@app.route('/purchase-orders/<int:id>/receive', methods=['POST'])
@login_required
def receive_purchase_order(id):
    order = PurchaseOrder.query.get_or_404(id)
    if order.status == 'pending':
        for item in order.items:
            product = Product.query.get(item.product_id)
            if product:
                product.stock += item.quantity
                product.purchase_price = item.unit_price
        
        supplier = Supplier.query.get(order.supplier_id)
        if supplier:
            supplier.balance += order.total
        
        order.status = 'received'
        order.received_at = datetime.now()
        db.session.commit()
        log_action('purchase_order_receive', f'Orden recibida: {order.order_number}')
        flash('Orden recibida y stock actualizado', 'success')
    return redirect(url_for('purchase_order_detail', id=id))

# ===================== FACTURACIÓN =====================

@app.route('/invoices')
@login_required
def invoices():
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    query = Invoice.query
    if search:
        query = query.join(Customer, Invoice.customer_id == Customer.id, isouter=True).filter(
            db.or_(Invoice.invoice_number.ilike(f'%{search}%'), Customer.name.ilike(f'%{search}%'))
        )
    if status:
        query = query.filter_by(status=status)
    invoices = query.order_by(Invoice.created_at.desc()).all()
    return render_template('invoices.html', invoices=invoices, search=search, selected_status=status)

@app.route('/invoices/new', methods=['GET', 'POST'])
@login_required
def new_invoice():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        items_data = json.loads(request.form.get('items', '[]'))
        
        if not items_data:
            flash('Agregue al menos un producto', 'error')
            return redirect(url_for('new_invoice'))

        last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
        invoice_number = f'INV-{(last_invoice.id + 1 if last_invoice else 1):06d}'

        invoice = Invoice(
            invoice_number=invoice_number,
            customer_id=int(customer_id) if customer_id else None,
            user_id=current_user.id,
            payment_method=request.form.get('payment_method', 'cash'),
            notes=request.form.get('notes', ''),
            tip_amount=Decimal(request.form.get('tip', 0)),
            status='completed'
        )

        subtotal = Decimal('0')
        for item in items_data:
            product = Product.query.get(item['product_id'])
            if product and product.stock >= item['quantity']:
                item_subtotal = Decimal(str(item['quantity'])) * product.sale_price
                invoice_item = InvoiceItem(
                    product_id=product.id,
                    quantity=item['quantity'],
                    unit_price=product.sale_price,
                    subtotal=item_subtotal
                )
                invoice.items.append(invoice_item)
                subtotal += item_subtotal
                movement = InventoryMovement(
                    product_id=product.id, type='exit', quantity=item['quantity'],
                    before_stock=product.stock + item['quantity'], after_stock=product.stock,
                    reference_type='sale', reference_id=invoice.id,
                    description=f'Venta {invoice.invoice_number}', user_id=current_user.id
                )
                db.session.add(movement)
                product.stock -= item['quantity']
            else:
                db.session.rollback()
                flash(f'Stock insuficiente para {product.name if product else "producto"}', 'error')
                return redirect(url_for('new_invoice'))

        discount_percent = Decimal(request.form.get('discount_percent', 0))
        discount_amount = subtotal * (discount_percent / 100)
        after_discount = subtotal - discount_amount
        tax_amount = after_discount * Decimal('0.15')
        total = after_discount + tax_amount + invoice.tip_amount

        invoice.subtotal = subtotal
        invoice.discount_percent = discount_percent
        invoice.discount_amount = discount_amount
        invoice.tax_amount = tax_amount
        invoice.total = total

        if invoice.payment_method == 'credit':
            invoice.is_credit = True
            invoice.paid_amount = Decimal('0')
            if customer_id:
                customer = Customer.query.get(int(customer_id))
                if customer:
                    customer.current_credit += total
        else:
            invoice.paid_amount = total

        db.session.add(invoice)
        
        active_register = CashRegister.query.filter_by(user_id=current_user.id, status='open').first()
        if active_register and invoice.payment_method == 'cash':
            entry = CashRegisterEntry(register_id=active_register.id, type='sale', amount=total, description=f'Venta {invoice_number}', invoice_id=invoice.id)
            db.session.add(entry)
        
        if customer_id:
            customer = Customer.query.get(int(customer_id))
            if customer:
                customer.loyalty_points += int(total // 10)

        db.session.commit()
        log_action('invoice_create', f'Factura: {invoice_number} - C$ {total:.2f}')
        flash(f'Factura {invoice_number} creada exitosamente', 'success')
        return redirect(url_for('view_invoice', id=invoice.id))

    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).filter(Product.stock > 0).order_by(Product.name).all()
    products_data = [{'id': p.id, 'code': p.code, 'name': p.name, 'sale_price': float(p.sale_price), 'stock': p.stock} for p in products]
    return render_template('invoice_form.html', customers=customers, products=products_data)

@app.route('/invoices/<int:id>')
@login_required
def view_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    return render_template('invoice_view.html', invoice=invoice)

@app.route('/invoices/<int:id>/cancel')
@login_required
def cancel_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.status == 'completed':
        for item in invoice.items:
            product = Product.query.get(item.product_id)
            if product:
                product.stock += item.quantity
        
        if invoice.is_credit and invoice.customer_id:
            customer = Customer.query.get(invoice.customer_id)
            if customer:
                customer.current_credit -= (invoice.total - invoice.credit_paid)
        
        invoice.status = 'cancelled'
        db.session.commit()
        log_action('invoice_cancel', f'Factura: {invoice.invoice_number}')
        flash('Factura cancelada y stock restaurado', 'success')
    return redirect(url_for('view_invoice', id=id))

@app.route('/invoices/<int:id>/add-payment', methods=['POST'])
@login_required
def add_payment(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.is_credit and invoice.credit_paid < invoice.total:
        amount = Decimal(request.form.get('amount', 0))
        if amount > 0:
            invoice.credit_paid += amount
            if invoice.credit_paid >= invoice.total:
                invoice.paid_amount = invoice.total
            
            payment = Payment(invoice_id=id, customer_id=invoice.customer_id, amount=amount, payment_method=request.form.get('payment_method', 'cash'), notes='Pago a crédito')
            db.session.add(payment)
            
            if invoice.customer_id:
                customer = Customer.query.get(invoice.customer_id)
                if customer:
                    customer.current_credit -= amount
            
            db.session.commit()
            log_action('payment_add', f'Pago C$ {amount:.2f} - Factura {invoice.invoice_number}')
            flash(f'Pago de C$ {amount:.2f} registrado', 'success')
    return redirect(url_for('view_invoice', id=id))

@app.route('/invoices/<int:id>/print')
@login_required
def print_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    return render_template('print_receipt.html', invoice=invoice)

# ===================== DEVOLUCIONES =====================

@app.route('/returns')
@login_required
def returns():
    returns = Return.query.order_by(Return.created_at.desc()).all()
    return render_template('returns.html', returns=returns)

@app.route('/returns/new/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
def new_return(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    if request.method == 'POST':
        last_return = Return.query.order_by(Return.id.desc()).first()
        return_number = f'DEV-{(last_return.id + 1 if last_return else 1):06d}'
        
        return_doc = Return(
            return_number=return_number,
            invoice_id=invoice_id,
            customer_id=invoice.customer_id,
            user_id=current_user.id,
            reason=request.form.get('reason', ''),
            status='completed'
        )
        
        items_data = json.loads(request.form.get('items', '[]'))
        total = Decimal('0')
        for item in items_data:
            product = Product.query.get(item['product_id'])
            if product:
                item_subtotal = Decimal(str(item['quantity'])) * Decimal(str(item['unit_price']))
                return_item = ReturnItem(
                    product_id=product.id,
                    quantity=item['quantity'],
                    unit_price=Decimal(str(item['unit_price'])),
                    subtotal=item_subtotal
                )
                return_doc.items.append(return_item)
                product.stock += item['quantity']
                total += item_subtotal
        
        return_doc.total = total
        db.session.add(return_doc)
        db.session.commit()
        log_action('return_create', f'Devolución: {return_number}')
        flash(f'Devolución {return_number} procesada', 'success')
        return redirect(url_for('view_invoice', id=invoice_id))
    
    return render_template('return_form.html', invoice=invoice)

@app.route('/returns/<int:id>')
@login_required
def view_return(id):
    return_doc = Return.query.get_or_404(id)
    return render_template('return_view.html', return_doc=return_doc)

# ===================== PRESUPUESTOS =====================

@app.route('/quotations')
@login_required
def quotations():
    quotations = Quotation.query.order_by(Quotation.created_at.desc()).all()
    return render_template('quotations.html', quotations=quotations)

@app.route('/quotations/new', methods=['GET', 'POST'])
@login_required
def new_quotation():
    if request.method == 'POST':
        last_quote = Quotation.query.order_by(Quotation.id.desc()).first()
        quotation_number = f'COT-{(last_quote.id + 1 if last_quote else 1):06d}'
        
        quotation = Quotation(
            quotation_number=quotation_number,
            customer_id=int(request.form['customer_id']) if request.form.get('customer_id') else None,
            user_id=current_user.id,
            notes=request.form.get('notes', ''),
            valid_until=date.today() + timedelta(days=30),
            status='pending'
        )
        
        items_data = json.loads(request.form.get('items', '[]'))
        subtotal = Decimal('0')
        for item in items_data:
            product = Product.query.get(item['product_id'])
            if product:
                item_subtotal = Decimal(str(item['quantity'])) * product.sale_price
                q_item = QuotationItem(
                    product_id=product.id,
                    quantity=item['quantity'],
                    unit_price=product.sale_price,
                    subtotal=item_subtotal
                )
                quotation.items.append(q_item)
                subtotal += item_subtotal
        
        tax_amount = subtotal * Decimal('0.15')
        quotation.subtotal = subtotal
        quotation.tax_amount = tax_amount
        quotation.total = subtotal + tax_amount
        
        db.session.add(quotation)
        db.session.commit()
        log_action('quotation_create', f'Presupuesto: {quotation_number}')
        flash(f'Presupuesto {quotation_number} creado', 'success')
        return redirect(url_for('view_quotation', id=quotation.id))
    
    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    products_data = [{'id': p.id, 'code': p.code, 'name': p.name, 'sale_price': float(p.sale_price), 'stock': p.stock} for p in products]
    return render_template('quotation_form.html', customers=customers, products=products_data)

@app.route('/quotations/<int:id>')
@login_required
def view_quotation(id):
    quotation = Quotation.query.get_or_404(id)
    return render_template('quotation_view.html', quotation=quotation)

@app.route('/quotations/<int:id>/convert', methods=['POST'])
@login_required
def convert_quotation(id):
    quotation = Quotation.query.get_or_404(id)
    if quotation.status == 'pending':
        quotation.status = 'converted'
        db.session.commit()
        log_action('quotation_convert', f'Presupuesto convertido: {quotation.quotation_number}')
        flash('Presupuesto convertido. Crear factura manualmente.', 'success')
    return redirect(url_for('view_quotation', id=id))

# ===================== CAJA =====================

@app.route('/cash-register')
@login_required
def cash_register():
    active_register = CashRegister.query.filter_by(user_id=current_user.id, status='open').first()
    today_sales = Decimal('0')
    today_entries = []
    
    if active_register:
        today_sales = db.session.query(db.func.sum(CashRegisterEntry.amount)).filter(
            CashRegisterEntry.register_id == active_register.id,
            CashRegisterEntry.type == 'sale'
        ).scalar() or 0
        today_entries = CashRegisterEntry.query.filter_by(register_id=active_register.id).order_by(CashRegisterEntry.created_at.desc()).all()
    
    return render_template('cash_register.html', active_register=active_register, today_sales=today_sales, today_entries=today_entries)

@app.route('/cash-register/open', methods=['POST'])
@login_required
def open_cash_register():
    amount = Decimal(request.form.get('amount', 0))
    register = CashRegister(user_id=current_user.id, opening_amount=amount, status='open')
    db.session.add(register)
    db.session.commit()
    log_action('register_open', f'Caja abierta: C$ {amount:.2f}')
    flash(f'Caja abierta con C$ {amount:.2f}', 'success')
    return redirect(url_for('cash_register'))

@app.route('/cash-register/close', methods=['POST'])
@login_required
def close_cash_register():
    register = CashRegister.query.filter_by(user_id=current_user.id, status='open').first()
    if register:
        actual_amount = Decimal(request.form.get('actual_amount', 0))
        entries_total = db.session.query(db.func.sum(CashRegisterEntry.amount)).filter(
            CashRegisterEntry.register_id == register.id
        ).scalar() or 0
        
        expected = register.openning_amount + entries_total
        register.closing_amount = expected
        register.actual_amount = actual_amount
        register.difference = actual_amount - expected
        register.status = 'closed'
        register.closed_at = datetime.now()
        db.session.commit()
        log_action('register_close', f'Caja cerrada. Diferencia: C$ {register.difference:.2f}')
        flash('Caja cerrada correctamente', 'success')
    return redirect(url_for('cash_register'))

@app.route('/cash-register/entry', methods=['POST'])
@login_required
def add_cash_entry():
    register = CashRegister.query.filter_by(user_id=current_user.id, status='open').first()
    if not register:
        flash('No hay caja abierta', 'error')
        return redirect(url_for('cash_register'))
    
    entry_type = request.form.get('type')
    amount = Decimal(request.form.get('amount', 0))
    description = request.form.get('description', '')
    
    if entry_type == 'withdrawal':
        amount = -abs(amount)
    
    entry = CashRegisterEntry(register_id=register.id, type=entry_type, amount=amount, description=description)
    db.session.add(entry)
    db.session.commit()
    log_action('register_entry', f'Movimiento: {entry_type} - C$ {amount:.2f}')
    flash('Movimiento registrado', 'success')
    return redirect(url_for('cash_register'))

# ===================== PUNTO DE VENTA =====================

@app.route('/pos')
@login_required
def pos():
    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).filter(Product.stock > 0).order_by(Product.name).all()
    categories = db.session.query(Product.category).distinct().filter(Product.category.isnot(None), Product.category != '').all()
    categories = [c[0] for c in categories]
    products_data = [{'id': p.id, 'code': p.code, 'name': p.name, 'sale_price': float(p.sale_price), 'stock': p.stock, 'min_stock': p.min_stock, 'category': p.category or '', 'unit': p.unit or 'und'} for p in products]
    return render_template('pos.html', customers=customers, products=products_data, categories=categories)

@app.route('/api/pos/create-sale', methods=['POST'])
@login_required
def api_create_sale():
    data = request.get_json()
    if not data.get('items'):
        return jsonify({'success': False, 'message': 'No hay productos en la venta'})
    
    customer_id = data.get('customer_id')
    items = data.get('items', [])
    payment_method = data.get('payment_method', 'cash')
    discount_percent = Decimal(str(data.get('discount', 0)))
    tip = Decimal(str(data.get('tip', 0)))
    
    last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
    invoice_number = f'POS-{(last_invoice.id + 1 if last_invoice else 1):06d}'
    
    invoice = Invoice(
        invoice_number=invoice_number,
        customer_id=int(customer_id) if customer_id else None,
        user_id=current_user.id,
        payment_method=payment_method,
        status='completed'
    )
    
    subtotal = Decimal('0')
    for item in items:
        product = Product.query.get(item['product_id'])
        if product and product.stock >= item['quantity']:
            item_subtotal = Decimal(str(item['quantity'])) * product.sale_price
            discount_amount = item_subtotal * (discount_percent / 100)
            invoice_item = InvoiceItem(
                product_id=product.id,
                quantity=item['quantity'],
                unit_price=product.sale_price,
                discount=discount_percent,
                subtotal=item_subtotal - discount_amount
            )
            invoice.items.append(invoice_item)
            subtotal += item_subtotal - discount_amount
            product.stock -= item['quantity']
        else:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Stock insuficiente para {product.name if product else "producto"}'})
    
    discount_amount = subtotal * (discount_percent / 100)
    after_discount = subtotal - discount_amount
    tax_amount = after_discount * Decimal('0.15')
    total = after_discount + tax_amount + tip
    
    invoice.subtotal = subtotal
    invoice.discount_percent = discount_percent
    invoice.discount_amount = discount_amount
    invoice.tax_amount = tax_amount
    invoice.tip_amount = tip
    invoice.total = total
    invoice.paid_amount = total
    
    db.session.add(invoice)
    
    active_register = CashRegister.query.filter_by(user_id=current_user.id, status='open').first()
    if active_register and payment_method == 'cash':
        entry = CashRegisterEntry(register_id=active_register.id, type='sale', amount=total, description=f'Venta {invoice_number}', invoice_id=invoice.id)
        db.session.add(entry)
    
    if customer_id:
        customer = Customer.query.get(int(customer_id))
        if customer:
            customer.loyalty_points += int(total // 10)
    
    db.session.commit()
    log_action('pos_sale', f'Venta POS: {invoice_number} - C$ {total:.2f}')
    
    paid = total
    change = Decimal('0')
    if payment_method == 'cash':
        paid = Decimal(str(data.get('paid', 0)))
        change = paid - total if paid > total else Decimal('0')
    
    return jsonify({
        'success': True,
        'invoice_id': invoice.id,
        'invoice_number': invoice_number,
        'total': float(total),
        'paid': float(paid),
        'change': float(change)
    })

@app.route('/api/customers/quick-add', methods=['POST'])
@login_required
def api_quick_add_customer():
    data = request.get_json()
    customer = Customer(name=data['name'], ruc=data.get('ruc', ''), phone=data.get('phone', ''))
    db.session.add(customer)
    db.session.commit()
    return jsonify({'success': True, 'customer_id': customer.id})

@app.route('/api/products/search')
@login_required
def api_products_search():
    search = request.args.get('q', '')
    products = Product.query.filter(
        Product.is_active == True, Product.stock > 0,
        db.or_(Product.name.ilike(f'%{search}%'), Product.code.ilike(f'%{search}%'))
    ).limit(10).all()
    return jsonify([{'id': p.id, 'code': p.code, 'name': p.name, 'sale_price': float(p.sale_price), 'stock': p.stock} for p in products])

@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    daily_data = db.session.query(
        db.func.date(Invoice.created_at).label('date'),
        db.func.sum(Invoice.total).label('total')
    ).filter(
        db.func.date(Invoice.created_at) >= thirty_days_ago,
        Invoice.status == 'completed'
    ).group_by(db.func.date(Invoice.created_at)).order_by('date').all()
    return jsonify([{'date': str(d.date), 'total': float(d.total)} for d in daily_data])

# ===================== REPORTES =====================

@app.route('/reports')
@login_required
def reports():
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    daily_sales = db.session.query(db.func.sum(Invoice.total)).filter(db.func.date(Invoice.created_at) == today, Invoice.status == 'completed').scalar() or 0
    monthly_sales = db.session.query(db.func.sum(Invoice.total)).filter(db.func.date(Invoice.created_at) >= month_start, Invoice.status == 'completed').scalar() or 0
    yearly_sales = db.session.query(db.func.sum(Invoice.total)).filter(db.func.date(Invoice.created_at) >= year_start, Invoice.status == 'completed').scalar() or 0
    daily_invoices = Invoice.query.filter(db.func.date(Invoice.created_at) == today, Invoice.status == 'completed').count()
    monthly_invoices = Invoice.query.filter(db.func.date(Invoice.created_at) >= month_start, Invoice.status == 'completed').count()

    top_products = db.session.query(
        Product.name, db.func.sum(InvoiceItem.quantity).label('total_sold')
    ).join(InvoiceItem).join(Invoice).filter(Invoice.status == 'completed').group_by(Product.name).order_by(db.desc('total_sold')).limit(10).all()

    return render_template('reports.html', daily_sales=daily_sales, monthly_sales=monthly_sales, yearly_sales=yearly_sales, daily_invoices=daily_invoices, monthly_invoices=monthly_invoices, top_products=top_products)

@app.route('/reports/daily')
@login_required
def daily_report():
    today = date.today()
    sales = Invoice.query.filter(db.func.date(Invoice.created_at) == today, Invoice.status == 'completed').all()
    total_sales = sum(float(inv.total) for inv in sales)
    total_tax = sum(float(inv.tax_amount) for inv in sales)
    cash_sales = sum(float(inv.total) for inv in sales if inv.payment_method == 'cash')
    card_sales = sum(float(inv.total) for inv in sales if inv.payment_method == 'card')
    credit_sales = sum(float(inv.total) for inv in sales if inv.payment_method == 'credit')
    
    product_sales = db.session.query(
        Product.name, db.func.sum(InvoiceItem.quantity).label('quantity'), db.func.sum(InvoiceItem.subtotal).label('total')
    ).join(InvoiceItem).join(Invoice).filter(db.func.date(Invoice.created_at) == today, Invoice.status == 'completed').group_by(Product.name).all()
    
    return render_template('daily_report.html', sales=sales, total_sales=total_sales, total_tax=total_tax, cash_sales=cash_sales, card_sales=card_sales, credit_sales=credit_sales, product_sales=product_sales, report_date=today)

@app.route('/reports/profit')
@login_required
def profit_report():
    start_date = request.args.get('start', date.today().replace(day=1).isoformat())
    end_date = request.args.get('end', date.today().isoformat())
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    sales = Invoice.query.filter(db.func.date(Invoice.created_at) >= start, db.func.date(Invoice.created_at) <= end, Invoice.status == 'completed').all()
    
    total_revenue = sum(float(inv.total) for inv in sales)
    total_tax = sum(float(inv.tax_amount) for inv in sales)
    
    product_costs = db.session.query(
        db.func.sum(PurchaseOrderItem.subtotal)
    ).join(PurchaseOrder).filter(
        PurchaseOrder.status == 'received',
        db.func.date(PurchaseOrder.received_at) >= start,
        db.func.date(PurchaseOrder.received_at) <= end
    ).scalar() or 0
    
    profit = total_revenue - float(product_costs)
    margin = (profit / total_revenue * 100) if total_revenue > 0 else 0
    
    return render_template('profit_report.html', total_revenue=total_revenue, total_tax=total_tax, product_costs=float(product_costs), profit=profit, margin=margin, start_date=start_date, end_date=end_date)

@app.route('/reports/inventory')
@login_required
def inventory_report():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    total_value = sum(float(p.purchase_price * p.stock) for p in products)
    total_retail = sum(float(p.sale_price * p.stock) for p in products)
    return render_template('inventory_report.html', products=products, total_value=total_value, total_retail=total_retail)

# ===================== GESTIÓN DE USUARIOS =====================

@app.route('/users')
@login_required
def users():
    if current_user.role != 'admin':
        flash('No tiene permisos para acceder', 'error')
        return redirect(url_for('dashboard'))
    users = User.query.order_by(User.full_name).all()
    return render_template('users.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User(username=request.form['username'], full_name=request.form['full_name'], role=request.form.get('role', 'cashier'))
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.commit()
        log_action('user_add', f'Usuario: {user.username}')
        flash('Usuario creado exitosamente', 'success')
        return redirect(url_for('users'))
    return render_template('user_form.html', user=None)

@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.username = request.form['username']
        user.full_name = request.form['full_name']
        user.role = request.form.get('role', 'cashier')
        user.is_active_user = 'is_active_user' in request.form
        if request.form.get('password'):
            user.set_password(request.form['password'])
        db.session.commit()
        log_action('user_edit', f'Usuario: {user.username}')
        flash('Usuario actualizado', 'success')
        return redirect(url_for('users'))
    return render_template('user_form.html', user=user)

@app.route('/users/activity')
@login_required
def activity_log():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(200).all()
    return render_template('activity_log.html', logs=logs)

# ===================== CONFIGURACIÓN Y RESPALDOS =====================

@app.route('/settings')
@login_required
def settings():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    return render_template('settings.html')

@app.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    flash('Configuración guardada', 'success')
    return redirect(url_for('settings'))

@app.route('/invoice-settings')
@login_required
def invoice_settings():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    settings = InvoiceSettings.query.first()
    if not settings:
        settings = InvoiceSettings()
        db.session.add(settings)
        db.session.commit()
    return render_template('invoice_settings.html', settings=settings)

@app.route('/invoice-settings/save', methods=['POST'])
@login_required
def save_invoice_settings():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    settings = InvoiceSettings.query.first()
    if not settings:
        settings = InvoiceSettings()
        db.session.add(settings)
    
    settings.business_name = request.form.get('business_name', 'Cherry Inventario')
    settings.business_ruc = request.form.get('business_ruc', '')
    settings.business_address = request.form.get('business_address', '')
    settings.business_phone = request.form.get('business_phone', '')
    settings.business_email = request.form.get('business_email', '')
    settings.business_website = request.form.get('business_website', '')
    settings.invoice_footer = request.form.get('invoice_footer', '¡Gracias por su compra!')
    settings.invoice_note = request.form.get('invoice_note', '')
    settings.default_tax_rate = Decimal(request.form.get('default_tax_rate', 15))
    settings.invoice_prefix = request.form.get('invoice_prefix', 'INV')
    settings.paper_size = request.form.get('paper_size', '80mm')
    
    settings.show_logo = 'show_logo' in request.form
    settings.show_ruc = 'show_ruc' in request.form
    settings.show_address = 'show_address' in request.form
    settings.show_phone = 'show_phone' in request.form
    settings.show_email = 'show_email' in request.form
    settings.show_website = 'show_website' in request.form
    settings.show_customer = 'show_customer' in request.form
    settings.show_cashier = 'show_cashier' in request.form
    settings.show_barcode = 'show_barcode' in request.form
    settings.show_tax_breakdown = 'show_tax_breakdown' in request.form
    settings.show_payment_method = 'show_payment_method' in request.form
    
    db.session.commit()
    log_action('invoice_settings_save', 'Configuración de factura actualizada')
    flash('Configuración de factura guardada', 'success')
    return redirect(url_for('invoice_settings'))

@app.route('/invoices/<int:id>/print/<format_type>')
@login_required
def print_invoice_format(id, format_type):
    invoice = Invoice.query.get_or_404(id)
    settings = InvoiceSettings.query.first()
    if not settings:
        settings = InvoiceSettings()
    if format_type == 'thermal':
        return render_template('print_thermal.html', invoice=invoice, settings=settings)
    else:
        return render_template('print_normal.html', invoice=invoice, settings=settings)

@app.route('/backup')
@login_required
def backup_database():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    db_path = os.path.join(app.instance_path, 'cherry_inventory.db')
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_file = os.path.join(backup_dir, f'cherry_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
    shutil.copy2(db_path, backup_file)
    
    log_action('backup', f'Respaldo creado: {os.path.basename(backup_file)}')
    flash(f'Respaldo creado: {os.path.basename(backup_file)}', 'success')
    return redirect(url_for('settings'))

@app.route('/backup/restore', methods=['POST'])
@login_required
def restore_backup():
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    
    backup_file = request.form.get('backup_file')
    if backup_file and os.path.exists(backup_file):
        db_path = os.path.join(app.instance_path, 'cherry_inventory.db')
        shutil.copy2(backup_file, db_path)
        log_action('backup_restore', f'Respaldo restaurado: {os.path.basename(backup_file)}')
        flash('Base de datos restaurada. Reinicie la aplicación.', 'success')
    else:
        flash('Archivo de respaldo no encontrado', 'error')
    return redirect(url_for('settings'))

@app.route('/backup/download/<filename>')
@login_required
def download_backup(filename):
    if current_user.role != 'admin':
        flash('No tiene permisos', 'error')
        return redirect(url_for('dashboard'))
    backup_dir = os.path.join(os.path.dirname(os.path.join(app.instance_path, 'cherry_inventory.db')), 'backups')
    return send_file(os.path.join(backup_dir, filename), as_attachment=True)

# ===================== INICIALIZACIÓN =====================

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.first():
            admin = User(username='admin', full_name='Administrador', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            
            cashier = User(username='cajero', full_name='Cajero General', role='cashier')
            cashier.set_password('cajero123')
            db.session.add(cashier)
            
            db.session.commit()
            print("Usuarios creados: admin/admin123 y cajero/cajero123")

def open_browser():
    import time
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:5000')

def check_updates_on_startup():
    try:
        from updater_v2 import check_and_update
        print("Verificando actualizaciones...")
        if check_and_update():
            print("Aplicacion actualizada. Reiniciando...")
            if getattr(sys, 'frozen', False):
                os.execl(sys.executable, sys.executable, *sys.argv)
            else:
                os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception as e:
        print(f"Error al verificar actualizaciones: {e}")

if __name__ == '__main__':
    init_db()
    if getattr(sys, 'frozen', False):
        check_updates_on_startup()
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        print("Iniciando Cherry Inventario...")
        print("El navegador se abrira automaticamente...")
        app.run(host='127.0.0.1', port=5000, debug=False)
    else:
        app.run(debug=True, port=5000)
