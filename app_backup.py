<<<<<<< HEAD
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3
import os
import razorpay
from dotenv import load_dotenv


# ==========================================
# FLASK APP
# ==========================================

load_dotenv()
app = Flask(__name__)

app.secret_key = "sportshop_secret_key"

# ==========================================
# RAZORPAY PAYMENT CONFIGURATION
# ==========================================

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

DATABASE = "sportshop.db"

UPLOAD_FOLDER = "static/uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


# ==========================================
# ALLOWED IMAGE
# ==========================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ==========================================
# CREATE DATABASE TABLES
# ==========================================

def init_db():

    conn = get_db()

    cursor = conn.cursor()


    # ======================================
    # USERS TABLE
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL

        )
    """)


    # ======================================
    # ADMIN TABLE
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL

        )
    """)


    # ======================================
    # PRODUCTS TABLE
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            category TEXT NOT NULL,

            price REAL NOT NULL,

            quantity INTEGER NOT NULL,

            description TEXT,

            image TEXT

        )
    """)


    # ======================================
    # ORDERS TABLE
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            total_amount REAL,

            status TEXT DEFAULT 'Pending',

            order_date TIMESTAMP
            DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # ======================================
    # ORDER ITEMS TABLE
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            order_id INTEGER,

            product_id INTEGER,

            quantity INTEGER,

            price REAL

        )
    """)


    # ======================================
    # DEFAULT ADMIN
    # ======================================

    cursor.execute("""
        INSERT OR IGNORE INTO admin
        (username, password)

        VALUES (?, ?)

    """, ("admin", "admin123"))


    conn.commit()

    conn.close()


# ==========================================
# ABOUT PAGE
# ==========================================

@app.route("/about")
def about():
    return render_template("about.html")


# ==========================================
# CONTACT PAGE
# ==========================================

@app.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        conn = get_db()

        conn.execute("""
            INSERT INTO contact (name, email, message)
            VALUES (?, ?, ?)
        """, (name, email, message))

        conn.commit()
        conn.close()

        return """
        <script>
            alert("Message sent successfully!");
            window.location.href = "/contact";
        </script>
        """

    return render_template("contact.html")

# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():

    # First open the customer login page.
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("index.html")


# ==========================================
# CUSTOMER PRODUCTS
# ==========================================

@app.route("/products")
def products():

    conn = get_db()

    products = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "products.html",
        products=products
    )

# ==========================================
# CART PAGE
# ==========================================

@app.route("/cart")
def cart():

    return render_template(
        "cart.html"
    )


# ==========================================
# CHECKOUT - COD
# ==========================================

def calculate_cart_total(cart):
    """Calculate total from current database prices and validate stock."""
    conn = get_db()
    total_amount = 0
    validated_items = []

    try:
        for item in cart:
            product_id = int(item["id"])
            requested_qty = int(item["quantity"])

            product = conn.execute(
                """
                SELECT id, name, price, quantity
                FROM products
                WHERE id = ?
                """,
                (product_id,)
            ).fetchone()

            if product is None:
                raise ValueError(f"Product ID {product_id} not found.")

            if requested_qty <= 0:
                raise ValueError("Invalid quantity.")

            if product["quantity"] < requested_qty:
                raise ValueError(
                    f"Only {product['quantity']} unit(s) of "
                    f"{product['name']} are available."
                )

            price = float(product["price"])
            total_amount += price * requested_qty

            validated_items.append({
                "id": product["id"],
                "name": product["name"],
                "price": price,
                "quantity": requested_qty
            })

        return total_amount, validated_items

    finally:
        conn.close()


def create_order_in_database(user_id, cart, status="Pending"):
    """Create an order and reduce stock after payment/COD confirmation."""
    total_amount, validated_items = calculate_cart_total(cart)

    conn = get_db()

    try:
        cursor = conn.execute(
            """
            INSERT INTO orders
            (
                user_id,
                total_amount,
                status
            )
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                total_amount,
                status
            )
        )

        order_id = cursor.lastrowid

        for item in validated_items:
            conn.execute(
                """
                INSERT INTO order_items
                (
                    order_id,
                    product_id,
                    quantity,
                    price
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["id"],
                    item["quantity"],
                    item["price"]
                )
            )

            updated = conn.execute(
                """
                UPDATE products
                SET quantity = quantity - ?
                WHERE id = ?
                AND quantity >= ?
                """,
                (
                    item["quantity"],
                    item["id"],
                    item["quantity"]
                )
            )

            if updated.rowcount != 1:
                raise ValueError(
                    f"Insufficient stock for product ID {item['id']}."
                )

        conn.commit()
        return order_id, total_amount

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        import json

        try:
            name = request.form["name"]
            phone = request.form["phone"]
            address = request.form["address"]
            city = request.form["city"]
            pincode = request.form["pincode"]
            payment_method = request.form["payment_method"]
            cart_data = request.form["cart_data"]

            cart = json.loads(cart_data)

            if not cart:
                return "Cart is empty!"

            order_id, total_amount = create_order_in_database(
                session["user_id"],
                cart,
                status="Pending"
            )

            return redirect(
                url_for(
                    "order_success",
                    order_id=order_id
                )
            )

        except (ValueError, KeyError, TypeError) as e:
            return f"Checkout error: {e}", 400

        except Exception as e:
            return f"Order failed: {e}", 500

    return render_template("checkout.html")


