from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from werkzeug.utils import secure_filename
import os


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///recipes.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "your_secret_key"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


# Recipe model
class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(120), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_filename = db.Column(db.String(120), nullable=True)


# Meal Plan Model
class MealPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipes = db.relationship('Recipe', secondary='meal_plan_recipe', backref='meal_plans')


# Meal Plan Recipe Model
class MealPlanRecipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meal_plan_id = db.Column(db.Integer, db.ForeignKey('meal_plan.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)


# Shopping List Model
class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ingredient_name = db.Column(db.String(100), nullable=False)
    user = db.relationship('User', back_populates='shopping_lists')

User.shopping_lists = db.relationship('ShoppingList', back_populates='user', cascade="all, delete-orphan")


# Shopping List Item Model
class ShoppingListItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='shopping_list_items', lazy=True)

    def __repr__(self):
        return f"<ShoppingListItem {self.name}>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username is already taken.', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('recipes'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/recipes', methods=['GET'])
@login_required
def recipes():
    search_query = request.args.get('search', '').lower()
    category_filter = request.args.get('category', '')

    query = Recipe.query.filter_by(user_id=current_user.id)

    if search_query:
        query = query.filter(
            (Recipe.title.ilike(f'%{search_query}%')) |
            (Recipe.ingredients.ilike(f'%{search_query}%')) |
            (Recipe.instructions.ilike(f'%{search_query}%'))
        )

    if category_filter:
        query = query.filter_by(category=category_filter)

    recipes = query.all()

    return render_template('recipes.html', recipes=recipes)


@app.route('/add_recipe', methods=['GET', 'POST'])
@login_required
def add_recipe():
    if request.method == 'POST':
        title = request.form['title']
        instructions = request.form['instructions']
        ingredients = request.form['ingredients']
        category = request.form['category']
        image_filename = None

        if 'image' in request.files:
            image = request.files['image']
            if image and allowed_file(image.filename):
                image_filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        new_recipe = Recipe(
            title=title,
            instructions=instructions,
            ingredients=ingredients,
            category=category,
            user_id=current_user.id,
            image_filename=image_filename
        )

        db.session.add(new_recipe)
        db.session.commit()

        flash('Recipe added successfully!', 'success')
        return redirect(url_for('recipes'))
    return render_template('add_recipe.html')


@app.route('/edit-recipe/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_recipe(id):
    recipe = Recipe.query.get_or_404(id)

    if recipe.user_id != current_user.id:
        flash('You do not have permission to edit this recipe.', 'danger')
        return redirect(url_for('recipes'))

    if request.method == 'POST':
        recipe.title = request.form['title']
        recipe.instructions = request.form['instructions']
        recipe.ingredients = request.form['ingredients']
        recipe.category = request.form['category']

        if 'image' in request.files:
            image = request.files['image']
            if image and allowed_file(image.filename):
                image_filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                recipe.image_filename = image_filename

        db.session.commit()
        flash('Recipe updated successfully!', 'success')
        return redirect(url_for('recipes'))

    return render_template('edit_recipe.html', recipe=recipe)


@app.route('/delete-recipe/<int:id>', methods=['POST'])
@login_required
def delete_recipe(id):
    recipe = Recipe.query.get_or_404(id)

    if recipe.user_id != current_user.id:
        flash('You do not have permission to delete this recipe.', 'danger')
        return redirect(url_for('recipes'))

    db.session.delete(recipe)
    db.session.commit()
    flash('Recipe deleted successfully!', 'success')
    return redirect(url_for('recipes'))


@app.route('/meal_plan', methods=['GET', 'POST'])
@login_required
def meal_plan():
    if request.method == 'POST':
        title = request.form['title']
        recipe_ids = request.form.getlist('recipes')
        new_meal_plan = MealPlan(title=title, user_id=current_user.id)
        db.session.add(new_meal_plan)

        for recipe_id in recipe_ids:
            recipe = Recipe.query.get(recipe_id)
            if recipe:
                new_meal_plan.recipes.append(recipe)

        db.session.commit()
        flash('Meal plan created!', 'success')
        return redirect(url_for('meal_plan'))

    recipes = Recipe.query.filter_by(user_id=current_user.id).all()
    meal_plans = MealPlan.query.filter_by(user_id=current_user.id).all()
    return render_template('meal_plan.html', meal_plans=meal_plans, recipes=recipes)


@app.route('/edit-meal-plan/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_meal_plan(id):
    meal_plan = MealPlan.query.get_or_404(id)

    if meal_plan.user_id != current_user.id:
        flash('You do not have permission to edit this meal plan.', 'danger')
        return redirect(url_for('meal_plan'))

    if request.method == 'POST':
        meal_plan.title = request.form['title']
        recipe_ids = request.form.getlist('recipes')
        meal_plan.recipes = []

        for recipe_id in recipe_ids:
            recipe = Recipe.query.get(recipe_id)
            if recipe:
                meal_plan.recipes.append(recipe)

        db.session.commit()
        flash('Meal plan updated!', 'success')
        return redirect(url_for('meal_plan'))

    recipes = Recipe.query.filter_by(user_id=current_user.id).all()
    return render_template('edit_meal_plan.html', meal_plan=meal_plan, recipes=recipes)


@app.route('/delete-meal-plan/<int:id>', methods=['POST'])
@login_required
def delete_meal_plan(id):
    meal_plan = MealPlan.query.get_or_404(id)

    if meal_plan.user_id != current_user.id:
        flash('You do not have permission to delete this meal plan.', 'danger')
        return redirect(url_for('meal_plan'))

    db.session.delete(meal_plan)
    db.session.commit()
    flash('Meal plan deleted successfully!', 'success')
    return redirect(url_for('meal_plan'))


@app.route('/shopping_list')
@login_required
def shopping_list():
    shopping_list_items = ShoppingListItem.query.filter_by(user_id=current_user.id).all()
    return render_template('shopping_list.html', shopping_list_items=shopping_list_items)


@app.route('/add_to_shopping_list', methods=['POST'])
def add_to_shopping_list():
    ingredient_name = request.form.get('ingredient_name')

    if not ingredient_name:
        flash('Ingredient name are required.', 'danger')
        return redirect(url_for('shopping_list'))

    new_item = ShoppingListItem(
        name=ingredient_name,
        user_id=current_user.id
    )
    db.session.add(new_item)
    db.session.commit()
    flash('Ingredient added to shopping list!', 'success')
    return redirect(url_for('shopping_list'))


@app.route('/add_ingredient', methods=['GET', 'POST'])
@login_required
def add_ingredient():
    if request.method == 'POST':
        name = request.form['name']

        new_item = ShoppingListItem(name=name, user_id=current_user.id)

        db.session.add(new_item)
        db.session.commit()

        flash('Ingredient added to shopping list!', 'success')
        return redirect(url_for('shopping_list'))

    return render_template('add_ingredient.html')


@app.route('/delete_ingredient/<int:id>', methods=['POST'])
@login_required
def delete_ingredient(id):
    ingredient = ShoppingListItem.query.get_or_404(id)

    if ingredient.user_id != current_user.id:
        flash('You do not have permission to delete this ingredient.', 'danger')
        return redirect(url_for('shopping_list'))

    db.session.delete(ingredient)
    db.session.commit()
    flash('Ingredient removed from shopping list!', 'success')
    return redirect(url_for('shopping_list'))


@app.route('/export_recipe_pdf/<int:id>')
@login_required
def export_recipe_pdf(id):
    recipe = Recipe.query.get_or_404(id)

    if recipe.user_id != current_user.id:
        flash('You do not have permission to export this recipe.', 'danger')
        return redirect(url_for('recipes'))

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    text = p.beginText(40, 800)

    text.setFont("Helvetica", 12)
    text.textLine(f"Recipe: {recipe.title}")
    text.textLine("")
    text.textLine("Ingredients:")
    text.textLine(recipe.ingredients)
    text.textLine("")
    text.textLine("Instructions:")
    text.textLine(recipe.instructions)

    p.drawText(text)
    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{recipe.title}.pdf",
        mimetype='application/pdf'
    )


@app.route('/export_recipe_txt/<int:id>')
@login_required
def export_recipe_txt(id):
    recipe = Recipe.query.get_or_404(id)

    if recipe.user_id != current_user.id:
        flash('You do not have permission to export this recipe.', 'danger')
        return redirect(url_for('recipes'))

    text_content = f"Recipe: {recipe.title}\n\n"
    text_content += f"Ingredients:\n{recipe.ingredients}\n\n"
    text_content += f"Instructions:\n{recipe.instructions}"

    return Response(
        text_content,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment;filename={recipe.title}.txt"}
    )


if __name__ == '__main__':
    app.run(debug=True)

