import os
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
import google.generativeai as genai

# ==================== APP CONFIG ====================
app = Flask(__name__)
app.secret_key = "supersecretkey_change_this_in_production_2024"
load_dotenv()

# ==================== GEMINI API SETUP ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_ENABLED = False

print("\n" + "="*70)
print("🔍 AI Configuration Status:")
print("="*70)

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        GEMINI_ENABLED = True
        print("✅ Gemini API: Configured")
        print("Mode: 🤖 AI-Powered (Gemini)")
    except Exception as e:
        print(f"⚠️ Gemini initialization failed: {e}")
        print("Mode: 🔌 Pattern-Based (Fallback)")
else:
    print("⚠️ Gemini API Key: Not Set")
    print("Mode: 🔌 Pattern-Based (Smart SQL Generation)")

print("="*70 + "\n")

# ==================== DATABASE SETUP ====================
def setup_database():
    """Initialize database connection"""
    try:
        db_uri = os.getenv("DATABASE_URI")
        if not db_uri:
            db_path = (Path(__file__).parent / "ecommerce.db").absolute()
            db_uri = f"sqlite:///{db_path}"
            print(f"📊 Database: {db_path}")
        
        engine = create_engine(db_uri, poolclass=NullPool, echo=False)
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✅ Database connected successfully\n")
        
        create_tables(engine)
        populate_sample_data(engine)
        return engine
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def create_tables(engine):
    """Create all required tables"""
    tables = {
        'users': """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        'products': """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                mrp REAL,
                category TEXT,
                subcategory TEXT,
                brand TEXT,
                rating REAL,
                num_reviews INTEGER DEFAULT 0,
                description TEXT,
                image_path TEXT,
                stock INTEGER DEFAULT 100,
                tags TEXT
            )
        """,
        'cart': """
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (product_id) REFERENCES products(id),
                UNIQUE(user_id, product_id)
            )
        """,
        'orders': """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                total REAL NOT NULL,
                status TEXT DEFAULT 'placed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """,
        'order_items': """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """,
        'interactions': """
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                duration INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """
    }
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_interactions_product ON interactions(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)",
        "CREATE INDEX IF NOT EXISTS idx_products_rating ON products(rating)"
    ]
    
    try:
        with engine.connect() as conn:
            for table_name, table_sql in tables.items():
                conn.execute(text(table_sql))
            
            for index_sql in indexes:
                conn.execute(text(index_sql))
            
            conn.commit()
            
            result = conn.execute(text("SELECT COUNT(*) FROM products"))
            count = result.fetchone()[0]
            print(f"✅ Tables created | Products: {count}")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")