# ==========================================
# RAZORPAY CREATE ORDER
# ==========================================

@app.route("/create-razorpay-order", methods=["POST"])
def create_razorpay_order():

    if "user_id" not in session:
        return {"success": False, "message": "Please login first."}, 401

    import json

    try:
        data = request.get_json(silent=True) or {}
        cart = data.get("cart", [])

        if not cart:
            return {"success": False, "message": "Cart is empty."}, 400

        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            return {
                "success": False,
                "message": "Razorpay API keys are not configured in .env."
            }, 500

        total_amount, validated_items = calculate_cart_total(cart)

        # Razorpay accepts amount in paise.
        razorpay_order = razorpay_client.order.create({
            "amount": int(round(total_amount * 100)),
            "currency": "INR",
            "receipt": f"sportshop_{session['user_id']}_{os.urandom(4).hex()}",
            "payment_capture": 1
        })

        session["pending_payment"] = {
            "razorpay_order_id": razorpay_order["id"],
            "cart": validated_items,
            "total_amount": total_amount
        }

        return {
            "success": True,
            "key_id": RAZORPAY_KEY_ID,
            "order_id": razorpay_order["id"],
            "amount": int(round(total_amount * 100)),
            "currency": "INR"
        }

    except ValueError as e:
        return {"success": False, "message": str(e)}, 400

    except Exception as e:
        return {
            "success": False,
            "message": f"Razorpay order creation failed: {e}"
        }, 500


# ==========================================
# RAZORPAY PAYMENT SUCCESS / VERIFY
# ==========================================

@app.route("/payment-success", methods=["POST"])
def payment_success():

    if "user_id" not in session:
        return {"success": False, "message": "Please login first."}, 401

    try:
        data = request.get_json(silent=True) or {}

        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_signature = data.get("razorpay_signature")

        pending_payment = session.get("pending_payment")

        if not all([
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
            pending_payment
        ]):
            return {
                "success": False,
                "message": "Payment verification data is incomplete."
            }, 400

        if razorpay_order_id != pending_payment["razorpay_order_id"]:
            return {
                "success": False,
                "message": "Payment order mismatch."
            }, 400

        # Verify Razorpay signature on the server.
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })

        order_id, total_amount = create_order_in_database(
            session["user_id"],
            pending_payment["cart"],
            status="Paid"
        )

        session.pop("pending_payment", None)

        return {
            "success": True,
            "order_id": order_id,
            "payment_id": razorpay_payment_id
        }

    except razorpay.errors.SignatureVerificationError:
        return {
            "success": False,
            "message": "Payment signature verification failed."
        }, 400

    except ValueError as e:
        return {"success": False, "message": str(e)}, 400

    except Exception as e:
        return {
            "success": False,
            "message": f"Payment verification failed: {e}"
        }, 500


# ==========================================
# CUSTOMER ORDERS
# ==========================================

@app.route("/orders")
def orders():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    orders = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    order_items = {}

    for order in orders:

        items = conn.execute(
            """
            SELECT
                order_items.quantity,
                order_items.price,
                products.name
            FROM order_items
            JOIN products
                ON order_items.product_id = products.id
            WHERE order_items.order_id = ?
            """,
            (order["id"],)
        ).fetchall()

        order_items[order["id"]] = items

    conn.close()

    return render_template(
        "orders.html",
        orders=orders,
        order_items=order_items
    )

# ==========================================
# ORDER SUCCESS
# ==========================================

@app.route("/order-success/<int:order_id>")
def order_success(order_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    return render_template(
        "order_success.html",
        order_id=order_id
    )

# ==========================================
# CUSTOMER REGISTER
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]

        email = request.form["email"]

        password = request.form["password"]


        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO users
                (name, email, password)

                VALUES (?, ?, ?)
                """,

                (name, email, password)
            )

            conn.commit()

            conn.close()

            return redirect(
                url_for("login")
            )


        except sqlite3.IntegrityError:

            conn.close()

            return "Email already registered!"


    return render_template(
        "register.html"
    )


# ==========================================
# CUSTOMER LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]

        password = request.form["password"]


        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users

            WHERE email = ?
            AND password = ?
            """,

            (email, password)
        ).fetchone()

        conn.close()


        if user:

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            return redirect(
                url_for("home")
            )


        return "Invalid email or password!"


    return render_template(
        "login.html"
    )


