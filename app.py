import json
import os
import requests
from flask import Flask, render_template_string, request, redirect, url_for, flash

###############################################################################
# CONFIG
###############################################################################
API_KEY = "09915cdf743143408c15fd7e428f6939"  # <--- Put your Spoonacular API key here
LOCAL_RECIPES_FILE = "local_recipes.json"

app = Flask(__name__)
app.secret_key = "some-secret-key"

###############################################################################
# 1) HELPER FUNCTIONS
###############################################################################

def load_local_recipes():
    """Load local recipes for Jude & Freya from a JSON file."""
    if os.path.exists(LOCAL_RECIPES_FILE):
        with open(LOCAL_RECIPES_FILE, "r") as f:
            return json.load(f)
    else:
        data = {
            "mine": [
                {
                    "name": "Grilled Chicken Salad",
                    "ingredients": ["chicken breast", "lettuce", "tomato", "cucumber"],
                    "calories": 350,
                    "protein": 40,
                    "source": "Jude",
                    "instructions": "Grill chicken, toss with lettuce, tomato, cucumber."
                }
            ],
            "girlfriend": [
                {
                    "name": "Veggie Stir-Fry",
                    "ingredients": ["tofu", "broccoli", "soy sauce"],
                    "calories": 250,
                    "protein": 10,
                    "source": "Freya",
                    "instructions": "Stir-fry tofu and broccoli with soy sauce."
                }
            ]
        }
        save_local_recipes(data)
        return data

def save_local_recipes(data):
    """Save local recipes back to the JSON file."""
    with open(LOCAL_RECIPES_FILE, "w") as f:
        json.dump(data, f, indent=4)

def complex_search(filters, number=5):
    """
    Use Spoonacular's complexSearch to get recipes.
    We'll parse minCalories/maxCalories from filters, plus excludeWords, diets, cuisines, etc.
    """
    url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "apiKey": API_KEY,
        "number": number,
        "addRecipeInformation": "true",
        "fillIngredients": "true",
        "addRecipeNutrition": "true"
    }

    # parse min/max calories
    if filters.get("calories_from"):
        params["minCalories"] = filters["calories_from"]
    if filters.get("calories_to"):
        params["maxCalories"] = filters["calories_to"]
    if filters.get("max_ingredients"):
        params["maxIngredients"] = filters["max_ingredients"]
    if filters.get("exclude_words"):
        params["excludeIngredients"] = filters["exclude_words"]
    if filters.get("search_query"):
        params["query"] = filters["search_query"]

    # diets (multiple checkboxes possible, but Spoonacular typically only supports one 'diet' param)
    diets = filters.get("diets", [])
    # We'll just pick the first if multiple
    if diets:
        # e.g. "low fat" => "lowfat" or "vegan" => "vegan"
        # We do minimal logic here; you might want a map
        first_diet = diets[0].lower().replace(" ", "")
        params["diet"] = first_diet

    # cuisine => same approach
    cuisines = filters.get("cuisines", [])
    if cuisines:
        first_cuisine = cuisines[0].lower().replace(" ", "")
        params["cuisine"] = first_cuisine

    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    results = []
    for item in data.get("results", []):
        ex_ings = item.get("extendedIngredients", [])
        nutrients = item.get("nutrition", {}).get("nutrients", [])
        results.append({
            "id": item.get("id"),
            "name": item.get("title", "Unnamed"),
            "source": "API",
            "instructions": "",
            "extendedIngredients": ex_ings,
            "nutrients": nutrients
        })
    return results

def get_analyzed_instructions(recipe_id):
    """Fetch step-by-step instructions from /recipes/{id}/analyzedInstructions."""
    if not recipe_id:
        return ""
    url = f"https://api.spoonacular.com/recipes/{recipe_id}/analyzedInstructions"
    params = {"apiKey": API_KEY}
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    except:
        return ""
    steps = []
    for block in data:
        for s in block.get("steps", []):
            num = s.get("number", "")
            text = s.get("step", "")
            if text.strip():
                steps.append(f"Step {num}: {text}")
    return "\n".join(steps)

###############################################################################
# 2) HTML TEMPLATES (in memory for demonstration)
###############################################################################

