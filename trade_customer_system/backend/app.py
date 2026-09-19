from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config.from_object('config.Config')

db = SQLAlchemy(app)
CORS(app)
jwt = JWTManager(app)

from models import Customer, Email, Event, Inquiry, Product, Task, User


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already exists'}), 400
    user = User(username=data['username'], email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'User created successfully'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user and user.check_password(data['password']):
        access_token = create_access_token(identity=user.id, expires_delta=timedelta(hours=24))
        return jsonify({'access_token': access_token, 'user': {'id': user.id, 'username': user.username, 'email': user.email}})
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/api/customers', methods=['GET'])
@jwt_required()
def get_customers():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    query = Customer.query
    if search:
        query = query.filter(Customer.company_name.contains(search) | Customer.contact_person.contains(search))
    if status:
        query = query.filter_by(status=status)
    
    customers = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'items': [{'id': c.id, 'company_name': c.company_name, 'contact_person': c.contact_person, 
                   'email': c.email, 'phone': c.phone, 'country': c.country, 'status': c.status,
                   'rating': c.rating, 'created_at': c.created_at.isoformat() if c.created_at else None} for c in customers.items],
        'total': customers.total,
        'pages': customers.pages
    })

@app.route('/api/customers/<int:id>', methods=['GET'])
@jwt_required()
def get_customer(id):
    customer = Customer.query.get_or_404(id)
    return jsonify({
        'id': customer.id,
        'company_name': customer.company_name,
        'contact_person': customer.contact_person,
        'email': customer.email,
        'phone': customer.phone,
        'country': customer.country,
        'city': customer.city,
        'industry': customer.industry,
        'website': customer.website,
        'source': customer.source,
        'status': customer.status,
        'rating': customer.rating,
        'notes': customer.notes,
        'created_at': customer.created_at.isoformat() if customer.created_at else None,
        'updated_at': customer.updated_at.isoformat() if customer.updated_at else None
    })

@app.route('/api/customers', methods=['POST'])
@jwt_required()
def create_customer():
    data = request.get_json()
    customer = Customer(
        company_name=data['company_name'],
        contact_person=data.get('contact_person'),
        email=data.get('email'),
        phone=data.get('phone'),
        country=data.get('country'),
        city=data.get('city'),
        industry=data.get('industry'),
        website=data.get('website'),
        source=data.get('source'),
        status=data.get('status', 'potential'),
        rating=data.get('rating', 0),
        notes=data.get('notes')
    )
    db.session.add(customer)
    db.session.commit()
    return jsonify({'message': 'Customer created successfully', 'id': customer.id}), 201