# ==========================================
# CUSTOMER LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.pop(
        "user_id",
        None
    )

    session.pop(
        "user_name",
        None
    )

    return redirect(
        url_for("home")
    )


# ==========================================
# ADMIN LOGIN
# ==========================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]


        conn = get_db()

        admin = conn.execute(
            """
            SELECT *
            FROM admin

            WHERE username = ?
            AND password = ?
            """,

            (username, password)
        ).fetchone()

        conn.close()


        if admin:

            session["admin"] = admin["username"]

            return redirect(
                url_for("admin_dashboard")
            )


        return "Invalid Admin Username or Password!"


    return render_template(
        "admin_login.html"
    )


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    # Total Products

    product_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM products
        """
    ).fetchone()[0]


    # Total Customers

    user_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        """
    ).fetchone()[0]


    # Total Orders

    order_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM orders
        """
    ).fetchone()[0]


    # Total Sales

    total_sales = conn.execute(
        """
        SELECT COALESCE(
            SUM(total_amount), 0
        )

        FROM orders

        WHERE status != 'Cancelled'
        """
    ).fetchone()[0]


    conn.close()


    return render_template(

        "admin_dashboard.html",

        product_count=product_count,

        user_count=user_count,

        order_count=order_count,

        total_sales=total_sales

    )

@app.route("/admin/customers")
def admin_customers():

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    customers = conn.execute("""
        SELECT
            users.id,
            users.name,
            users.email,
            COUNT(DISTINCT orders.id) AS total_orders,
            COALESCE(SUM(orders.total_amount), 0) AS total_spent
        FROM users
        LEFT JOIN orders
            ON users.id = orders.user_id
        GROUP BY users.id
        ORDER BY users.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_customers.html",
        customers=customers
    )

# ==========================================
# ADMIN CUSTOMER DETAILS
# ==========================================

@app.route("/admin/customers/<int:user_id>")
def admin_customer_details(user_id):

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    customer = conn.execute("""
        SELECT
            id,
            name,
            email
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    if customer is None:
        conn.close()
        return "Customer not found!", 404

    orders = conn.execute("""
        SELECT
            id,
            total_amount,
            status,
            order_date
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "admin_customer_details.html",
        customer=customer,
        orders=orders
    )


# ==========================================
# ADMIN PRODUCT LIST
# ==========================================

@app.route("/admin/products")
def admin_products():

    if "admin" not in session:
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    products = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_products.html",
        products=products
    )

    # ==========================================
# ADMIN STOCK
# ==========================================