base_html = r"""
<!DOCTYPE html>
<html>
<head>
  <title>Flask Recipe Planner</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
  <style>
    .freya-section {
      background-color: #ffc0cb; /* baby pink for Freya's section */
      padding: 10px;
      border-radius: 5px;
    }
    .jude-section {
      background-color: #f0f0f0;
      padding: 10px;
      border-radius: 5px;
    }
    .plus-button-jude {
      background-color: yellow;
      border: none;
      font-weight: bold;
      margin-right: 5px;
    }
    .plus-button-freya {
      background-color: pink;
      border: none;
      font-weight: bold;
    }
  </style>
</head>
<body class="bg-light">

<nav class="navbar navbar-expand-lg navbar-dark bg-primary">
  <div class="container-fluid">
    <a class="navbar-brand" href="{{ url_for('home') }}">Recipe Planner</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarsExample" aria-controls="navbarsExample" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navbarsExample">
      <ul class="navbar-nav me-auto mb-2 mb-lg-0">
        <li class="nav-item"><a class="nav-link" href="{{ url_for('home') }}">Home</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('manage') }}">Manage</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('weekly') }}">Weekly</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('advanced') }}">Advanced</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('desserts') }}">Desserts</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('recipe_search') }}">Search</a></li>
      </ul>
    </div>
  </div>
</nav>

<div class="container my-4">
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <div class="alert alert-info">
        {% for msg in messages %}
          <p>{{ msg }}</p>
        {% endfor %}
      </div>
    {% endif %}
  {% endwith %}
  
  {% block content %}{% endblock %}
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

home_html = r"""
{% extends "base.html" %}
{% block content %}
<div class="bg-white p-4 rounded">
  <h1>Welcome Jude & Freya!</h1>
  <p class="lead">Jude's Recipes: {{ mine_count }}<br>Freya's Recipes: {{ gf_count }}</p>
</div>
{% endblock %}
"""

manage_html = r"""
{% extends "base.html" %}
{% block content %}
<h1>Manage Recipes</h1>
<div class="row">
  <div class="col-md-6 jude-section mb-3">
    <h2>Jude's Recipes</h2>
    <ul class="list-group">
      {% for r in local_data.mine %}
      <li class="list-group-item">
        {{ r.name }} 
        ({{ r.calories or 'N/A' }} cal, {{ r.protein or 'N/A' }} g protein)
        <br><small>Ingredients: {{ r.ingredients|join(', ') }}</small>
        <br><small>Instructions: {{ r.instructions }}</small>
      </li>
      {% endfor %}
    </ul>
    <hr>
    <h3>Add New Recipe (Jude)</h3>
    <form method="POST" action="{{ url_for('add_local_recipe') }}">
      <input type="hidden" name="category" value="mine">
      <div class="mb-2">
        <label>Recipe Name:</label>
        <input type="text" name="name" class="form-control">
      </div>
      <div class="mb-2">
        <label>Ingredients (comma-separated):</label>
        <input type="text" name="ingredients" class="form-control">
      </div>
      <div class="mb-2">
        <label>Calories (optional):</label>
        <input type="text" name="calories" class="form-control">
      </div>
      <div class="mb-2">
        <label>Protein (g, optional):</label>
        <input type="text" name="protein" class="form-control">
      </div>
      <div class="mb-2">
        <label>Instructions (optional):</label>
        <textarea name="instructions" class="form-control"></textarea>
      </div>
      <button class="btn btn-sm btn-primary">Add Recipe</button>
    </form>
  </div>
  
  <div class="col-md-6 freya-section mb-3">
    <h2>Freya's Recipes</h2>
    <ul class="list-group">
      {% for r in local_data.girlfriend %}
      <li class="list-group-item">
        {{ r.name }}
        ({{ r.calories or 'N/A' }} cal, {{ r.protein or 'N/A' }} g protein)
        <br><small>Ingredients: {{ r.ingredients|join(', ') }}</small>
        <br><small>Instructions: {{ r.instructions }}</small>
      </li>
      {% endfor %}
    </ul>
    <hr>
    <h3>Add New Recipe (Freya)</h3>
    <form method="POST" action="{{ url_for('add_local_recipe') }}">
      <input type="hidden" name="category" value="girlfriend">
      <div class="mb-2">
        <label>Recipe Name:</label>
        <input type="text" name="name" class="form-control">
      </div>
      <div class="mb-2">
        <label>Ingredients (comma-separated):</label>
        <input type="text" name="ingredients" class="form-control">
      </div>
      <div class="mb-2">
        <label>Calories (optional):</label>
        <input type="text" name="calories" class="form-control">
      </div>
      <div class="mb-2">
        <label>Protein (g, optional):</label>
        <input type="text" name="protein" class="form-control">
      </div>
      <div class="mb-2">
        <label>Instructions (optional):</label>
        <textarea name="instructions" class="form-control"></textarea>
      </div>
      <button class="btn btn-sm btn-primary">Add Recipe</button>
    </form>
  </div>