@app.route('/api/customers/<int:id>', methods=['PUT'])
@jwt_required()
def update_customer(id):
    customer = Customer.query.get_or_404(id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(customer, key):
            setattr(customer, key, value)
    customer.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Customer updated successfully'})

@app.route('/api/customers/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    db.session.delete(customer)
    db.session.commit()
    return jsonify({'message': 'Customer deleted successfully'})

@app.route('/api/products', methods=['GET'])
@jwt_required()
def get_products():
    products = Product.query.all()
    return jsonify([{'id': p.id, 'product_name': p.product_name, 'category': p.category, 
                     'model': p.model, 'price': p.price, 'currency': p.currency,
                     'min_order': p.min_order} for p in products])

@app.route('/api/products', methods=['POST'])
@jwt_required()
def create_product():
    data = request.get_json()
    product = Product(
        product_name=data['product_name'],
        category=data.get('category'),
        model=data.get('model'),
        price=data.get('price'),
        currency=data.get('currency', 'USD'),
        min_order=data.get('min_order'),
        description=data.get('description'),
        specs=data.get('specs')
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({'message': 'Product created successfully', 'id': product.id}), 201

@app.route('/api/inquiries', methods=['GET'])
@jwt_required()
def get_inquiries():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status', '')
    
    query = Inquiry.query
    if status:
        query = query.filter_by(status=status)
    
    inquiries = query.paginate(page=page, per_page=per_page, error_out=False)
    result = []
    for inquiry in inquiries.items:
        customer = Customer.query.get(inquiry.customer_id)
        product = Product.query.get(inquiry.product_id) if inquiry.product_id else None
        result.append({
            'id': inquiry.id,
            'customer_id': inquiry.customer_id,
            'customer_name': customer.company_name if customer else '',
            'product_id': inquiry.product_id,
            'product_name': product.product_name if product else '',
            'subject': inquiry.subject,
            'content': inquiry.content,
            'quantity': inquiry.quantity,
            'budget': inquiry.budget,
            'currency': inquiry.currency,
            'status': inquiry.status,
            'priority': inquiry.priority,
            'source': inquiry.source,
            'created_at': inquiry.created_at.isoformat() if inquiry.created_at else None
        })
    return jsonify({'items': result, 'total': inquiries.total, 'pages': inquiries.pages})

@app.route('/api/inquiries', methods=['POST'])
@jwt_required()
def create_inquiry():
    data = request.get_json()
    inquiry = Inquiry(
        customer_id=data['customer_id'],
        product_id=data.get('product_id'),
        subject=data['subject'],
        content=data.get('content'),
        quantity=data.get('quantity'),
        budget=data.get('budget'),
        currency=data.get('currency', 'USD'),
        status=data.get('status', 'pending'),
        priority=data.get('priority', 'normal'),
        source=data.get('source')
    )
    db.session.add(inquiry)
    db.session.commit()
    return jsonify({'message': 'Inquiry created successfully', 'id': inquiry.id}), 201

@app.route('/api/inquiries/<int:id>', methods=['PUT'])
@jwt_required()
def update_inquiry(id):
    inquiry = Inquiry.query.get_or_404(id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(inquiry, key):
            setattr(inquiry, key, value)
    inquiry.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Inquiry updated successfully'})

@app.route('/api/emails', methods=['GET'])
@jwt_required()
def get_emails():
    customer_id = request.args.get('customer_id', type=int)
    query = Email.query
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    emails = query.all()
    return jsonify([{'id': e.id, 'customer_id': e.customer_id, 'subject': e.subject,
                     'content': e.content, 'status': e.status,
                     'sent_at': e.sent_at.isoformat() if e.sent_at else None} for e in emails])

@app.route('/api/emails', methods=['POST'])
@jwt_required()
def send_email():
    data = request.get_json()
    email = Email(
        customer_id=data['customer_id'],
        subject=data.get('subject'),
        content=data.get('content'),
        status='sent'
    )
    db.session.add(email)
    db.session.commit()
    return jsonify({'message': 'Email recorded successfully', 'id': email.id}), 201

@app.route('/api/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    status = request.args.get('status', '')
    query = Task.query
    if status:
        query = query.filter_by(status=status)
    tasks = query.all()
    return jsonify([{'id': t.id, 'title': t.title, 'description': t.description,
                     'priority': t.priority, 'status': t.status,
                     'due_date': t.due_date.isoformat() if t.due_date else None,
                     'assignee': t.assignee} for t in tasks])

@app.route('/api/tasks', methods=['POST'])
@jwt_required()
def create_task():
    data = request.get_json()
    task = Task(
        title=data['title'],
        description=data.get('description'),
        related_id=data.get('related_id'),
        related_type=data.get('related_type'),
        priority=data.get('priority', 'normal'),
        status=data.get('status', 'pending'),
        due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
        assignee=data.get('assignee')
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({'message': 'Task created successfully', 'id': task.id}), 201

@app.route('/api/events', methods=['GET'])
@jwt_required()
def get_events():
    events = Event.query.all()
    return jsonify([{'id': e.id, 'title': e.title, 'description': e.description,
                     'event_date': e.event_date.isoformat() if e.event_date else None,
                     'location': e.location, 'type': e.type, 'participants': e.participants} for e in events])

@app.route('/api/events', methods=['POST'])
@jwt_required()
def create_event():
    data = request.get_json()
    event = Event(
        title=data['title'],
        description=data.get('description'),
        event_date=datetime.fromisoformat(data['event_date']) if data.get('event_date') else None,
        location=data.get('location'),
        type=data.get('type'),
        participants=data.get('participants')
    )
    db.session.add(event)
    db.session.commit()
    return jsonify({'message': 'Event created successfully', 'id': event.id}), 201

@app.route('/api/analytics/customers', methods=['GET'])
@jwt_required()
def customer_analytics():
    total = Customer.query.count()
    by_status = db.session.query(Customer.status, db.func.count(Customer.id)).group_by(Customer.status).all()
    by_country = db.session.query(Customer.country, db.func.count(Customer.id)).group_by(Customer.country).limit(10).all()
    
    return jsonify({
        'total': total,
        'by_status': {status: count for status, count in by_status},
        'by_country': {country: count for country, count in by_country}
    })

@app.route('/api/analytics/inquiries', methods=['GET'])
@jwt_required()
def inquiry_analytics():
    total = Inquiry.query.count()
    pending = Inquiry.query.filter_by(status='pending').count()
    replied = Inquiry.query.filter_by(status='replied').count()
    
    return jsonify({
        'total': total,
        'pending': pending,
        'replied': replied,
        'conversion_rate': round(replied / total * 100, 2) if total > 0 else 0
    })

with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@example.com').first():
        admin = User(username='admin', email='admin@example.com')
        admin.set_password('admin123')
        admin.role = 'admin'
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