@app.route("/admin/stock")
def admin_stock():

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    stock = conn.execute("""
        SELECT
            id,
            name,
            category,
            price,
            quantity,
            image
        FROM products
        ORDER BY quantity ASC, id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_stock.html",
        stock=stock
    )


# ==========================================
# ADMIN ADD PRODUCT
# ==========================================

@app.route(
    "/admin/products/add",
    methods=["GET", "POST"]
)
def admin_add_product():

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    if request.method == "POST":

        name = request.form["name"]

        category = request.form["category"]

        price = request.form["price"]

        quantity = request.form["quantity"]

        description = request.form["description"]


        image = request.files.get("image")

        image_name = ""


        # IMAGE UPLOAD

        if image and image.filename:

            if allowed_file(
                image.filename
            ):

                image_name = secure_filename(
                    image.filename
                )


                os.makedirs(
                    app.config["UPLOAD_FOLDER"],
                    exist_ok=True
                )


                image.save(

                    os.path.join(

                        app.config[
                            "UPLOAD_FOLDER"
                        ],

                        image_name

                    )

                )


        conn = get_db()


        conn.execute(
            """
            INSERT INTO products

            (
                name,
                category,
                price,
                quantity,
                description,
                image
            )

            VALUES (?, ?, ?, ?, ?, ?)

            """,

            (
                name,
                category,
                price,
                quantity,
                description,
                image_name
            )
        )


        conn.commit()

        conn.close()


        return redirect(
            url_for("admin_products")
        )


    return render_template(
        "admin_add_product.html"
    )


# ==========================================
# ADMIN EDIT PRODUCT
# ==========================================

@app.route(
    "/admin/products/edit/<int:product_id>",
    methods=["GET", "POST"]
)
def admin_edit_product(product_id):

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    product = conn.execute(
        """
        SELECT *
        FROM products

        WHERE id = ?
        """,

        (product_id,)
    ).fetchone()


    if product is None:

        conn.close()

        return "Product not found!"


    if request.method == "POST":

        name = request.form["name"]

        category = request.form["category"]

        price = request.form["price"]

        quantity = request.form["quantity"]

        description = request.form["description"]


        image = request.files.get("image")

        image_name = product["image"]


        if image and image.filename:

            if allowed_file(
                image.filename
            ):

                image_name = secure_filename(
                    image.filename
                )


                os.makedirs(
                    app.config["UPLOAD_FOLDER"],
                    exist_ok=True
                )


                image.save(

                    os.path.join(

                        app.config[
                            "UPLOAD_FOLDER"
                        ],

                        image_name

                    )

                )


        conn.execute(
            """
            UPDATE products

            SET

                name = ?,

                category = ?,

                price = ?,

                quantity = ?,

                description = ?,

                image = ?

            WHERE id = ?

            """,

            (
                name,
                category,
                price,
                quantity,
                description,
                image_name,
                product_id
            )
        )


        conn.commit()

        conn.close()


        return redirect(
            url_for("admin_products")
        )


    conn.close()


    return render_template(

        "admin_edit_product.html",

        product=product

    )


# ==========================================
# ADMIN DELETE PRODUCT
# ==========================================

@app.route(
    "/admin/products/delete/<int:product_id>"
)
def admin_delete_product(product_id):

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    product = conn.execute(
        """
        SELECT image
        FROM products

        WHERE id = ?
        """,

        (product_id,)
    ).fetchone()


    if product:

        # Delete image

        if product["image"]:

            image_path = os.path.join(

                app.config[
                    "UPLOAD_FOLDER"
                ],

                product["image"]

            )


            if os.path.exists(
                image_path
            ):

                os.remove(
                    image_path
                )


        # Delete product

        conn.execute(
            """
            DELETE FROM products
            WHERE id = ?
            """,

            (product_id,)
        )


        conn.commit()


    conn.close()


    return redirect(
        url_for("admin_products")
    )





# ==========================================
# ADMIN ORDERS
# ==========================================

@app.route("/admin/orders")
def admin_orders():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()
    orders = conn.execute("""
        SELECT orders.id, orders.total_amount, orders.status, orders.order_date,
               users.name AS customer_name, users.email AS email
        FROM orders
        LEFT JOIN users ON orders.user_id = users.id
        ORDER BY orders.id DESC
    """).fetchall()

    order_items = {}
    for order in orders:
        order_items[order["id"]] = conn.execute("""
            SELECT order_items.quantity, order_items.price, products.name
            FROM order_items
            JOIN products ON order_items.product_id = products.id
            WHERE order_items.order_id = ?
        """, (order["id"],)).fetchall()

    conn.close()
    return render_template("admin_orders.html", orders=orders, order_items=order_items)


@app.route("/admin/orders/status/<int:order_id>", methods=["POST"])
def update_order_status(order_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    new_status = request.form.get("status")
    allowed_statuses = ["Pending", "Confirmed", "Shipped", "Delivered", "Cancelled"]

    if new_status not in allowed_statuses:
        return "Invalid order status", 400

    conn = get_db()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_orders"))

# ==========================================
# ADMIN ORDER DETAILS
# ==========================================

@app.route("/admin/orders/<int:order_id>")
def admin_order_details(order_id):

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    order = conn.execute(
        """
        SELECT
            orders.id,
            orders.total_amount,
            orders.status,
            orders.order_date,
            users.name AS customer_name,
            users.email AS email
        FROM orders
        LEFT JOIN users
            ON orders.user_id = users.id
        WHERE orders.id = ?
        """,
        (order_id,)
    ).fetchone()

    if order is None:
        conn.close()
        return "Order not found!", 404

    items = conn.execute(
        """
        SELECT
            order_items.quantity,
            order_items.price,
            products.name
        FROM order_items
        JOIN products
            ON order_items.product_id = products.id
        WHERE order_items.order_id = ?
        """,
        (order_id,)
    ).fetchall()

    conn.close()

    return render_template(
        "admin_order_details.html",
        order=order,
        items=items
    )



# ==========================================
# ADMIN LOGOUT
# ==========================================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    # Create upload folder

    os.makedirs(
        UPLOAD_FOLDER,
        exist_ok=True
    )


    # Create database

    init_db()


    # Run Flask

    app.run(

        debug=True,

        host="127.0.0.1",

        port=5000

=======
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3
import os
import razorpay
from dotenv import load_dotenv


# ==========================================
# FLASK APP
# ==========================================

load_dotenv()
app = Flask(__name__)

app.secret_key = "sportshop_secret_key"

# ==========================================
# RAZORPAY PAYMENT CONFIGURATION
# ==========================================

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

DATABASE = "sportshop.db"

UPLOAD_FOLDER = "static/uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


# ==========================================
# ALLOWED IMAGE
# ==========================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ==========================================
# CREATE DATABASE TABLES
# ==========================================

def init_db():

    conn = get_db()

    cursor = conn.cursor()


    # ======================================
    # USERS TABLE
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL

        )
    """)


    # ======================================
    # ADMIN TABLE
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL

        )
    """)


    # ======================================
    # PRODUCTS TABLE
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            category TEXT NOT NULL,

            price REAL NOT NULL,

            quantity INTEGER NOT NULL,

            description TEXT,

            image TEXT

        )
    """)


    # ======================================
    # ORDERS TABLE
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            total_amount REAL,

            status TEXT DEFAULT 'Pending',

            order_date TIMESTAMP
            DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # ======================================
    # ORDER ITEMS TABLE
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            order_id INTEGER,

            product_id INTEGER,

            quantity INTEGER,

            price REAL

        )
    """)


    # ======================================
    # DEFAULT ADMIN
    # ======================================

    cursor.execute("""
        INSERT OR IGNORE INTO admin
        (username, password)

        VALUES (?, ?)

    """, ("admin", "admin123"))


    conn.commit()

    conn.close()


# ==========================================
# ABOUT PAGE
# ==========================================

@app.route("/about")
def about():
    return render_template("about.html")


# ==========================================
# CONTACT PAGE
# ==========================================

@app.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        conn = get_db()

        conn.execute("""
            INSERT INTO contact (name, email, message)
            VALUES (?, ?, ?)
        """, (name, email, message))

        conn.commit()
        conn.close()

        return """
        <script>
            alert("Message sent successfully!");
            window.location.href = "/contact";
        </script>
        """

    return render_template("contact.html")

# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():

    # First open the customer login page.
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("index.html")


# ==========================================
# CUSTOMER PRODUCTS
# ==========================================

@app.route("/products")
def products():

    conn = get_db()

    products = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "products.html",
        products=products
    )

# ==========================================
# CART PAGE
# ==========================================

@app.route("/cart")
def cart():

    return render_template(
        "cart.html"
    )


# ==========================================
# CHECKOUT - COD
# ==========================================

def calculate_cart_total(cart):
    """Calculate total from current database prices and validate stock."""
    conn = get_db()
    total_amount = 0
    validated_items = []

    try:
        for item in cart:
            product_id = int(item["id"])
            requested_qty = int(item["quantity"])

            product = conn.execute(
                """
                SELECT id, name, price, quantity
                FROM products
                WHERE id = ?
                """,
                (product_id,)
            ).fetchone()

            if product is None:
                raise ValueError(f"Product ID {product_id} not found.")

            if requested_qty <= 0:
                raise ValueError("Invalid quantity.")

            if product["quantity"] < requested_qty:
                raise ValueError(
                    f"Only {product['quantity']} unit(s) of "
                    f"{product['name']} are available."
                )

            price = float(product["price"])
            total_amount += price * requested_qty

            validated_items.append({
                "id": product["id"],
                "name": product["name"],
                "price": price,
                "quantity": requested_qty
            })

        return total_amount, validated_items

    finally:
        conn.close()


def create_order_in_database(user_id, cart, status="Pending"):
    """Create an order and reduce stock after payment/COD confirmation."""
    total_amount, validated_items = calculate_cart_total(cart)

    conn = get_db()

    try:
        cursor = conn.execute(
            """
            INSERT INTO orders
            (
                user_id,
                total_amount,
                status
            )
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                total_amount,
                status
            )
        )

        order_id = cursor.lastrowid

        for item in validated_items:
            conn.execute(
                """
                INSERT INTO order_items
                (
                    order_id,
                    product_id,
                    quantity,
                    price
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["id"],
                    item["quantity"],
                    item["price"]
                )
            )

            updated = conn.execute(
                """
                UPDATE products
                SET quantity = quantity - ?
                WHERE id = ?
                AND quantity >= ?
                """,
                (
                    item["quantity"],
                    item["id"],
                    item["quantity"]
                )
            )

            if updated.rowcount != 1:
                raise ValueError(
                    f"Insufficient stock for product ID {item['id']}."
                )

        conn.commit()
        return order_id, total_amount

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        import json

        try:
            name = request.form["name"]
            phone = request.form["phone"]
            address = request.form["address"]
            city = request.form["city"]
            pincode = request.form["pincode"]
            payment_method = request.form["payment_method"]
            cart_data = request.form["cart_data"]

            cart = json.loads(cart_data)

            if not cart:
                return "Cart is empty!"

            order_id, total_amount = create_order_in_database(
                session["user_id"],
                cart,
                status="Pending"
            )

            return redirect(
                url_for(
                    "order_success",
                    order_id=order_id
                )
            )

        except (ValueError, KeyError, TypeError) as e:
            return f"Checkout error: {e}", 400

        except Exception as e:
            return f"Order failed: {e}", 500

    return render_template("checkout.html")


# ==========================================
# RAZORPAY CREATE ORDER
# ==========================================

@app.route("/create-razorpay-order", methods=["POST"])
def create_razorpay_order():

    if "user_id" not in session:
        return {"success": False, "message": "Please login first."}, 401

    import json

    try:
        data = request.get_json(silent=True) or {}
        cart = data.get("cart", [])

        if not cart:
            return {"success": False, "message": "Cart is empty."}, 400

        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            return {
                "success": False,
                "message": "Razorpay API keys are not configured in .env."
            }, 500

        total_amount, validated_items = calculate_cart_total(cart)

        # Razorpay accepts amount in paise.
        razorpay_order = razorpay_client.order.create({
            "amount": int(round(total_amount * 100)),
            "currency": "INR",
            "receipt": f"sportshop_{session['user_id']}_{os.urandom(4).hex()}",
            "payment_capture": 1
        })

        session["pending_payment"] = {
            "razorpay_order_id": razorpay_order["id"],
            "cart": validated_items,
            "total_amount": total_amount
        }

        return {
            "success": True,
            "key_id": RAZORPAY_KEY_ID,
            "order_id": razorpay_order["id"],
            "amount": int(round(total_amount * 100)),
            "currency": "INR"
        }

    except ValueError as e:
        return {"success": False, "message": str(e)}, 400

    except Exception as e:
        return {
            "success": False,
            "message": f"Razorpay order creation failed: {e}"
        }, 500


# ==========================================
# RAZORPAY PAYMENT SUCCESS / VERIFY
# ==========================================

@app.route("/payment-success", methods=["POST"])
def payment_success():

    if "user_id" not in session:
        return {"success": False, "message": "Please login first."}, 401

    try:
        data = request.get_json(silent=True) or {}

        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_signature = data.get("razorpay_signature")

        pending_payment = session.get("pending_payment")

        if not all([
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
            pending_payment
        ]):
            return {
                "success": False,
                "message": "Payment verification data is incomplete."
            }, 400

        if razorpay_order_id != pending_payment["razorpay_order_id"]:
            return {
                "success": False,
                "message": "Payment order mismatch."
            }, 400

        # Verify Razorpay signature on the server.
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })

        order_id, total_amount = create_order_in_database(
            session["user_id"],
            pending_payment["cart"],
            status="Paid"
        )

        session.pop("pending_payment", None)

        return {
            "success": True,
            "order_id": order_id,
            "payment_id": razorpay_payment_id
        }

    except razorpay.errors.SignatureVerificationError:
        return {
            "success": False,
            "message": "Payment signature verification failed."
        }, 400

    except ValueError as e:
        return {"success": False, "message": str(e)}, 400

    except Exception as e:
        return {
            "success": False,
            "message": f"Payment verification failed: {e}"
        }, 500


# ==========================================
# CUSTOMER ORDERS
# ==========================================

@app.route("/orders")
def orders():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    orders = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    order_items = {}

    for order in orders:

        items = conn.execute(
            """
            SELECT
                order_items.quantity,
                order_items.price,
                products.name
            FROM order_items
            JOIN products
                ON order_items.product_id = products.id
            WHERE order_items.order_id = ?
            """,
            (order["id"],)
        ).fetchall()

        order_items[order["id"]] = items

    conn.close()

    return render_template(
        "orders.html",
        orders=orders,
        order_items=order_items
    )

# ==========================================
# ORDER SUCCESS
# ==========================================

@app.route("/order-success/<int:order_id>")
def order_success(order_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    return render_template(
        "order_success.html",
        order_id=order_id
    )

# ==========================================
# CUSTOMER REGISTER
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]

        email = request.form["email"]

        password = request.form["password"]


        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO users
                (name, email, password)

                VALUES (?, ?, ?)
                """,

                (name, email, password)
            )

            conn.commit()

            conn.close()

            return redirect(
                url_for("login")
            )


        except sqlite3.IntegrityError:

            conn.close()

            return "Email already registered!"


    return render_template(
        "register.html"
    )


