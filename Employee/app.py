from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import logging

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client['EMPLOYEE']
users_collection = db['users']
tasks_collection = db['tasks']
appraisals_collection = db['appraisals']

# Route: Landing on Register Page
@app.route("/")
def home():
    return render_template("index.html")


# Route: Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")  

        hashed_password = generate_password_hash(password)
        users_collection.insert_one({
            "name": name,
            "email": email,
            "password": hashed_password,
            "role": role
        })

        session["email"] = email
        session["role"] = role

        if role == "admin":
            return redirect(url_for("admin_dashboard"))
        else:
            return redirect(url_for("employee_dashboard"))

    return render_template("register.html")

# Route: Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        user = users_collection.find_one({"email": email})
        
        if user and check_password_hash(user["password"], password):
            session["email"] = email
            session["role"] = user["role"]
            session["employee_id"] = str(user["_id"])  # Store employee ID in session

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("employee_dashboard"))
        else:
            return "Invalid credentials, please try again."
    
    return render_template("login.html")


# ✅ Route: Admin Dashboard
@app.route("/admin_dashboard")
def admin_dashboard():
    if "role" in session and session["role"] == "admin":
        employees = list(users_collection.find({"role": "employee"}))
        tasks = list(tasks_collection.find())
        reports = list(db.reports.find())  # Fetch all reports

        return render_template("admin_dashboard.html", employees=employees, tasks=tasks, reports=reports)

    return redirect(url_for("login"))


# ✅ Route: Add Employee to MongoDB
@app.route("/add_employee", methods=["POST"])
def add_employee():
    if "role" in session and session["role"] == "admin":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        hashed_password = generate_password_hash(password)
        users_collection.insert_one({
            "name": name,
            "email": email,
            "password": hashed_password,
            "role": "employee"
        })

        return redirect(url_for("admin_dashboard"))

    return redirect(url_for("login"))

# ✅ Route: Assign Task to Employee
@app.route("/assign_task", methods=["POST"])
def assign_task():
    if "role" in session and session["role"] == "admin":
        employee_email = request.form.get("employee_email")
        task_category = request.form.get("task_category")
        task_priority = request.form.get("task_priority")
        task_description = request.form.get("task_description")

        tasks_collection.insert_one({
            "employee_email": employee_email,
            "task_category": task_category,
            "task_priority": task_priority,
            "task_description": task_description,
            "evaluation": ""
        })

        return redirect(url_for("admin_dashboard"))

    return redirect(url_for("login"))

# ✅ Route: Update Employee Appraisal
@app.route("/update_appraisal", methods=["POST"])
def update_appraisal():
    if "role" in session and session["role"] == "admin":
        employee_email = request.form.get("employee_email")
        appraisal_rating = request.form.get("appraisal_rating")
        appraisal_comments = request.form.get("appraisal_comments")

        logging.info(f"Session Role: {session['role']}, Employee Email: {employee_email}")
        logging.info(f"Appraisal Rating: {appraisal_rating}, Appraisal Comments: {appraisal_comments}")

        if not employee_email or not appraisal_rating:
            flash("Failed to update appraisal. Please fill all required fields.", "danger")
            return redirect(url_for("admin_dashboard"))

        try:
            result = appraisals_collection.insert_one({
                "employee_email": employee_email,
                "appraisal_rating": appraisal_rating,
                "appraisal_comments": appraisal_comments
            })
            logging.info(f"Appraisal inserted with ID: {result.inserted_id}")
            flash("Appraisal updated successfully!", "success")
        except Exception as e:
            logging.error(f"Error inserting appraisal: {e}")
            flash("An error occurred while updating the appraisal. Please try again.", "danger")

        return redirect(url_for("admin_dashboard"))

    flash("Unauthorized access. Please log in as an admin.", "danger")
    return redirect(url_for("login"))

# ✅ Route: Evaluate Task
@app.route("/evaluate_task", methods=["POST"])
def evaluate_task():
    if "role" in session and session["role"] == "admin":
        task_id = request.form.get("task_id")
        evaluation = request.form.get("evaluation")

        tasks_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"evaluation": evaluation}}
        )

        return redirect(url_for("admin_dashboard"))

    return redirect(url_for("login"))


# ✅ Route: Employee Dashboard (Now Fetches Appraisal Scores)
@app.route("/employee_dashboard")
def employee_dashboard():
    if "email" not in session:
        return redirect(url_for("login"))

    employee_email = session["email"]
    tasks = list(tasks_collection.find({"employee_email": employee_email}))
    appraisals = list(appraisals_collection.find({"employee_email": employee_email}))
    reports = list(db.reports.find({"employee_email": employee_email}))  # Fetch reports

    return render_template(
        "employee_dashboard.html",
        tasks=tasks,
        appraisals=appraisals,
        reports=reports
    )


@app.route("/submit_task", methods=["POST"])
def submit_task():
    if "employee_id" not in session:
        return redirect("/login")

    employee_id = session["employee_id"]
    task_description = request.form.get("task_description")

    task_data = {
        "employee_id": employee_id,
        "task_description": task_description,
        "status": "Pending"
    }

    db.tasks.insert_one(task_data)
    return redirect("/employee_dashboard")


@app.route("/logout")
def logout():
    session.clear()  # Clear session data
    return redirect("/login")
