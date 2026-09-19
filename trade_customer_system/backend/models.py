from datetime import datetime

from app import db
from werkzeug.security import check_password_hash, generate_password_hash


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    country = db.Column(db.String(100))
    city = db.Column(db.String(100))
    industry = db.Column(db.String(100))
    website = db.Column(db.String(200))
    source = db.Column(db.String(100))
    status = db.Column(db.String(20), default='potential')
    rating = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    inquiries = db.relationship('Inquiry', backref='customer', lazy=True)
    emails = db.relationship('Email', backref='customer', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    model = db.Column(db.String(100))
    price = db.Column(db.Float)
    currency = db.Column(db.String(10), default='USD')
    min_order = db.Column(db.Integer)
    description = db.Column(db.Text)
    specs = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    inquiries = db.relationship('Inquiry', backref='product', lazy=True)

class Inquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    subject = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    quantity = db.Column(db.Integer)
    budget = db.Column(db.Float)
    currency = db.Column(db.String(10), default='USD')
    status = db.Column(db.String(20), default='pending')
    priority = db.Column(db.String(20), default='normal')
    source = db.Column(db.String(100))
    reply_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    subject = db.Column(db.String(200))
    content = db.Column(db.Text)
    status = db.Column(db.String(20), default='sent')
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    opened_at = db.Column(db.DateTime)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    related_id = db.Column(db.Integer)
    related_type = db.Column(db.String(20))
    priority = db.Column(db.String(20), default='normal')
    status = db.Column(db.String(20), default='pending')
    due_date = db.Column(db.DateTime)
    assignee = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.DateTime)
    location = db.Column(db.String(200))
    type = db.Column(db.String(50))
    participants = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
