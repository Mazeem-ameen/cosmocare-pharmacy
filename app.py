from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from forms import LoginForm, ProductForm, ContactForm
from models import db, Product, Category, Admin
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace_this_with_a_strong_random_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def init_db():
    with app.app_context():
        db.create_all()
        if not Admin.query.filter_by(username='admin').first():
            admin = Admin(username='admin', password_hash=generate_password_hash('password123'))
            db.session.add(admin)
            db.session.commit()

        categories = ['Skincare', 'Hair Care', 'Acne Treatment', 'Vitamins', 'Beauty Products']
        for cat in categories:
            if not Category.query.filter_by(name=cat).first():
                db.session.add(Category(name=cat))
        db.session.commit()


@app.route('/')
def home():
    products = Product.query.order_by(Product.id.desc()).limit(8).all()
    reviews = [
        {'name': 'Ava Martin', 'rating': 5, 'text': 'CosmoCare Pro has transformed my skincare routine. Excellent service and real results!'},
        {'name': 'Leah Roberts', 'rating': 5, 'text': 'The product selection is incredible. My hair care routine is now so much easier.'},
        {'name': 'Emily Clark', 'rating': 4, 'text': 'Great online experience and helpful product categories. Highly recommended.'}
    ]
    return render_template('home.html', products=products, reviews=reviews)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        flash('Thank you for contacting CosmoCare Pro. We will be in touch soon.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        admin = Admin.query.filter_by(username=form.username.data).first()
        if admin and check_password_hash(admin.password_hash, form.password.data):
            session['admin_logged_in'] = True
            session['admin_username'] = admin.username
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    products = Product.query.order_by(Product.id.desc()).limit(5).all()
    low_stock_count = Product.query.filter(Product.stock <= 5).count()
    categories = Category.query.count()
    total_products = Product.query.count()
    return render_template(
        'dashboard.html',
        total_products=total_products,
        total_categories=categories,
        low_stock_count=low_stock_count,
        recent_products=products
    )


@app.route('/products')
def products():
    category_name = request.args.get('category')
    search_query = request.args.get('search')
    query = Product.query

    if category_name:
        query = query.join(Category).filter(Category.name == category_name)
    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))

    products = query.order_by(Product.id.desc()).all()
    categories = Category.query.all()
    return render_template('products.html', products=products, categories=categories, selected_category=category_name, search_query=search_query)


@app.route('/product/add', methods=['GET', 'POST'])
def add_product():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    form = ProductForm()
    form.category.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
    if form.validate_on_submit():
        filename = None
        if form.image.data:
            image = form.image.data
            if allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        product = Product(
            name=form.name.data,
            category_id=form.category.data,
            price=form.price.data,
            stock=form.stock.data,
            description=form.description.data,
            image_filename=filename
        )
        db.session.add(product)
        db.session.commit()
        flash('Product added successfully.', 'success')
        return redirect(url_for('products'))

    return render_template('product_form.html', form=form, title='Add Product')


@app.route('/product/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    product = Product.query.get_or_404(product_id)
    form = ProductForm(obj=product)
    form.category.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
    if form.validate_on_submit():
        if form.image.data:
            image = form.image.data
            if allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                product.image_filename = filename

        product.name = form.name.data
        product.category_id = form.category.data
        product.price = form.price.data
        product.stock = form.stock.data
        product.description = form.description.data
        db.session.commit()
        flash('Product updated successfully.', 'success')
        return redirect(url_for('products'))

    return render_template('product_form.html', form=form, title='Edit Product', product=product)


@app.route('/product/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    product = Product.query.get_or_404(product_id)
    if product.image_filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], product.image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully.', 'success')
    return redirect(url_for('products'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
