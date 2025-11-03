from flask import Flask, jsonify, request, render_template, session, redirect, url_for, flash
from pymongo import MongoClient
import urllib.parse
from bson import ObjectId
from flask_cors import CORS
from datetime import datetime
import secrets
import os
import random
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask app
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
app.secret_key = secrets.token_hex(16)
CORS(app)

# MongoDB Setup
try:
    username = "shyam"
    password = "mongodb@123"
    encoded_password = urllib.parse.quote_plus(password)
    atlas_uri = f"mongodb+srv://{username}:{encoded_password}@cluster0.1lqvxu8.mongodb.net/"
    client = MongoClient(atlas_uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ Successfully connected to MongoDB!")
    
    # Initialize collections
    db_fashion = client["fashion_recommender"]
    db_ecommerce = client["ecommerce_app"]
    
    products_col = db_fashion["products"]
    users_col = db_ecommerce["users"]
    orders_col = db_ecommerce["orders"]
    
except Exception as e:
    print(f"❌ Error connecting to MongoDB: {e}")
    client = None

def generate_sample_products(count=1000):
    categories = {
        'Men': ['T-Shirt', 'Shirt', 'Jeans', 'Hoodie', 'Jacket', 'Sweater', 'Shorts', 'Suit', 'Blazer', 'Coat'],
        'Women': ['Dress', 'Blouse', 'Skirt', 'Top', 'Jeans', 'Jumpsuit', 'Leggings', 'Sweater', 'Jacket', 'Coat'],
        'Accessories': ['Watch', 'Sunglasses', 'Hat', 'Belt', 'Bag', 'Wallet', 'Scarf', 'Gloves', 'Tie', 'Socks'],
        'Shoes': ['Sneakers', 'Boots', 'Sandals', 'Heels', 'Loafers', 'Oxfords', 'Flip Flops', 'Slippers', 'Running Shoes', 'Dress Shoes'],
        'Bags': ['Backpack', 'Handbag', 'Tote', 'Clutch', 'Crossbody', 'Satchel', 'Duffel', 'Briefcase', 'Purse', 'Waist Bag']
    }
    
    colors = ['Black', 'White', 'Red', 'Blue', 'Green', 'Yellow', 'Pink', 'Purple', 'Orange', 'Gray']
    materials = ['Cotton', 'Polyester', 'Wool', 'Silk', 'Denim', 'Leather', 'Suede', 'Linen', 'Velvet', 'Cashmere']
    
    products = []
    
    for i in range(1, count + 1):
        category = random.choice(list(categories.keys()))
        product_type = random.choice(categories[category])
        color = random.choice(colors)
        material = random.choice(materials)
        
        # Generate more varied prices
        base_price = random.uniform(10, 500)
        price = round(base_price, 2)
        mrp = round(price * random.uniform(1.2, 2.0), 2)
        
        product = {
            'id': i,
            'name': f"{color} {material} {product_type} {i}",
            'price': price,
            'mrp': mrp,
            'category': category,
            'type': product_type,
            'color': color,
            'material': material,
            'rating': round(random.uniform(3, 5), 1),
            'image': f'https://picsum.photos/seed/product-{i}/400/500',  # Unique image for each product using picsum.photos
            'description': f"High quality {color.lower()} {material.lower()} {product_type.lower()} for all occasions. Made with premium materials for maximum comfort and style.",
            'in_stock': random.choice([True, True, True, True, False])  # 80% chance of being in stock
        }
        
        # Add some products with discounts
        if random.random() > 0.7:  # 30% chance of having a discount
            product['on_sale'] = True
            product['discount_percent'] = round((1 - (price / mrp)) * 100)
        else:
            product['on_sale'] = False
            
        products.append(product)
    
    return products

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/products')
def get_products():
    try:
        if client:
            products = list(products_col.find({}).limit(100))
            for product in products:
                product['_id'] = str(product['_id'])
        else:
            products = generate_sample_products(20)
        return jsonify({"status": "success", "data": products})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>')
def get_product(product_id):
    try:
        if client:
            product = products_col.find_one({'_id': ObjectId(product_id)})
            if not product:
                return jsonify({"status": "error", "message": "Product not found"}), 404
            product['_id'] = str(product['_id'])
        else:
            products = generate_sample_products(20)
            product = next((p for p in products if p['id'] == int(product_id)), None)
            if not product:
                return jsonify({"status": "error", "message": "Product not found"}), 404
        return jsonify({"status": "success", "data": product})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not all([username, email, password]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400
    
    try:
        if client:
            if users_col.find_one({'email': email}):
                return jsonify({"status": "error", "message": "Email already exists"}), 400
            
            user = {
                'username': username,
                'email': email,
                'password': generate_password_hash(password),
                'created_at': datetime.utcnow()
            }
            result = users_col.insert_one(user)
            user_id = str(result.inserted_id)
        else:
            user_id = "sample_user_" + str(hash(email))
        
        session['user_id'] = user_id
        session['username'] = username
        
        return jsonify({
            "status": "success",
            "message": "User registered successfully",
            "user": {"id": user_id, "username": username, "email": email}
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    try:
        if client:
            user = users_col.find_one({'email': email})
            if not user or not check_password_hash(user['password'], password):
                return jsonify({"status": "error", "message": "Invalid credentials"}), 401
            user_id = str(user['_id'])
            username = user['username']
        else:
            # For demo purposes only - not secure for production
            user_id = "sample_user_" + str(hash(email))
            username = email.split('@')[0]
        
        session['user_id'] = user_id
        session['username'] = username
        
        return jsonify({
            "status": "success",
            "message": "Login successful",
            "user": {"id": user_id, "username": username, "email": email}
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"status": "success", "message": "Logged out successfully"})

@app.route('/api/cart', methods=['GET', 'POST', 'DELETE'])
def cart():
    if 'cart' not in session:
        session['cart'] = []
    
    if request.method == 'GET':
        return jsonify({"status": "success", "data": session['cart']})
    
    data = request.get_json()
    
    if request.method == 'POST':
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        # Check if product exists
        if client:
            product = products_col.find_one({'_id': ObjectId(product_id)})
            if not product:
                return jsonify({"status": "error", "message": "Product not found"}), 404
            product['_id'] = str(product['_id'])
        else:
            products = generate_sample_products(20)
            product = next((p for p in products if p['id'] == int(product_id)), None)
            if not product:
                return jsonify({"status": "error", "message": "Product not found"}), 404
        
        # Add to cart
        cart = session['cart']
        existing_item = next((item for item in cart if item['product_id'] == product_id), None)
        
        if existing_item:
            existing_item['quantity'] += quantity
        else:
            cart.append({
                'product_id': product_id,
                'name': product['name'],
                'price': product['price'],
                'image': product.get('image', '/static/imgs/placeholder.jpg'),
                'quantity': quantity
            })
        
        session['cart'] = cart
        return jsonify({"status": "success", "message": "Product added to cart", "cart": cart})
    
    elif request.method == 'DELETE':
        product_id = data.get('product_id')
        session['cart'] = [item for item in session['cart'] if item['product_id'] != product_id]
        return jsonify({"status": "success", "message": "Product removed from cart"})

@app.route('/api/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    if not session.get('cart'):
        return jsonify({"status": "error", "message": "Cart is empty"}), 400
    
    try:
        order = {
            'user_id': session['user_id'],
            'items': session['cart'],
            'total': sum(item['price'] * item['quantity'] for item in session['cart']),
            'status': 'pending',
            'created_at': datetime.utcnow()
        }
        
        if client:
            orders_col.insert_one(order)
        
        # Clear cart after successful order
        session['cart'] = []
        
        return jsonify({
            "status": "success",
            "message": "Order placed successfully",
            "order_id": str(order.get('_id', 'sample_order_id'))
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Serve static files
@app.route('/<path:path>')
def serve_static(path):
    return app.send_static_file(path)

if __name__ == '__main__':
    # Create static directories if they don't exist
    os.makedirs('static/imgs', exist_ok=True)
    app.run(debug=True, port=5000)