def populate_sample_data(engine):
    """Generate 1000 sample products"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM products"))
            if result.fetchone()[0] >= 1000:
                return
            
            categories = {
                'Men': {'T-Shirts': ['Cotton T-Shirt', 'Polo Shirt', 'V-Neck Tee'], 'Shirts': ['Casual Shirt', 'Formal Shirt']},
                'Women': {'Tops': ['Blouse', 'Tank Top'], 'Dresses': ['Maxi Dress', 'Midi Dress']},
                'Kids': {'Boys': ['Kids T-Shirt'], 'Girls': ['Girls Dress']},
                'Accessories': {'Bags': ['Backpack', 'Tote Bag']}
            }
            
            brands = ['Nike', 'Adidas', 'Puma', 'H&M', 'Zara', 'Levis']
            colors = ['Black', 'White', 'Navy', 'Grey', 'Red', 'Blue']
            
            conn.execute(text("DELETE FROM products"))
            conn.commit()
            
            products = []
            for i in range(1, 1001):
                cat = random.choice(list(categories.keys()))
                subcat = random.choice(list(categories[cat].keys()))
                ptype = random.choice(categories[cat][subcat])
                brand = random.choice(brands)
                color = random.choice(colors)
                
                price = random.randint(299, 9500)
                mrp = int(price * random.uniform(1.3, 1.8))
                
                products.append({
                    "id": i, "name": f"{brand} {color} {ptype}",
                    "price": price, "mrp": mrp,
                    "category": cat, "subcategory": subcat, "brand": brand,
                    "rating": round(random.uniform(3.2, 4.9), 1),
                    "num_reviews": random.randint(10, 5000),
                    "description": f"{color} {ptype} from {brand}",
                    "image_path": f"/static/imgs/downloaded_images/{((i-1)%35)+1}.jpg",
                    "stock": random.randint(50, 500),
                    "tags": f"{cat},{brand},{color}".lower()
                })
                
                if len(products) == 100:
                    conn.execute(text("""
                        INSERT INTO products (id, name, price, mrp, category, subcategory, brand, rating, 
                                            num_reviews, description, image_path, stock, tags)
                        VALUES (:id, :name, :price, :mrp, :category, :subcategory, :brand, :rating, 
                                :num_reviews, :description, :image_path, :stock, :tags)
                    """), products)
                    conn.commit()
                    products = []
            
            if products:
                conn.execute(text("""
                    INSERT INTO products (id, name, price, mrp, category, subcategory, brand, rating, 
                                        num_reviews, description, image_path, stock, tags)
                    VALUES (:id, :name, :price, :mrp, :category, :subcategory, :brand, :rating, 
                            :num_reviews, :description, :image_path, :stock, :tags)
                """), products)
                conn.commit()
            
            print("✅ 1000 products generated")
    except Exception as e:
        print(f"⚠️ Error populating data: {e}")

db_engine = setup_database()

# ==================== DATABASE SCHEMA ====================
def get_database_schema():
    """Get detailed database schema with sample data"""
    try:
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            
            schema = {}
            for table in tables:
                # Get column info
                result = conn.execute(text(f"PRAGMA table_info({table})"))
                columns = [{"name": row[1], "type": row[2]} for row in result]
                
                # Get sample data
                result = conn.execute(text(f"SELECT * FROM {table} LIMIT 2"))
                sample_rows = [dict(zip([col['name'] for col in columns], row)) for row in result]
                
                schema[table] = {
                    "columns": columns,
                    "sample_data": sample_rows
                }
            
            return schema
    except Exception as e:
        print(f"Error getting schema: {e}")
        return {}

# ==================== GEMINI SQL GENERATION ====================
def generate_sql_with_gemini(question, schema):
    """Use Gemini API to generate SQL with context awareness"""
    if not GEMINI_ENABLED:
        return None
    
    try:
        # Build detailed schema description
        schema_text = "📊 **E-commerce Database Schema:**\n\n"
        
        for table_name, table_info in schema.items():
            schema_text += f"**Table: {table_name}**\n"
            schema_text += "Columns: " + ", ".join([f"{col['name']} ({col['type']})" for col in table_info['columns']]) + "\n"
            
            if table_info['sample_data']:
                schema_text += "Sample Data:\n"
                for i, row in enumerate(table_info['sample_data'][:1], 1):
                    schema_text += f"  Row {i}: {json.dumps(row, default=str)}\n"
            schema_text += "\n"
        
        # Context about the application
        context = """
This is an e-commerce database with user interactions tracked. Key insights:
- Products have categories (Men, Women, Kids, Accessories), brands, prices, ratings
- Users can view products, add to cart, place orders
- Interactions table tracks user behavior (view, click, add_to_cart, purchase)
- Orders and order_items track purchase history
"""
        
        prompt = f"""{context}

{schema_text}

**User Question:** {question}

**Instructions:**
1. Generate ONLY a valid SQLite SELECT query
2. Use proper SQL syntax with exact column names from the schema
3. Include appropriate JOINs if multiple tables are needed
4. Add ORDER BY for meaningful sorting
5. Include LIMIT (default 100) unless asking for counts/aggregates
6. For aggregations, use GROUP BY appropriately
7. Return ONLY the SQL query, no explanations, no markdown code blocks

