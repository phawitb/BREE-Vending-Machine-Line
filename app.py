from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
LIFF_ID = os.getenv("LIFF_ID", "fallback_if_not_found")

# Flask setup
app = Flask(__name__)
app.secret_key = 'mysecretkey'

# MongoDB setup
mongo_uri = "mongodb+srv://GGI1hazu1c7YGlyM:GGI1hazu1c7YGlyM@cluster0.jnfgllb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(mongo_uri, server_api=ServerApi('1'))
db = client["BREE"]
users_collection = db["users"]
vms_collection = db["vms"]

# Define vending machine ID
vm_id = "M0001"

# Function to get products from MongoDB for the given vmId
def get_products_by_vm(vm_id):
    doc = vms_collection.find_one({'vmId': vm_id})
    if doc and 'products' in doc:
        return doc['products']
    return []

# Function to count items in the cart
def get_cart_count():
    return sum(session.get('cart', {}).values())

# Route: Homepage (Product list)
@app.route('/')
def index():
    products = get_products_by_vm(vm_id)  # always fetch fresh data
    cart_count = get_cart_count()
    return render_template('index.html', products=products, cart_count=cart_count, liff_id=LIFF_ID)

# Route: Shopping cart
@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    cart_items = []
    total = 0
    products = get_products_by_vm(vm_id)  # always fetch fresh data

    for product_id, quantity in cart.items():
        for p in products:
            if p['id'] == int(product_id):
                item_total = p['price'] * quantity
                total += item_total
                cart_items.append({
                    'name': p['name'],
                    'price': p['price'],
                    'quantity': quantity,
                    'total': item_total
                })

    cart_count = get_cart_count()
    return render_template('cart.html', cart_items=cart_items, total=total, cart_count=cart_count, liff_id=LIFF_ID)

# Route: LINE profile save to MongoDB (only new user)
@app.route('/profile', methods=['POST'])
def profile():
    data = request.get_json()
    print("🎯 Received LINE Profile:", data)

    line_id = data.get('userId')
    display_name = data.get('displayName')

    if not line_id:
        return jsonify({'status': 'error', 'message': 'Missing line ID'}), 400

    # Check if user already exists
    existing_user = users_collection.find_one({'line_id': line_id})
    if existing_user:
        print("👤 User already exists:", existing_user['line_name'])
        return jsonify({"status": "ok", "message": "User already exists", "line_id": line_id})

    # Insert new user
    new_user = {
        'line_id': line_id,
        'line_name': display_name,
        'created_at': datetime.utcnow()
    }
    users_collection.insert_one(new_user)
    print("✅ New user inserted:", display_name)

    return jsonify({"status": "ok", "message": "New user inserted", "line_id": line_id})

# Route: Clear shopping cart
@app.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('cart'))

# API: Add product to cart
@app.route('/api/add_to_cart', methods=['POST'])
def api_add_to_cart():
    product_id = request.json.get('product_id')
    if not product_id:
        return jsonify({'status': 'error', 'message': 'Missing product_id'}), 400

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    session['cart'] = cart

    return jsonify({'status': 'success', 'cart': cart})

# API: Confirm order (return QR)
@app.route('/api/confirm_order', methods=['POST'])
def confirm_order():
    cart = session.get('cart', {})
    if not cart:
        return jsonify({'status': 'error', 'message': 'Cart is empty'}), 400

    print("🧾 Order confirmed:", cart)

    return jsonify({
        'status': 'success',
        'qr_url': 'https://blog.tcea.org/wp-content/uploads/2022/05/qrcode_tcea.org-1.png'
    })

# Run the app
if __name__ == '__main__':
    app.run(port=6001, debug=True)