# ==========================================
# CUSTOMER LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]

        password = request.form["password"]


        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users

            WHERE email = ?
            AND password = ?
            """,

            (email, password)
        ).fetchone()

        conn.close()


        if user:

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            return redirect(
                url_for("home")
            )


        return "Invalid email or password!"


    return render_template(
        "login.html"
    )


# ==========================================
# CUSTOMER LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.pop(
        "user_id",
        None
    )

    session.pop(
        "user_name",
        None
    )

    return redirect(
        url_for("home")
    )


# ==========================================
# ADMIN LOGIN
# ==========================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]


        conn = get_db()

        admin = conn.execute(
            """
            SELECT *
            FROM admin

            WHERE username = ?
            AND password = ?
            """,

            (username, password)
        ).fetchone()

        conn.close()


        if admin:

            session["admin"] = admin["username"]

            return redirect(
                url_for("admin_dashboard")
            )


        return "Invalid Admin Username or Password!"


    return render_template(
        "admin_login.html"
    )


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    # Total Products

    product_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM products
        """
    ).fetchone()[0]


    # Total Customers

    user_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        """
    ).fetchone()[0]


    # Total Orders

    order_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM orders
        """
    ).fetchone()[0]


    # Total Sales

    total_sales = conn.execute(
        """
        SELECT COALESCE(
            SUM(total_amount), 0
        )

        FROM orders

        WHERE status != 'Cancelled'
        """
    ).fetchone()[0]


    conn.close()


    return render_template(

        "admin_dashboard.html",

        product_count=product_count,

        user_count=user_count,

        order_count=order_count,

        total_sales=total_sales

    )

