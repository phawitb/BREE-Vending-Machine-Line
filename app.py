from flask import Flask, render_template, session, redirect, url_for, request, jsonify, flash, send_from_directory
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
LIFF_ID = os.getenv("LIFF_ID", "fallback_if_not_found")

app = Flask(__name__)
app.secret_key = 'mysecretkey'

# Upload setup
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# MongoDB setup
mongo_uri = "mongodb+srv://GGI1hazu1c7YGlyM:GGI1hazu1c7YGlyM@cluster0.jnfgllb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(mongo_uri, server_api=ServerApi('1'))
db = client["BREE"]
users_collection = db["users"]
vms_collection = db["vms"]

def get_products_by_vm(vm_id):
    doc = vms_collection.find_one({'vmId': vm_id})
    if doc and 'products' in doc:
        return doc['products']
    return []

def get_cart_count():
    return sum(session.get('cart', {}).values())

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def root():
    return 'Welcome. Try /M0001/'

@app.route('/liff-login')
def liff_login():
    session.pop('cart', None)
    session['has_visited'] = True
    next_url = request.args.get("next")
    vm_id = request.args.get("vmId", "M0001")
    if not next_url:
        next_url = f"/{vm_id}"
    return render_template("liff_login.html", liff_id=LIFF_ID, next_url=next_url)

@app.route('/<vm_id>/')
def index(vm_id):
    session['last_vm_id'] = vm_id
    products = get_products_by_vm(vm_id)
    cart_count = get_cart_count()
    point = session.get('point', "0")
    return render_template('index.html', products=products, cart_count=cart_count, liff_id=LIFF_ID, vm_id=vm_id, point=point)

@app.route('/<vm_id>/cart')
def cart(vm_id):
    cart = session.get('cart', {})
    cart_items = []
    total = 0
    products = get_products_by_vm(vm_id)
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
    point = session.get('point', "0")
    return render_template('cart.html', cart_items=cart_items, total=total, cart_count=cart_count, liff_id=LIFF_ID, vm_id=vm_id, point=point)

@app.route('/<vm_id>/clear_cart')
def clear_cart(vm_id):
    session.pop('cart', None)
    return redirect(url_for('cart', vm_id=vm_id))

@app.route('/<vm_id>/api/add_to_cart', methods=['POST'])
def api_add_to_cart(vm_id):
    product_id = request.json.get('product_id')
    if not product_id:
        return jsonify({'status': 'error', 'message': 'Missing product_id'}), 400
    if 'cart' not in session:
        session['cart'] = {}
    cart = session['cart']
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    session['cart'] = cart
    return jsonify({'status': 'success', 'cart': cart})

@app.route('/<vm_id>/api/confirm_order', methods=['POST'])
def confirm_order(vm_id):
    cart = session.get('cart', {})
    if not cart:
        return jsonify({'status': 'error', 'message': 'Cart is empty'}), 400
    print(f"🧾 Order confirmed from VM {vm_id}:", cart)
    return jsonify({'status': 'success', 'qr_url': 'https://blog.tcea.org/wp-content/uploads/2022/05/qrcode_tcea.org-1.png'})

@app.route('/<vm_id>/profile', methods=['GET', 'POST'])
def profile(vm_id):
    if request.method == 'POST':
        data = request.get_json()
        session['line_id'] = data.get('userId')
        session['line_name'] = data.get('displayName')
        session['user_picture'] = data.get('pictureUrl')
        point = "0"
        if data.get('userId'):
            user = users_collection.find_one({"line_id": data['userId']})
            if user:
                point = user.get('point', "0")
            else:
                users_collection.insert_one({
                    'line_id': data['userId'],
                    'line_name': data['displayName'],
                    'point': "0",
                    'created_at': datetime.utcnow()
                })
        session['point'] = point
        return jsonify({"status": "ok", "point": point})
    else:
        line_id = session.get('line_id', None)
        line_name = session.get('line_name', 'Unknown')
        user_picture = session.get('user_picture', '/static/default_user.png')
        point = session.get('point', "0")
        show_manage_button = False
        vm_doc = None
        if line_id:
            vm_doc = vms_collection.find_one({"vmId": vm_id})
            if vm_doc and 'admin' in vm_doc:
                show_manage_button = line_id in vm_doc['admin']
        return render_template('profile.html', vm_doc=vm_doc, line_id=line_id, line_name=line_name, user_picture=user_picture, vm_id=vm_id, point=point, show_manage_button=show_manage_button)

@app.route('/<vm_id>/manage')
def manage_products(vm_id):
    products = get_products_by_vm(vm_id)
    return render_template('manage.html', products=products, vm_id=vm_id)

@app.route('/<vm_id>/add_product', methods=['POST'])
def add_product(vm_id):
    name = request.form['name'].strip()
    price = float(request.form['price'])
    count = int(request.form.get('count', 0))
    image = None
    if 'image_file' in request.files:
        file = request.files['image_file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image = f'/static/uploads/{filename}'
    if not image:
        image = request.form.get('image_url', '').strip()
        if not image:
            image = '/static/default_product.jpg'
    vm_doc = vms_collection.find_one({'vmId': vm_id})
    if vm_doc:
        products = vm_doc.get('products', [])
        if any(p['name'].strip().lower() == name.lower() for p in products):
            flash(f"❌ ชื่อสินค้า '{name}' มีอยู่แล้ว ไม่สามารถเพิ่มซ้ำได้", 'danger')
            return redirect(url_for('manage_products', vm_id=vm_id))
        new_id = max((p['id'] for p in products), default=0) + 1
        products.append({'id': new_id, 'name': name, 'price': price, 'image': image, 'count': count})
        vms_collection.update_one({'vmId': vm_id}, {'$set': {'products': products}})
        flash(f"✅ เพิ่มสินค้า '{name}' สำเร็จแล้ว", 'success')
    return redirect(url_for('manage_products', vm_id=vm_id))

@app.route('/<vm_id>/delete_product', methods=['POST'])
def delete_product(vm_id):
    product_id = int(request.form['id'])
    vm_doc = vms_collection.find_one({'vmId': vm_id})
    if vm_doc:
        products = [p for p in vm_doc.get('products', []) if p['id'] != product_id]
        vms_collection.update_one({'vmId': vm_id}, {'$set': {'products': products}})
    return redirect(url_for('manage_products', vm_id=vm_id))

@app.route('/<vm_id>/update_all_products', methods=['POST'])
def update_all_products(vm_id):
    try:
        ids = request.form.getlist('id[]')
        names = request.form.getlist('name[]')
        prices = request.form.getlist('price[]')
        old_images = request.form.getlist('image[]')
        counts = request.form.getlist('count[]')
        image_files = request.files.getlist('image_file[]')
        updated_products = []
        for i in range(len(ids)):
            image = old_images[i]
            if image_files[i] and allowed_file(image_files[i].filename):
                filename = secure_filename(image_files[i].filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_files[i].save(filepath)
                image = f'/static/uploads/{filename}'
            product = {
                'id': int(ids[i]),
                'name': names[i],
                'price': float(prices[i]),
                'image': image,
                'count': int(counts[i]) if counts[i] else 0
            }
            updated_products.append(product)
        vms_collection.update_one({'vmId': vm_id}, {'$set': {'products': updated_products}})
        return redirect(url_for('manage_products', vm_id=vm_id))
    except Exception as e:
        print(f"❌ Error in update_all_products: {e}")
        return f"❌ Update failed: {e}", 500

# if __name__ == '__main__':
#     app.run(port=6002, debug=True)