</div>
{% endblock %}
"""

weekly_html = r"""
{% extends "base.html" %}
{% block content %}
<h1>Weekly Dinner</h1>
<form method="POST" class="bg-white p-4 rounded">
  <div class="mb-3">
    <label>Number of Jude's Recipes:</label>
    <input type="text" name="my_count" class="form-control" value="1">
  </div>
  <div class="mb-3">
    <label>Number of Freya's Recipes:</label>
    <input type="text" name="gf_count" class="form-control" value="1">
  </div>
  <div class="mb-3">
    <label>Number of Spoonacular Recipes:</label>
    <input type="text" name="api_count" class="form-control" value="1">
  </div>

  <!-- Example advanced filters: min/max cal -->
  <div class="mb-3">
    <label>Min Calories (optional):</label>
    <input type="text" name="min_cal" class="form-control">
  </div>
  <div class="mb-3">
    <label>Max Calories (optional):</label>
    <input type="text" name="max_cal" class="form-control">
  </div>

  <!-- Checkboxes for diets -->
  <div class="mb-3">
    <label>Diets (pick any):</label><br>
    <input type="checkbox" name="diets" value="low fat"> Low Fat<br>
    <input type="checkbox" name="diets" value="high protein"> High Protein<br>
    <input type="checkbox" name="diets" value="vegan"> Vegan<br>
    <input type="checkbox" name="diets" value="vegetarian"> Vegetarian<br>
    <input type="checkbox" name="diets" value="paleo"> Paleo<br>
    <input type="checkbox" name="diets" value="gluten free"> Gluten Free<br>
  </div>

  <!-- Checkboxes for cuisine -->
  <div class="mb-3">
    <label>Cuisine (pick any):</label><br>
    <input type="checkbox" name="cuisines" value="italian"> Italian<br>
    <input type="checkbox" name="cuisines" value="indian"> Indian<br>
    <input type="checkbox" name="cuisines" value="mexican"> Mexican<br>
    <input type="checkbox" name="cuisines" value="chinese"> Chinese<br>
    <input type="checkbox" name="cuisines" value="american"> American<br>
  </div>

  <button type="submit" class="btn btn-primary">Generate Weekly Plan</button>
</form>
{% endblock %}
"""

weekly_plan_html = r"""
{% extends "base.html" %}
{% block content %}
<h1>Weekly Plan</h1>
<div class="row">
  <div class="col-md-8">
    <h2>Recipes</h2>
    {% for rec in recipes %}
    <div class="card mb-3">
      <div class="card-body">
        <h5 class="card-title">{{ rec.name }} <span class="badge bg-secondary">{{ rec.source }}</span></h5>
        <button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#inst-{{ loop.index }}">Instructions</button>
        <button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#nutr-{{ loop.index }}">Nutrients</button>
        <button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#ing-{{ loop.index }}">Ingredients</button>

        <div class="mt-2 collapse" id="inst-{{ loop.index }}">
          <pre class="bg-light p-2">{{ rec.instructions }}</pre>
        </div>
        <div class="mt-2 collapse" id="nutr-{{ loop.index }}">
          <ul>
            {% for n in rec.nutrients %}
            <li>{{ n.name }}: {{ n.amount }}{{ n.unit }}</li>
            {% endfor %}
          </ul>
        </div>
        <div class="mt-2 collapse" id="ing-{{ loop.index }}">
          <ul>
            {% for ing in rec.extendedIngredients %}
            <li>
              {{ ing.amount }} {{ ing.unit }} {{ ing.name }}
            </li>
            {% endfor %}
          </ul>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  <div class="col-md-4">
    <h2>Shopping List</h2>
    <ul class="list-group">
      {% for item in shopping %}
      <li class="list-group-item">{{ item }}</li>
      {% endfor %}
    </ul>
  </div>