**SQL Query:**"""

        # Generate with Gemini
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=500,
            )
        )
        
        sql = response.text.strip()
        
        # Clean up the response
        sql = sql.replace("```sql", "").replace("```", "").strip()
        sql = sql.replace("**SQL Query:**", "").strip()
        
        # Take first line if multiple lines
        if '\n' in sql:
            lines = [line.strip() for line in sql.split('\n') if line.strip()]
            sql = lines[0]
        
        # Validate it's a SELECT query
        if not sql.upper().startswith("SELECT"):
            return None
        
        # Ensure LIMIT exists for non-aggregate queries
        if "LIMIT" not in sql.upper() and not any(agg in sql.upper() for agg in ["COUNT(", "SUM(", "AVG(", "MAX(", "MIN("]):
            sql = sql.rstrip(';') + " LIMIT 100;"
        
        return sql
    
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

# ==================== PATTERN-BASED SQL GENERATION (FALLBACK) ====================
def generate_sql_from_pattern(question):
    """Smart pattern matching for common SQL queries"""
    q = question.lower().strip()
    
    def get_limit(default='10'):
        match = re.search(r'\b(\d+)\b', q)
        return match.group(1) if match else default
    
    # Database structure queries
    if re.search(r'\b(show|list|what|display)\b.*\btables?\b', q):
        return "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    
    if re.search(r'\b(describe|schema|structure)\b.*\b(products?|users?|orders?)', q):
        return "SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name;"
    
    # Product queries
    if re.search(r'\b(count|how many)\b.*\bproducts?\b', q):
        return "SELECT COUNT(*) as total_products FROM products;"
    
    if re.search(r'\b(show|list|get|display)\b.*(all)?\s*\bproducts?\b', q) and 'category' not in q:
        return "SELECT id, name, price, brand, category, rating FROM products LIMIT 100;"
    
    if re.search(r'\b(top|most|highest)\b.*\b(expensive|price)\b.*\bproducts?\b', q):
        limit = get_limit()
        return f"SELECT name, price, brand, category, rating FROM products ORDER BY price DESC LIMIT {limit};"
    
    if re.search(r'\b(cheap|cheapest|lowest)\b.*\bprice', q):
        limit = get_limit()
        return f"SELECT name, price, brand, category, rating FROM products ORDER BY price ASC LIMIT {limit};"
    
    if re.search(r'\b(top|best|highest)\b.*\b(rated|rating)\b', q):
        limit = get_limit()
        return f"SELECT name, rating, price, brand, category FROM products ORDER BY rating DESC LIMIT {limit};"
    
    if re.search(r'\b(average|avg|mean)\b.*\bprice', q):
        return "SELECT ROUND(AVG(price), 2) as average_price, COUNT(*) as total_products FROM products;"
    
    # Price range queries
    price_match = re.search(r'\bunder\s+(\d+)', q)
    if price_match:
        price = price_match.group(1)
        return f"SELECT name, price, brand, rating FROM products WHERE price < {price} ORDER BY price DESC LIMIT 100;"
    
    price_match = re.search(r'\b(above|over)\s+(\d+)', q)
    if price_match:
        price = price_match.group(2)
        return f"SELECT name, price, brand, rating FROM products WHERE price > {price} ORDER BY price ASC LIMIT 100;"
    
    # User queries
    if re.search(r'\b(count|how many)\b.*\busers?\b', q):
        return "SELECT COUNT(*) as total_users FROM users;"
    
    if re.search(r'\b(list|show|all)\b.*\busers?\b', q):
        return "SELECT id, username, email, created_at FROM users LIMIT 100;"
    
    # Order queries
    if re.search(r'\b(count|how many)\b.*\borders?\b', q):
        return "SELECT COUNT(*) as total_orders FROM orders;"
    
    if re.search(r'\b(total|sum).*\b(revenue|sales)\b', q):
        return "SELECT SUM(total) as total_revenue, COUNT(*) as total_orders, ROUND(AVG(total), 2) as avg_order_value FROM orders;"
    
    if re.search(r'\b(recent|latest)\b.*\borders?\b', q):
        limit = get_limit()
        return f"SELECT o.id, o.user_id, u.username, o.total, o.status, o.created_at FROM orders o LEFT JOIN users u ON o.user_id = u.id ORDER BY o.created_at DESC LIMIT {limit};"
    
    # Category queries
    if re.search(r'\bcategor', q):
        return "SELECT category, COUNT(*) as product_count, ROUND(AVG(price), 2) as avg_price FROM products GROUP BY category ORDER BY product_count DESC;"
    
    # Brand queries
    if re.search(r'\bbrands?\b.*\b(count|list)', q):
        return "SELECT brand, COUNT(*) as product_count, ROUND(AVG(price), 2) as avg_price FROM products GROUP BY brand ORDER BY product_count DESC LIMIT 20;"
    
    # Interaction/Analytics queries
    if re.search(r'\b(popular|most viewed|trending)\b.*\bproducts?\b', q):
        return """SELECT p.name, p.price, p.brand, COUNT(i.id) as view_count 
                  FROM products p 
                  LEFT JOIN interactions i ON p.id = i.product_id 
                  WHERE i.action = 'view' 
                  GROUP BY p.id 
                  ORDER BY view_count DESC 
                  LIMIT 20;"""
    
    if re.search(r'\buser.*\bactivity\b', q):
        return """SELECT u.username, COUNT(DISTINCT i.id) as interactions, 
                  COUNT(DISTINCT o.id) as orders, SUM(o.total) as total_spent
                  FROM users u
                  LEFT JOIN interactions i ON u.id = i.user_id
                  LEFT JOIN orders o ON u.id = o.user_id
                  GROUP BY u.id
                  ORDER BY interactions DESC
                  LIMIT 50;"""
    
    # Brand-specific queries
    brands = ['nike', 'adidas', 'puma', 'zara', 'h&m', 'levis']
    for brand in brands:
        if brand in q:
            brand_title = brand.title() if brand != 'h&m' else 'H&M'
            return f"SELECT name, price, rating, category FROM products WHERE LOWER(brand) = '{brand}' ORDER BY rating DESC LIMIT 100;"
    
    # Category-specific queries
    categories = ['men', 'women', 'kids', 'accessories']
    for cat in categories:
        if cat in q:
            return f"SELECT name, price, brand, rating FROM products WHERE LOWER(category) = '{cat}' ORDER BY rating DESC LIMIT 100;"
    
    return None

# ==================== MAIN QUERY ENDPOINT ====================
@app.route("/api/database/query", methods=["POST"])
def api_database_query():
    """Main database query endpoint with Gemini AI"""
    try:
        data = request.json
        question = data.get("question", "").strip()
        
        if not question:
            return jsonify({"status": "error", "message": "Please provide a question"}), 400
        
        if not db_engine:
            return jsonify({"status": "error", "message": "Database not connected"}), 500
        
        sql_query = None
        source = "unknown"
        
        # Try Gemini first if available
        if GEMINI_ENABLED:
            schema = get_database_schema()
            sql_query = generate_sql_with_gemini(question, schema)
            if sql_query:
                source = "gemini"
        
        # Fallback to pattern-based
        if not sql_query:
            sql_query = generate_sql_from_pattern(question)
            if sql_query:
                source = "pattern"
        
        if not sql_query:
            return jsonify({
                "status": "error",
                "message": "Could not understand your question. Try: 'Show top 10 expensive products' or 'Count all users'"
            }), 400
        
        # Execute query
        with db_engine.connect() as conn:
            result = conn.execute(text(sql_query))
            columns = list(result.keys())
            rows = result.fetchall()
            
            results = [{col: val for col, val in zip(columns, row)} for row in rows]
            
            # Generate explanation
            if source == "gemini":
                explanation = f"✨ Query generated by Gemini AI. Found {len(results)} results."
            else:
                explanation = f"🔍 Query generated by pattern matching. Found {len(results)} results."
            
            return jsonify({
                "status": "success",
                "question": question,
                "sql_query": sql_query,
                "explanation": explanation,
                "results": results,
                "row_count": len(results),
                "columns": columns,
                "source": source
            })
    
    except Exception as e:
        error_msg = str(e)
        return jsonify({
            "status": "error",
            "message": f"Query execution error: {error_msg}",
            "suggestion": "Try rephrasing your question or check the SQL syntax."
        }), 400

# ==================== OTHER API ENDPOINTS ====================
@app.route("/api/database/schema", methods=["GET"])
def api_database_schema():
    """Get database schema with sample data"""
    schema = get_database_schema()
    return jsonify({"status": "success", "schema": schema})

@app.route("/api/products", methods=["GET"])
def api_products():
    """Get all products with optional filters"""
    try:
        category = request.args.get("category")
        min_price = request.args.get("min_price", type=float)
        max_price = request.args.get("max_price", type=float)
        
        query = "SELECT * FROM products WHERE 1=1"
        params = {}
        
        if category:
            query += " AND category = :category"
            params["category"] = category
        
        if min_price is not None:
            query += " AND price >= :min_price"
            params["min_price"] = min_price
        
        if max_price is not None:
            query += " AND price <= :max_price"
            params["max_price"] = max_price
        
        query += " ORDER BY rating DESC LIMIT 1000"
        
        with db_engine.connect() as conn:
            result = conn.execute(text(query), params)
            products = [dict(zip(result.keys(), row)) for row in result]
        
        return jsonify({"status": "success", "data": products})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/users/register", methods=["POST"])
def api_register():
    """Register new user"""
    try:
        data = request.json
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        
        if not all([username, email, password]):
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        hashed_password = generate_password_hash(password)
        
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO users (username, email, password)
                VALUES (:username, :email, :password)
            """), {"username": username, "email": email, "password": hashed_password})
            conn.commit()
            user_id = result.lastrowid
        
        return jsonify({"status": "success", "message": "User registered", "user_id": user_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/api/users/login", methods=["POST"])
def api_login():
    """Login user"""
    try:
        data = request.json
        email = data.get("email")
        password = data.get("password")
        
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM users WHERE email = :email"), {"email": email})
            user = result.fetchone()
        
        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            return jsonify({
                "status": "success",
                "user": {"id": user[0], "username": user[1], "email": user[2]}
            })
        
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/interactions", methods=["POST"])
def api_log_interaction():
    """Log user interaction"""
    try:
        data = request.json
        user_id = session.get("user_id")
        
        if not user_id:
            return jsonify({"status": "error", "message": "Not logged in"}), 401
        
        product_id = data.get("product_id")
        action = data.get("action")
        duration = data.get("duration", 0)
        
        with db_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO interactions (user_id, product_id, action, duration)
                VALUES (:user_id, :product_id, :action, :duration)
            """), {"user_id": user_id, "product_id": product_id, "action": action, "duration": duration})
            conn.commit()
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================== ROUTES ====================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/database-query")
def database_query_page():
    return render_template("dataquery.html")

# ==================== MAIN ====================
if __name__ == "__main__":
    print("\n🚀 VOXE E-commerce Application with Gemini AI")
    print(f"🌐 Main: http://localhost:5000")
    print(f"💬 Database Query: http://localhost:5000/database-query")
    print(f"📊 Database: {'✅ Connected' if db_engine else '❌ Failed'}")
    print(f"🤖 Gemini AI: {'✅ Enabled' if GEMINI_ENABLED else '🔌 Pattern-Based Mode'}\n")
    
    app.run(debug=True, host="0.0.0.0", port=5000)