@app.route("/admin/customers")
def admin_customers():

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    customers = conn.execute("""
        SELECT
            users.id,
            users.name,
            users.email,
            COUNT(DISTINCT orders.id) AS total_orders,
            COALESCE(SUM(orders.total_amount), 0) AS total_spent
        FROM users
        LEFT JOIN orders
            ON users.id = orders.user_id
        GROUP BY users.id
        ORDER BY users.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_customers.html",
        customers=customers
    )

# ==========================================
# ADMIN CUSTOMER DETAILS
# ==========================================

@app.route("/admin/customers/<int:user_id>")
def admin_customer_details(user_id):

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    customer = conn.execute("""
        SELECT
            id,
            name,
            email
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    if customer is None:
        conn.close()
        return "Customer not found!", 404

    orders = conn.execute("""
        SELECT
            id,
            total_amount,
            status,
            order_date
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "admin_customer_details.html",
        customer=customer,
        orders=orders
    )


# ==========================================
# ADMIN PRODUCT LIST
# ==========================================

@app.route("/admin/products")
def admin_products():

    if "admin" not in session:
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    products = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_products.html",
        products=products
    )

    # ==========================================
# ADMIN STOCK
# ==========================================

@app.route("/admin/stock")
def admin_stock():

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    stock = conn.execute("""
        SELECT
            id,
            name,
            category,
            price,
            quantity,
            image
        FROM products
        ORDER BY quantity ASC, id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_stock.html",
        stock=stock
    )


# ==========================================
# ADMIN ADD PRODUCT
# ==========================================

@app.route(
    "/admin/products/add",
    methods=["GET", "POST"]
)
def admin_add_product():

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    if request.method == "POST":

        name = request.form["name"]

        category = request.form["category"]

        price = request.form["price"]

        quantity = request.form["quantity"]

        description = request.form["description"]


        image = request.files.get("image")

        image_name = ""


        # IMAGE UPLOAD

        if image and image.filename:

            if allowed_file(
                image.filename
            ):

                image_name = secure_filename(
                    image.filename
                )


                os.makedirs(
                    app.config["UPLOAD_FOLDER"],
                    exist_ok=True
                )


                image.save(

                    os.path.join(

                        app.config[
                            "UPLOAD_FOLDER"
                        ],

                        image_name

                    )

                )


        conn = get_db()


        conn.execute(
            """
            INSERT INTO products

            (
                name,
                category,
                price,
                quantity,
                description,
                image
            )

            VALUES (?, ?, ?, ?, ?, ?)

            """,

            (
                name,
                category,
                price,
                quantity,
                description,
                image_name
            )
        )


        conn.commit()

        conn.close()


        return redirect(
            url_for("admin_products")
        )


    return render_template(
        "admin_add_product.html"
    )


# ==========================================
# ADMIN EDIT PRODUCT
# ==========================================

@app.route(
    "/admin/products/edit/<int:product_id>",
    methods=["GET", "POST"]
)
def admin_edit_product(product_id):

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    product = conn.execute(
        """
        SELECT *
        FROM products

        WHERE id = ?
        """,

        (product_id,)
    ).fetchone()


    if product is None:

        conn.close()

        return "Product not found!"


    if request.method == "POST":

        name = request.form["name"]

        category = request.form["category"]

        price = request.form["price"]

        quantity = request.form["quantity"]

        description = request.form["description"]


        image = request.files.get("image")

        image_name = product["image"]


        if image and image.filename:

            if allowed_file(
                image.filename
            ):

                image_name = secure_filename(
                    image.filename
                )


                os.makedirs(
                    app.config["UPLOAD_FOLDER"],
                    exist_ok=True
                )


                image.save(

                    os.path.join(

                        app.config[
                            "UPLOAD_FOLDER"
                        ],

                        image_name

                    )

                )


        conn.execute(
            """
            UPDATE products

            SET

                name = ?,

                category = ?,

                price = ?,

                quantity = ?,

                description = ?,

                image = ?

            WHERE id = ?

            """,

            (
                name,
                category,
                price,
                quantity,
                description,
                image_name,
                product_id
            )
        )


        conn.commit()

        conn.close()


        return redirect(
            url_for("admin_products")
        )


    conn.close()


    return render_template(

        "admin_edit_product.html",

        product=product

    )


# ==========================================
# ADMIN DELETE PRODUCT
# ==========================================

@app.route(
    "/admin/products/delete/<int:product_id>"
)
def admin_delete_product(product_id):

    if "admin" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    product = conn.execute(
        """
        SELECT image
        FROM products

        WHERE id = ?
        """,

        (product_id,)
    ).fetchone()


    if product:

        # Delete image

        if product["image"]:

            image_path = os.path.join(

                app.config[
                    "UPLOAD_FOLDER"
                ],

                product["image"]

            )


            if os.path.exists(
                image_path
            ):

                os.remove(
                    image_path
                )


        # Delete product

        conn.execute(
            """
            DELETE FROM products
            WHERE id = ?
            """,

            (product_id,)
        )


        conn.commit()


    conn.close()


    return redirect(
        url_for("admin_products")
    )





# ==========================================
# ADMIN ORDERS
# ==========================================

@app.route("/admin/orders")
def admin_orders():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()
    orders = conn.execute("""
        SELECT orders.id, orders.total_amount, orders.status, orders.order_date,
               users.name AS customer_name, users.email AS email
        FROM orders
        LEFT JOIN users ON orders.user_id = users.id
        ORDER BY orders.id DESC
    """).fetchall()

    order_items = {}
    for order in orders:
        order_items[order["id"]] = conn.execute("""
            SELECT order_items.quantity, order_items.price, products.name
            FROM order_items
            JOIN products ON order_items.product_id = products.id
            WHERE order_items.order_id = ?
        """, (order["id"],)).fetchall()

    conn.close()
    return render_template("admin_orders.html", orders=orders, order_items=order_items)


@app.route("/admin/orders/status/<int:order_id>", methods=["POST"])
def update_order_status(order_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    new_status = request.form.get("status")
    allowed_statuses = ["Pending", "Confirmed", "Shipped", "Delivered", "Cancelled"]

    if new_status not in allowed_statuses:
        return "Invalid order status", 400

    conn = get_db()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_orders"))

# ==========================================
# ADMIN ORDER DETAILS
# ==========================================

@app.route("/admin/orders/<int:order_id>")
def admin_order_details(order_id):

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    order = conn.execute(
        """
        SELECT
            orders.id,
            orders.total_amount,
            orders.status,
            orders.order_date,
            users.name AS customer_name,
            users.email AS email
        FROM orders
        LEFT JOIN users
            ON orders.user_id = users.id
        WHERE orders.id = ?
        """,
        (order_id,)
    ).fetchone()

    if order is None:
        conn.close()
        return "Order not found!", 404

    items = conn.execute(
        """
        SELECT
            order_items.quantity,
            order_items.price,
            products.name
        FROM order_items
        JOIN products
            ON order_items.product_id = products.id
        WHERE order_items.order_id = ?
        """,
        (order_id,)
    ).fetchall()

    conn.close()

    return render_template(
        "admin_order_details.html",
        order=order,
        items=items
    )



# ==========================================
# ADMIN LOGOUT
# ==========================================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    # Create upload folder

    os.makedirs(
        UPLOAD_FOLDER,
        exist_ok=True
    )


    # Create database

    init_db()


    # Run Flask

    app.run(

        debug=True,

        host="127.0.0.1",

        port=5000

>>>>>>> f329322b65c2c5b1f12a0ce626ab6edff97fb707
    )