</div>
{% endblock %}
"""

advanced_html = r"""
{% extends "base.html" %}
{% block content %}
<h1>Advanced Filters</h1>
<p>(Placeholder or form for advanced filters, e.g. diet, allergies, etc.)</p>
{% endblock %}
"""

desserts_html = r"""
{% extends "base.html" %}
{% block content %}
<h1>Dessert Recipes</h1>
<div class="row row-cols-1 row-cols-md-2 g-4">
{% for d in desserts %}
  <div class="col">
    <div class="card h-100">
      <div class="card-body">
        <h5 class="card-title">{{ d.name }}</h5>
        <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#inst-{{ loop.index }}">Instructions</button>
        <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#nutr-{{ loop.index }}">Nutrients</button>
        <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#ing-{{ loop.index }}">Ingredients</button>

        <div id="inst-{{ loop.index }}" class="collapse mt-2">
          <pre class="bg-light p-2">{{ d.instructions }}</pre>
        </div>
        <div id="nutr-{{ loop.index }}" class="collapse mt-2">
          <ul>
            {% for n in d.nutrients %}
            <li>{{ n.name }}: {{ n.amount }}{{ n.unit }}</li>
            {% endfor %}
          </ul>
        </div>
        <div class="mt-2 collapse" id="ing-{{ loop.index }}">
          <ul>
            {% for ing in d.extendedIngredients %}
            <li>{{ ing.amount }} {{ ing.unit }} {{ ing.name }}</li>
            {% endfor %}
          </ul>
        </div>
        
        <button class="plus-button-jude btn btn-sm">+ Jude</button>
        <button class="plus-button-freya btn btn-sm">+ Freya</button>
      </div>
    </div>
  </div>
{% endfor %}
</div>
{% endblock %}
"""

search_form_html = r"""
{% extends "base.html" %}
{% block content %}
<h1>Recipe Search</h1>
<form method="POST" class="bg-white p-3 rounded">
  <div class="mb-2">
    <label>Search Query:</label>
    <input type="text" name="query" class="form-control">
  </div>
  <div class="mb-2">
    <label>Min Calories:</label>
    <input type="text" name="min_cal" class="form-control">
  </div>
  <div class="mb-2">
    <label>Max Calories:</label>
    <input type="text" name="max_cal" class="form-control">
  </div>
  <div class="mb-2">
    <label>Max Ingredients:</label>
    <input type="text" name="max_ing" class="form-control">
  </div>
  <div class="mb-2">
    <label>Exclude Words:</label>
    <input type="text" name="exclude" class="form-control">
  </div>

  <!-- Diet checkboxes -->
  <div class="mb-3">
    <label>Diets (pick any):</label><br>
    <input type="checkbox" name="diets" value="low fat"> Low Fat<br>
    <input type="checkbox" name="diets" value="high protein"> High Protein<br>
    <input type="checkbox" name="diets" value="vegan"> Vegan<br>
    <input type="checkbox" name="diets" value="vegetarian"> Vegetarian<br>
    <input type="checkbox" name="diets" value="paleo"> Paleo<br>
    <input type="checkbox" name="diets" value="gluten free"> Gluten Free<br>
  </div>

  <!-- Cuisine checkboxes -->
  <div class="mb-3">
    <label>Cuisines (pick any):</label><br>
    <input type="checkbox" name="cuisines" value="italian"> Italian<br>
    <input type="checkbox" name="cuisines" value="indian"> Indian<br>
    <input type="checkbox" name="cuisines" value="mexican"> Mexican<br>
    <input type="checkbox" name="cuisines" value="chinese"> Chinese<br>
    <input type="checkbox" name="cuisines" value="american"> American<br>
  </div>

  <button class="btn btn-primary" type="submit">Search</button>
</form>
{% endblock %}
"""

search_results_html = r"""
{% extends "base.html" %}
{% block content %}
<h1>Search Results</h1>
<div class="row row-cols-1 row-cols-md-2 g-4">
{% for rec in recipes %}
  <div class="col">
    <div class="card h-100">
      <div class="card-body">
        <h5 class="card-title">{{ rec.name }}</h5>
        <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#inst-{{ loop.index }}">Instructions</button>
        <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#nutr-{{ loop.index }}">Nutrients</button>
        <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#ing-{{ loop.index }}">Ingredients</button>

        <div id="inst-{{ loop.index }}" class="collapse mt-2">
          <pre class="bg-light p-2">{{ rec.instructions }}</pre>
        </div>
        <div id="nutr-{{ loop.index }}" class="collapse mt-2">
          <ul>
            {% for n in rec.nutrients %}
            <li>{{ n.name }}: {{ n.amount }}{{ n.unit }}</li>
            {% endfor %}
          </ul>
        </div>
        <div class="mt-2 collapse" id="ing-{{ loop.index }}">
          <ul>
            {% for ing in rec.extendedIngredients %}
            <li>{{ ing.amount }} {{ ing.unit }} {{ ing.name }}</li>
            {% endfor %}
          </ul>
        </div>
        
        <!-- Plus Buttons for Jude/Freya -->
        <button class="plus-button-jude btn btn-sm">+ Jude</button>
        <button class="plus-button-freya btn btn-sm">+ Freya</button>
      </div>
    </div>
  </div>
{% endfor %}
</div>
{% endblock %}
"""

###############################################################################
# 3) TEMPLATES DICTIONARY
###############################################################################

TEMPLATE_MAP = {
    "base.html": base_html,
    "home.html": home_html,
    "manage.html": manage_html,
    "weekly.html": weekly_html,
    "weekly_plan.html": weekly_plan_html,
    "advanced.html": advanced_html,
    "desserts.html": desserts_html,
    "search_form.html": search_form_html,
    "search_results.html": search_results_html
}

from flask import render_template_string

@app.template_global()
def render_template(name, **context):
    if name in TEMPLATE_MAP:
        return render_template_string(TEMPLATE_MAP[name], **context)
    return f"Template {name} not found."

###############################################################################
# 4) ROUTES
###############################################################################

@app.route("/")
def home():
    data = load_local_recipes()
    mine_count = len(data.get("mine", []))
    gf_count = len(data.get("girlfriend", []))
    return render_template("home.html", mine_count=mine_count, gf_count=gf_count)

@app.route("/manage", methods=["GET"])
def manage():
    data = load_local_recipes()
    return render_template("manage.html", local_data=data)

@app.route("/add_local_recipe", methods=["POST"])
def add_local_recipe():
    data = load_local_recipes()
    category = request.form.get("category", "mine")
    name = request.form.get("name", "Unnamed")
    ingredients_str = request.form.get("ingredients", "")
    cal_str = request.form.get("calories", "")
    prot_str = request.form.get("protein", "")
    instructions = request.form.get("instructions", "")

    try:
        cal = int(cal_str) if cal_str else None
    except:
        cal = None
    try:
        prot = int(prot_str) if prot_str else None
    except:
        prot = None

    ing_list = [x.strip() for x in ingredients_str.split(",") if x.strip()]

    new_rec = {
        "name": name,
        "ingredients": ing_list,
        "calories": cal,
        "protein": prot,
        "source": "Jude" if category == "mine" else "Freya",
        "instructions": instructions
    }
    data.setdefault(category, []).append(new_rec)
    save_local_recipes(data)
    flash(f"Added '{name}' to {new_rec['source']}'s recipes.")
    return redirect(url_for("manage"))

@app.route("/weekly", methods=["GET", "POST"])
def weekly():
    if request.method == "POST":
        my_count = int(request.form.get("my_count", 1))
        gf_count = int(request.form.get("gf_count", 1))
        api_count = int(request.form.get("api_count", 1))
        min_cal = request.form.get("min_cal", "")
        max_cal = request.form.get("max_cal", "")

        # diets & cuisines from checkboxes
        diets = request.form.getlist("diets")  # multiple checkboxes
        cuisines = request.form.getlist("cuisines")

        spoon_filters = {}
        if min_cal:
            spoon_filters["calories_from"] = min_cal
        if max_cal:
            spoon_filters["calories_to"] = max_cal
        if diets:
            spoon_filters["diets"] = diets
        if cuisines:
            spoon_filters["cuisines"] = cuisines

        data = load_local_recipes()
        mine = data.get("mine", [])[:my_count]
        gf = data.get("girlfriend", [])[:gf_count]

        spoon_recs = complex_search(spoon_filters, number=api_count)
        combined = []

        for r in mine:
            ex_ings = [{"name": i, "amount": 1, "unit": ""} for i in r["ingredients"]]
            combined.append({
                "id": None,
                "name": r["name"],
                "instructions": r.get("instructions", ""),
                "extendedIngredients": ex_ings,
                "source": "Jude",
                "nutrients": []
            })
        for r in gf:
            ex_ings = [{"name": i, "amount": 1, "unit": ""} for i in r["ingredients"]]
            combined.append({
                "id": None,
                "name": r["name"],
                "instructions": r.get("instructions", ""),
                "extendedIngredients": ex_ings,
                "source": "Freya",
                "nutrients": []
            })

        combined.extend(spoon_recs)

        shopping = set()
        for rec in combined:
            rid = rec.get("id")
            if rec["source"] == "API" and rid:
                # fetch instructions
                steps = get_analyzed_instructions(rid)
                rec["instructions"] = steps
            for ing in rec["extendedIngredients"]:
                amt = ing.get("amount", 1)
                unit = ing.get("unit", "")
                name = ing.get("name", "")
                if name:
                    full_str = f"{amt} {unit} {name}".strip()
                    shopping.add(full_str)

        return render_template("weekly_plan.html", recipes=combined, shopping=sorted(shopping))

    return render_template("weekly.html")

@app.route("/advanced", methods=["GET", "POST"])
def advanced():
    if request.method == "POST":
        flash("Advanced filters saved!")
        return redirect(url_for("weekly"))
    return render_template("advanced.html")

@app.route("/desserts")
def desserts():
    spoon_filters = {}
    desserts = complex_search(spoon_filters, number=5)
    # Force dessert logic. If you want strict 'type=dessert', do:
    # desserts = complex_search(spoon_filters, number=5, forced_dessert=True)
    for d in desserts:
        rid = d.get("id")
        if rid:
            steps = get_analyzed_instructions(rid)
            d["instructions"] = steps
    return render_template("desserts.html", desserts=desserts)

@app.route("/search", methods=["GET", "POST"])
def recipe_search():
    if request.method == "POST":
        query = request.form.get("query", "")
        min_cal = request.form.get("min_cal", "")
        max_cal = request.form.get("max_cal", "")
        max_ing = request.form.get("max_ing", "")
        exclude = request.form.get("exclude", "")

        diets = request.form.getlist("diets")
        cuisines = request.form.getlist("cuisines")

        spoon_filters = {}
        if query:
            spoon_filters["search_query"] = query
        if min_cal:
            spoon_filters["calories_from"] = min_cal
        if max_cal:
            spoon_filters["calories_to"] = max_cal
        if max_ing:
            spoon_filters["max_ingredients"] = max_ing
        if exclude:
            spoon_filters["exclude_words"] = exclude
        if diets:
            spoon_filters["diets"] = diets
        if cuisines:
            spoon_filters["cuisines"] = cuisines

        found = complex_search(spoon_filters, number=5)
        for rec in found:
            rid = rec.get("id")
            if rid:
                steps = get_analyzed_instructions(rid)
                rec["instructions"] = steps
        return render_template("search_results.html", recipes=found)

    return render_template("search_form.html")

@app.route("/add_api_recipe", methods=["POST"])
def add_api_recipe():
    # parse data from request.form or request.json
    # store in local recipes
    return "OK"

###############################################################################
# 4) RUN
###############################################################################

if __name__ == "__main__":
    app.run(debug=True)
