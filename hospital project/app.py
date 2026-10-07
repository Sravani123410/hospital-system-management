import os
import io
from datetime import datetime, timedelta, date
from functools import wraps
from io import BytesIO
from urllib.parse import parse_qs

import jwt
import pandas as pd
import numpy as np
from dotenv import load_dotenv

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
    session,
    send_file,
    make_response
)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "hospital-secret"
)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:password@localhost:3306/hospital_db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "hospital-jwt-secret"
)

db = SQLAlchemy(app)


# =========================================================
# METHOD OVERRIDE
# =========================================================

class MethodOverrideMiddleware:

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):

        if environ.get("REQUEST_METHOD") == "POST":

            content_type = environ.get(
                "CONTENT_TYPE",
                ""
            )

            if "application/x-www-form-urlencoded" in content_type:

                try:

                    length = int(
                        environ.get(
                            "CONTENT_LENGTH",
                            "0"
                        )
                    )

                    body = environ[
                        "wsgi.input"
                    ].read(length)

                    form = parse_qs(
                        body.decode("utf-8")
                    )

                    method = form.get(
                        "_method",
                        [None]
                    )[0]

                    if method and method.upper() in [
                        "PUT",
                        "PATCH",
                        "DELETE"
                    ]:

                        environ[
                            "REQUEST_METHOD"
                        ] = method.upper()

                    environ[
                        "wsgi.input"
                    ] = BytesIO(body)

                    environ[
                        "CONTENT_LENGTH"
                    ] = str(len(body))

                except Exception:
                    pass

        return self.app(
            environ,
            start_response
        )


app.wsgi_app = MethodOverrideMiddleware(
    app.wsgi_app
)


# =========================================================
# DATABASE MODELS
# =========================================================

class Patient(db.Model):

    __tablename__ = "patients"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    age = db.Column(
        db.Integer,
        nullable=False
    )

    gender = db.Column(
        db.String(20),
        nullable=False
    )

    contact = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    appointments = db.relationship(
        "Appointment",
        backref="patient",
        cascade="all, delete-orphan"
    )


class Doctor(db.Model):

    __tablename__ = "doctors"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    specialization = db.Column(
        db.String(100),
        nullable=False
    )

    appointments = db.relationship(
        "Appointment",
        backref="doctor",
        cascade="all, delete-orphan"
    )


class User(db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="doctor"
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id"),
        nullable=True
    )

    doctor = db.relationship(
        "Doctor",
        backref=db.backref(
            "user_account",
            uselist=False
        )
    )


class Appointment(db.Model):

    __tablename__ = "appointments"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("patients.id"),
        nullable=False
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id"),
        nullable=False
    )

    date = db.Column(
        db.Date,
        nullable=False
    )

    diagnosis = db.Column(
        db.String(255),
        nullable=False
    )

    status = db.Column(
        db.String(50),
        nullable=False
    )

    recovery_date = db.Column(
        db.Date,
        nullable=True
    )


# =========================================================
# CREATE TABLES
# =========================================================

with app.app_context():

    db.create_all()


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def patient_dict(patient):

    return {
        "id": patient.id,
        "name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "contact": patient.contact
    }


def doctor_dict(doctor):

    return {
        "id": doctor.id,
        "name": doctor.name,
        "specialization": doctor.specialization
    }


def normalize_date(value):

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return parse_date(value)


def parse_date(value):

    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:

        return datetime.strptime(
            str(value),
            "%Y-%m-%d"
        ).date()

    except (
        ValueError,
        TypeError
    ):

        return None


def calculate_recovery_days(appointment):

    if not appointment.date:
        return None

    if not appointment.recovery_date:
        return None

    try:

        appointment_date = normalize_date(
            appointment.date
        )

        recovery_date = normalize_date(
            appointment.recovery_date
        )

        if appointment_date is None:
            return None

        if recovery_date is None:
            return None

        return (
            recovery_date - appointment_date
        ).days

    except (
        TypeError,
        ValueError
    ):

        return None


def appointment_dict(appointment):

    recovery_days = calculate_recovery_days(
        appointment
    )

    appointment_date = normalize_date(
        appointment.date
    )

    recovery_date = normalize_date(
        appointment.recovery_date
    )

    return {

        "id": appointment.id,

        "patient_id": appointment.patient_id,

        "patient_name": (
            appointment.patient.name
            if appointment.patient
            else None
        ),

        "doctor_id": appointment.doctor_id,

        "doctor_name": (
            appointment.doctor.name
            if appointment.doctor
            else None
        ),

        "date": (
            appointment_date.isoformat()
            if appointment_date
            else None
        ),

        "diagnosis": appointment.diagnosis,

        "status": appointment.status,

        "recovery_date": (
            recovery_date.isoformat()
            if recovery_date
            else None
        ),

        "recovery_days": recovery_days
    }


def get_int(value):

    try:

        return int(value)

    except (
        ValueError,
        TypeError
    ):

        return None


def json_data():

    return request.get_json(
        silent=True
    ) or {}


# =========================================================
# WEB AUTHENTICATION
# =========================================================

def current_web_user():

    user_id = session.get(
        "user_id"
    )

    if not user_id:
        return None

    return db.session.get(
        User,
        user_id
    )


def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not current_web_user():

            return redirect(
                url_for("login")
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


def admin_required_web(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        user = current_web_user()

        if not user:

            return redirect(
                url_for("login")
            )

        if user.role != "admin":

            flash(
                "Admin access required",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# JWT AUTHENTICATION
# =========================================================

def create_token(user):

    payload = {

        "user_id": user.id,

        "role": user.role,

        "doctor_id": user.doctor_id,

        "exp": (
            datetime.utcnow()
            + timedelta(hours=2)
        )
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm="HS256"
    )


def jwt_user():

    authorization = request.headers.get(
        "Authorization",
        ""
    )

    if not authorization.startswith(
        "Bearer "
    ):

        return None

    token = authorization.split(
        " ",
        1
    )[1].strip()

    if not token:
        return None

    try:

        data = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=["HS256"]
        )

        user_id = data.get(
            "user_id"
        )

        if not user_id:
            return None

        return db.session.get(
            User,
            user_id
        )

    except (
        jwt.ExpiredSignatureError,
        jwt.InvalidTokenError,
        KeyError,
        TypeError
    ):

        return None


def jwt_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        user = jwt_user()

        if not user:

            return jsonify({
                "error": "Authentication required"
            }), 401

        return function(
            *args,
            **kwargs
        )

    return wrapper


def admin_required_api(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        user = jwt_user()

        if not user:

            return jsonify({
                "error": "Authentication required"
            }), 401

        if user.role != "admin":

            return jsonify({
                "error": "Admin access required"
            }), 403

        return function(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if current_web_user():

        return redirect(
            url_for("dashboard")
        )

    return redirect(
        url_for("login")
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    user = current_web_user()

    if user.role == "doctor":

        appointment_count = (
            Appointment.query
            .filter_by(
                doctor_id=user.doctor_id
            )
            .count()
        )

    else:

        appointment_count = (
            Appointment.query.count()
        )

    if user.role == "doctor":

        recovered_count = (
            Appointment.query
            .filter_by(
                doctor_id=user.doctor_id,
                status="Recovered"
            )
            .count()
        )

    else:

        recovered_count = (
            Appointment.query
            .filter_by(
                status="Recovered"
            )
            .count()
        )

    return render_template(
        "dashboard.html",
        patient_count=Patient.query.count(),
        doctor_count=Doctor.query.count(),
        appointment_count=appointment_count,
        recovered_count=recovered_count,
        current_user=user
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "GET":

        return render_template(
            "login.html"
        )

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    if not username or not password:

        flash(
            "Username and password are required",
            "danger"
        )

        return redirect(
            url_for("login")
        )

    user = User.query.filter_by(
        username=username
    ).first()

    if (
        not user
        or not check_password_hash(
            user.password_hash,
            password
        )
    ):

        flash(
            "Invalid username or password",
            "danger"
        )

        return redirect(
            url_for("login")
        )

    session["user_id"] = user.id
    session["role"] = user.role
    session["token"] = create_token(user)

    flash(
        "Login successful",
        "success"
    )

    return redirect(
        url_for("dashboard")
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# ADMIN REGISTRATION
# =========================================================

@app.route(
    "/register-admin",
    methods=["GET", "POST"]
)
def register_admin():

    if request.method == "GET":

        return render_template(
            "register.html"
        )

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    if not username or not password:

        flash(
            "Username and password are required",
            "danger"
        )

        return redirect(
            url_for("register_admin")
        )

    existing = User.query.filter_by(
        username=username
    ).first()

    if existing:

        flash(
            "Username already exists",
            "danger"
        )

        return redirect(
            url_for("register_admin")
        )

    user = User(

        username=username,

        password_hash=generate_password_hash(
            password
        ),

        role="admin"
    )

    db.session.add(user)
    db.session.commit()

    flash(
        "Admin registered successfully. Please login.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# =========================================================
# PATIENT WEB
# =========================================================

@app.route("/patients")
@admin_required_web
def patients():

    return render_template(
        "patients/list.html",
        patients=Patient.query.all()
    )


@app.route("/patients/new")
@admin_required_web
def new_patient():

    return render_template(
        "patients/form.html",
        patient=None
    )


@app.route(
    "/patients",
    methods=["POST"]
)
@admin_required_web
def create_patient():

    name = request.form.get(
        "name",
        ""
    ).strip()

    age = get_int(
        request.form.get("age")
    )

    gender = request.form.get(
        "gender",
        ""
    ).strip()

    contact = request.form.get(
        "contact",
        ""
    ).strip()

    if not name or not gender or not contact:

        flash(
            "All patient fields are required",
            "danger"
        )

        return redirect(
            url_for("new_patient")
        )

    if age is None or age < 0:

        flash(
            "Age must be a valid non-negative number",
            "danger"
        )

        return redirect(
            url_for("new_patient")
        )

    existing = Patient.query.filter_by(
        contact=contact
    ).first()

    if existing:

        flash(
            "Contact already exists",
            "danger"
        )

        return redirect(
            url_for("new_patient")
        )

    patient = Patient(

        name=name,

        age=age,

        gender=gender,

        contact=contact
    )

    db.session.add(patient)
    db.session.commit()

    flash(
        "Patient added successfully",
        "success"
    )

    return redirect(
        url_for("patients")
    )


@app.route("/patients/<int:id>")
@admin_required_web
def patient_details(id):

    patient = db.get_or_404(
        Patient,
        id
    )

    return render_template(
        "patients/detail.html",
        patient=patient
    )


@app.route("/patients/<int:id>/edit")
@admin_required_web
def edit_patient(id):

    patient = db.get_or_404(
        Patient,
        id
    )

    return render_template(
        "patients/form.html",
        patient=patient
    )


@app.route(
    "/patients/<int:id>",
    methods=["PUT", "PATCH"]
)
@login_required
def update_patient(id):

    patient = db.get_or_404(
        Patient,
        id
    )

    data = (
        request.get_json(silent=True)
        if request.is_json
        else request.form
    )

    user = current_web_user()

    if user.role != "admin":

        if request.is_json:

            return jsonify({
                "error": "Admin access required"
            }), 403

        flash(
            "Admin access required",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    if "name" in data:

        name = str(
            data["name"]
        ).strip()

        if name:
            patient.name = name

    if "age" in data:

        age = get_int(
            data["age"]
        )

        if age is None or age < 0:

            if request.is_json:

                return jsonify({
                    "error": "Invalid age"
                }), 400

            flash(
                "Invalid age",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_patient",
                    id=id
                )
            )

        patient.age = age

    if "gender" in data:

        gender = str(
            data["gender"]
        ).strip()

        if gender:
            patient.gender = gender

    if "contact" in data:

        contact = str(
            data["contact"]
        ).strip()

        existing = Patient.query.filter(
            Patient.contact == contact,
            Patient.id != id
        ).first()

        if existing:

            if request.is_json:

                return jsonify({
                    "error": "Contact already exists"
                }), 409

            flash(
                "Contact already exists",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_patient",
                    id=id
                )
            )

        if contact:
            patient.contact = contact

    db.session.commit()

    if request.is_json:

        return jsonify({
            "message": "Patient updated",
            "patient": patient_dict(patient)
        })

    flash(
        "Patient updated successfully",
        "success"
    )

    return redirect(
        url_for(
            "patient_details",
            id=id
        )
    )


@app.route(
    "/patients/<int:id>",
    methods=["DELETE"]
)
@admin_required_web
def delete_patient(id):

    patient = db.get_or_404(
        Patient,
        id
    )

    db.session.delete(patient)
    db.session.commit()

    if request.is_json:

        return jsonify({
            "message": "Patient deleted"
        })

    flash(
        "Patient deleted successfully",
        "success"
    )

    return redirect(
        url_for("patients")
    )


# =========================================================
# DOCTOR WEB
# =========================================================

@app.route("/doctors")
@admin_required_web
def doctors():

    return render_template(
        "doctors/list.html",
        doctors=Doctor.query.all()
    )


@app.route("/doctors/new")
@admin_required_web
def new_doctor():

    return render_template(
        "doctors/form.html",
        doctor=None
    )


@app.route(
    "/doctors",
    methods=["POST"]
)
@admin_required_web
def create_doctor():

    name = request.form.get(
        "name",
        ""
    ).strip()

    specialization = request.form.get(
        "specialization",
        ""
    ).strip()

    if not name or not specialization:

        flash(
            "Name and specialization are required",
            "danger"
        )

        return redirect(
            url_for("new_doctor")
        )

    doctor = Doctor(

        name=name,

        specialization=specialization
    )

    db.session.add(doctor)
    db.session.commit()

    flash(
        "Doctor added successfully",
        "success"
    )

    return redirect(
        url_for("doctors")
    )


@app.route("/doctors/<int:id>")
@admin_required_web
def doctor_details(id):

    doctor = db.get_or_404(
        Doctor,
        id
    )

    return render_template(
        "doctors/detail.html",
        doctor=doctor
    )


@app.route("/doctors/<int:id>/edit")
@admin_required_web
def edit_doctor(id):

    doctor = db.get_or_404(
        Doctor,
        id
    )

    return render_template(
        "doctors/form.html",
        doctor=doctor
    )


@app.route(
    "/doctors/<int:id>",
    methods=["PUT", "PATCH"]
)
@login_required
def update_doctor(id):

    doctor = db.get_or_404(
        Doctor,
        id
    )

    user = current_web_user()

    if user.role != "admin":

        if request.is_json:

            return jsonify({
                "error": "Admin access required"
            }), 403

        flash(
            "Admin access required",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    data = (
        request.get_json(silent=True)
        if request.is_json
        else request.form
    )

    if "name" in data:

        name = str(
            data["name"]
        ).strip()

        if name:
            doctor.name = name

    if "specialization" in data:

        specialization = str(
            data["specialization"]
        ).strip()

        if specialization:
            doctor.specialization = specialization

    db.session.commit()

    if request.is_json:

        return jsonify({
            "message": "Doctor updated",
            "doctor": doctor_dict(doctor)
        })

    flash(
        "Doctor updated successfully",
        "success"
    )

    return redirect(
        url_for(
            "doctor_details",
            id=id
        )
    )


@app.route(
    "/doctors/<int:id>",
    methods=["DELETE"]
)
@admin_required_web
def delete_doctor(id):

    doctor = db.get_or_404(
        Doctor,
        id
    )

    User.query.filter_by(
        doctor_id=id
    ).update({
        "doctor_id": None
    })

    db.session.delete(doctor)
    db.session.commit()

    if request.is_json:

        return jsonify({
            "message": "Doctor deleted"
        })

    flash(
        "Doctor deleted successfully",
        "success"
    )

    return redirect(
        url_for("doctors")
    )


# =========================================================
# APPOINTMENT WEB
# =========================================================

@app.route("/appointments")
@login_required
def appointments():

    user = current_web_user()

    if user.role == "doctor":

        data = (
            Appointment.query
            .filter_by(
                doctor_id=user.doctor_id
            )
            .all()
        )

    else:

        data = Appointment.query.all()

    return render_template(
        "appointments/list.html",
        appointments=data
    )


@app.route("/appointments/new")
@admin_required_web
def new_appointment():

    return render_template(
        "appointments/form.html",
        appointment=None,
        patients=Patient.query.all(),
        doctors=Doctor.query.all()
    )


@app.route(
    "/appointments",
    methods=["POST"]
)
@admin_required_web
def create_appointment():

    patient_id = get_int(
        request.form.get("patient_id")
    )

    doctor_id = get_int(
        request.form.get("doctor_id")
    )

    appointment_date = parse_date(
        request.form.get("date")
    )

    diagnosis = request.form.get(
        "diagnosis",
        ""
    ).strip()

    status = request.form.get(
        "status",
        "Scheduled"
    ).strip()

    recovery_date = parse_date(
        request.form.get("recovery_date")
    )

    patient = (
        db.session.get(
            Patient,
            patient_id
        )
        if patient_id is not None
        else None
    )

    doctor = (
        db.session.get(
            Doctor,
            doctor_id
        )
        if doctor_id is not None
        else None
    )

    if not patient or not doctor:

        flash(
            "Invalid patient or doctor",
            "danger"
        )

        return redirect(
            url_for("new_appointment")
        )

    if not appointment_date:

        flash(
            "Valid appointment date is required",
            "danger"
        )

        return redirect(
            url_for("new_appointment")
        )

    if not diagnosis:

        flash(
            "Diagnosis is required",
            "danger"
        )

        return redirect(
            url_for("new_appointment")
        )

    if (
        recovery_date
        and recovery_date < appointment_date
    ):

        flash(
            "Recovery date cannot be before appointment date",
            "danger"
        )

        return redirect(
            url_for("new_appointment")
        )

    appointment = Appointment(

        patient_id=patient.id,

        doctor_id=doctor.id,

        date=appointment_date,

        diagnosis=diagnosis,

        status=status or "Scheduled",

        recovery_date=recovery_date
    )

    db.session.add(appointment)
    db.session.commit()

    flash(
        "Appointment created successfully",
        "success"
    )

    return redirect(
        url_for("appointments")
    )


@app.route("/appointments/<int:id>")
@login_required
def appointment_details(id):

    appointment = db.get_or_404(
        Appointment,
        id
    )

    user = current_web_user()

    if (
        user.role == "doctor"
        and appointment.doctor_id != user.doctor_id
    ):

        flash(
            "Access denied",
            "danger"
        )

        return redirect(
            url_for("appointments")
        )

    return render_template(
        "appointments/detail.html",
        appointment=appointment
    )


@app.route("/appointments/<int:id>/edit")
@login_required
def edit_appointment(id):

    appointment = db.get_or_404(
        Appointment,
        id
    )

    user = current_web_user()

    if (
        user.role == "doctor"
        and appointment.doctor_id != user.doctor_id
    ):

        flash(
            "Access denied",
            "danger"
        )

        return redirect(
            url_for("appointments")
        )

    return render_template(
        "appointments/form.html",
        appointment=appointment,
        patients=Patient.query.all(),
        doctors=Doctor.query.all()
    )


@app.route(
    "/appointments/<int:id>",
    methods=["PUT", "PATCH"]
)
@login_required
def update_appointment(id):

    appointment = db.get_or_404(
        Appointment,
        id
    )

    user = current_web_user()

    if (
        user.role == "doctor"
        and appointment.doctor_id != user.doctor_id
    ):

        if request.is_json:

            return jsonify({
                "error": "Access denied"
            }), 403

        flash(
            "Access denied",
            "danger"
        )

        return redirect(
            url_for("appointments")
        )

    data = (
        request.get_json(silent=True)
        if request.is_json
        else request.form
    )

    if "date" in data:

        new_date = parse_date(
            data["date"]
        )

        if not new_date:

            if request.is_json:

                return jsonify({
                    "error": "Invalid date"
                }), 400

            flash(
                "Invalid date",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_appointment",
                    id=id
                )
            )

        appointment.date = new_date

    if "diagnosis" in data:

        diagnosis = str(
            data["diagnosis"]
        ).strip()

        if diagnosis:
            appointment.diagnosis = diagnosis

    if "status" in data:

        status = str(
            data["status"]
        ).strip()

        if status:
            appointment.status = status

    if "recovery_date" in data:

        value = data[
            "recovery_date"
        ]

        if value:

            recovery_date = parse_date(
                value
            )

            if not recovery_date:

                if request.is_json:

                    return jsonify({
                        "error": "Invalid recovery date"
                    }), 400

                flash(
                    "Invalid recovery date",
                    "danger"
                )

                return redirect(
                    url_for(
                        "edit_appointment",
                        id=id
                    )
                )

            appointment_date = normalize_date(
                appointment.date
            )

            if (
                appointment_date
                and recovery_date < appointment_date
            ):

                if request.is_json:

                    return jsonify({
                        "error": (
                            "Recovery date cannot be "
                            "before appointment date"
                        )
                    }), 400

                flash(
                    "Recovery date cannot be before appointment date",
                    "danger"
                )

                return redirect(
                    url_for(
                        "edit_appointment",
                        id=id
                    )
                )

            appointment.recovery_date = recovery_date

        else:

            appointment.recovery_date = None

    if user.role == "admin":

        if "patient_id" in data:

            patient_id = get_int(
                data["patient_id"]
            )

            if patient_id is None:

                return jsonify({
                    "error": "Invalid patient ID"
                }), 400

            if not db.session.get(
                Patient,
                patient_id
            ):

                return jsonify({
                    "error": "Patient not found"
                }), 404

            appointment.patient_id = patient_id

        if "doctor_id" in data:

            doctor_id = get_int(
                data["doctor_id"]
            )

            if doctor_id is None:

                return jsonify({
                    "error": "Invalid doctor ID"
                }), 400

            if not db.session.get(
                Doctor,
                doctor_id
            ):

                return jsonify({
                    "error": "Doctor not found"
                }), 404

            appointment.doctor_id = doctor_id

    db.session.commit()

    if request.is_json:

        return jsonify({
            "message": "Appointment updated",
            "appointment": appointment_dict(
                appointment
            )
        })

    flash(
        "Appointment updated successfully",
        "success"
    )

    return redirect(
        url_for(
            "appointment_details",
            id=id
        )
    )


@app.route(
    "/appointments/<int:id>",
    methods=["DELETE"]
)
@admin_required_web
def delete_appointment(id):

    appointment = db.get_or_404(
        Appointment,
        id
    )

    db.session.delete(appointment)
    db.session.commit()

    if request.is_json:

        return jsonify({
            "message": "Appointment deleted"
        })

    flash(
        "Appointment deleted successfully",
        "success"
    )

    return redirect(
        url_for("appointments")
    )


# =========================================================
# API AUTHENTICATION
# =========================================================

@app.route(
    "/api/register",
    methods=["POST"]
)
@app.route(
    "/api/auth/register",
    methods=["POST"]
)
def api_register():

    data = json_data()

    username = str(
        data.get(
            "username",
            ""
        )
    ).strip()

    password = data.get(
        "password",
        ""
    )

    role = str(
        data.get(
            "role",
            "doctor"
        )
    ).lower()

    if not username or not password:

        return jsonify({
            "error": "Username and password required"
        }), 400

    if role not in [
        "admin",
        "doctor"
    ]:

        return jsonify({
            "error": "Role must be admin or doctor"
        }), 400

    if User.query.filter_by(
        username=username
    ).first():

        return jsonify({
            "error": "Username already exists"
        }), 409

    if role == "admin":

        existing_admin = User.query.filter_by(
            role="admin"
        ).first()

        if existing_admin:

            current_user = jwt_user()

            if (
                not current_user
                or current_user.role != "admin"
            ):

                return jsonify({
                    "error": "Admin permission required"
                }), 403

    doctor_id = data.get(
        "doctor_id"
    )

    if role == "doctor":

        if doctor_id is not None:

            doctor_id = get_int(
                doctor_id
            )

            if doctor_id is None:

                return jsonify({
                    "error": "Invalid doctor ID"
                }), 400

            if not db.session.get(
                Doctor,
                doctor_id
            ):

                return jsonify({
                    "error": "Doctor not found"
                }), 404

            if User.query.filter_by(
                doctor_id=doctor_id
            ).first():

                return jsonify({
                    "error": (
                        "Doctor is already associated "
                        "with another user"
                    )
                }), 409

    user = User(

        username=username,

        password_hash=generate_password_hash(
            password
        ),

        role=role,

        doctor_id=(
            doctor_id
            if role == "doctor"
            else None
        )
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({

        "message": "User registered successfully",

        "user": {

            "id": user.id,

            "username": user.username,

            "role": user.role,

            "doctor_id": user.doctor_id
        }

    }), 201


@app.route(
    "/api/login",
    methods=["POST"]
)
@app.route(
    "/api/auth/login",
    methods=["POST"]
)
def api_login():

    data = json_data()

    username = str(
        data.get(
            "username",
            ""
        )
    ).strip()

    password = data.get(
        "password",
        ""
    )

    if not username or not password:

        return jsonify({
            "error": "Username and password required"
        }), 400

    user = User.query.filter_by(
        username=username
    ).first()

    if (
        not user
        or not check_password_hash(
            user.password_hash,
            password
        )
    ):

        return jsonify({
            "error": "Invalid username or password"
        }), 401

    token = create_token(user)

    return jsonify({

        "message": "Login successful",

        "token": token,

        "user": {

            "id": user.id,

            "username": user.username,

            "role": user.role,

            "doctor_id": user.doctor_id
        }

    }), 200


# =========================================================
# API PATIENTS
# =========================================================

@app.route(
    "/api/patients",
    methods=["GET"]
)
@jwt_required
def api_get_patients():

    patients_list = Patient.query.all()

    return jsonify([
        patient_dict(p)
        for p in patients_list
    ]), 200


@app.route(
    "/api/patients/<int:id>",
    methods=["GET"]
)
@jwt_required
def api_get_patient(id):

    patient = db.get_or_404(
        Patient,
        id
    )

    return jsonify(
        patient_dict(patient)
    ), 200


@app.route(
    "/api/patients",
    methods=["POST"]
)
@admin_required_api
def api_create_patient():

    data = json_data()

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    age = get_int(
        data.get("age")
    )

    gender = str(
        data.get(
            "gender",
            ""
        )
    ).strip()

    contact = str(
        data.get(
            "contact",
            ""
        )
    ).strip()

    if not name or not gender or not contact:

        return jsonify({
            "error": (
                "Name, gender, and contact are required"
            )
        }), 400

    if age is None or age < 0:

        return jsonify({
            "error": (
                "Age must be a non-negative integer"
            )
        }), 400

    if Patient.query.filter_by(
        contact=contact
    ).first():

        return jsonify({
            "error": "Contact already exists"
        }), 409

    patient = Patient(

        name=name,

        age=age,

        gender=gender,

        contact=contact
    )

    db.session.add(patient)
    db.session.commit()

    return jsonify({

        "message": "Patient created successfully",

        "patient": patient_dict(patient)

    }), 201


@app.route(
    "/api/patients/<int:id>",
    methods=["PUT", "PATCH"]
)
@admin_required_api
def api_update_patient(id):

    patient = db.get_or_404(
        Patient,
        id
    )

    data = json_data()

    if not data:

        return jsonify({
            "error": "JSON body required"
        }), 400

    if "name" in data:

        name = str(
            data["name"]
        ).strip()

        if not name:

            return jsonify({
                "error": "Name cannot be empty"
            }), 400

        patient.name = name

    if "age" in data:

        age = get_int(
            data["age"]
        )

        if age is None or age < 0:

            return jsonify({
                "error": "Invalid age"
            }), 400

        patient.age = age

    if "gender" in data:

        gender = str(
            data["gender"]
        ).strip()

        if not gender:

            return jsonify({
                "error": "Gender cannot be empty"
            }), 400

        patient.gender = gender

    if "contact" in data:

        contact = str(
            data["contact"]
        ).strip()

        if not contact:

            return jsonify({
                "error": "Contact cannot be empty"
            }), 400

        existing = Patient.query.filter(
            Patient.contact == contact,
            Patient.id != id
        ).first()

        if existing:

            return jsonify({
                "error": "Contact already exists"
            }), 409

        patient.contact = contact

    db.session.commit()

    return jsonify({

        "message": "Patient updated",

        "patient": patient_dict(patient)

    }), 200


@app.route(
    "/api/patients/<int:id>",
    methods=["DELETE"]
)
@admin_required_api
def api_delete_patient(id):

    patient = db.get_or_404(
        Patient,
        id
    )

    db.session.delete(patient)
    db.session.commit()

    return jsonify({
        "message": "Patient deleted"
    }), 200


# =========================================================
# API DOCTORS
# =========================================================

@app.route(
    "/api/doctors",
    methods=["GET"]
)
@jwt_required
def api_get_doctors():

    doctors_list = Doctor.query.all()

    return jsonify([
        doctor_dict(d)
        for d in doctors_list
    ]), 200


@app.route(
    "/api/doctors/<int:id>",
    methods=["GET"]
)
@jwt_required
def api_get_doctor(id):

    doctor = db.get_or_404(
        Doctor,
        id
    )

    return jsonify(
        doctor_dict(doctor)
    ), 200


@app.route(
    "/api/doctors",
    methods=["POST"]
)
@admin_required_api
def api_create_doctor():

    data = json_data()

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    specialization = str(
        data.get(
            "specialization",
            ""
        )
    ).strip()

    if not name or not specialization:

        return jsonify({
            "error": (
                "Name and specialization are required"
            )
        }), 400

    doctor = Doctor(

        name=name,

        specialization=specialization
    )

    db.session.add(doctor)
    db.session.commit()

    return jsonify({

        "message": "Doctor created successfully",

        "doctor": doctor_dict(doctor)

    }), 201


@app.route(
    "/api/doctors/<int:id>",
    methods=["PUT", "PATCH"]
)
@admin_required_api
def api_update_doctor(id):

    doctor = db.get_or_404(
        Doctor,
        id
    )

    data = json_data()

    if not data:

        return jsonify({
            "error": "JSON body required"
        }), 400

    if "name" in data:

        name = str(
            data["name"]
        ).strip()

        if not name:

            return jsonify({
                "error": "Name cannot be empty"
            }), 400

        doctor.name = name

    if "specialization" in data:

        specialization = str(
            data["specialization"]
        ).strip()

        if not specialization:

            return jsonify({
                "error": (
                    "Specialization cannot be empty"
                )
            }), 400

        doctor.specialization = specialization

    db.session.commit()

    return jsonify({

        "message": "Doctor updated",

        "doctor": doctor_dict(doctor)

    }), 200


@app.route(
    "/api/doctors/<int:id>",
    methods=["DELETE"]
)
@admin_required_api
def api_delete_doctor(id):

    doctor = db.get_or_404(
        Doctor,
        id
    )

    User.query.filter_by(
        doctor_id=id
    ).update({
        "doctor_id": None
    })

    db.session.delete(doctor)
    db.session.commit()

    return jsonify({
        "message": "Doctor deleted"
    }), 200


# =========================================================
# API APPOINTMENTS
# =========================================================

@app.route(
    "/api/appointments",
    methods=["GET"]
)
@jwt_required
def api_get_appointments():

    user = jwt_user()

    if user.role == "doctor":

        appointments_list = (
            Appointment.query
            .filter_by(
                doctor_id=user.doctor_id
            )
            .all()
        )

    else:

        appointments_list = (
            Appointment.query.all()
        )

    return jsonify([
        appointment_dict(a)
        for a in appointments_list
    ]), 200


@app.route(
    "/api/appointments/<int:id>",
    methods=["GET"]
)
@jwt_required
def api_get_appointment(id):

    appointment = db.get_or_404(
        Appointment,
        id
    )

    user = jwt_user()

    if (
        user.role == "doctor"
        and appointment.doctor_id != user.doctor_id
    ):

        return jsonify({
            "error": "Access denied"
        }), 403

    return jsonify(
        appointment_dict(appointment)
    ), 200


@app.route(
    "/api/appointments",
    methods=["POST"]
)
@admin_required_api
def api_create_appointment():

    data = json_data()

    patient_id = get_int(
        data.get("patient_id")
    )

    doctor_id = get_int(
        data.get("doctor_id")
    )

    appointment_date = parse_date(
        data.get("date")
    )

    diagnosis = str(
        data.get(
            "diagnosis",
            ""
        )
    ).strip()

    status = str(
        data.get(
            "status",
            "Scheduled"
        )
    ).strip()

    recovery_date = parse_date(
        data.get("recovery_date")
    )

    if (
        patient_id is None
        or doctor_id is None
    ):

        return jsonify({
            "error": (
                "Patient ID and Doctor ID are required"
            )
        }), 400

    if not db.session.get(
        Patient,
        patient_id
    ):

        return jsonify({
            "error": "Patient not found"
        }), 404

    if not db.session.get(
        Doctor,
        doctor_id
    ):

        return jsonify({
            "error": "Doctor not found"
        }), 404

    if not appointment_date:

        return jsonify({
            "error": (
                "Valid appointment date required "
                "(YYYY-MM-DD)"
            )
        }), 400

    if not diagnosis:

        return jsonify({
            "error": "Diagnosis is required"
        }), 400

    if (
        recovery_date
        and recovery_date < appointment_date
    ):

        return jsonify({
            "error": (
                "Recovery date cannot be "
                "before appointment date"
            )
        }), 400

    appointment = Appointment(

        patient_id=patient_id,

        doctor_id=doctor_id,

        date=appointment_date,

        diagnosis=diagnosis,

        status=status or "Scheduled",

        recovery_date=recovery_date
    )

    db.session.add(appointment)
    db.session.commit()

    return jsonify({

        "message": (
            "Appointment created successfully"
        ),

        "appointment": appointment_dict(
            appointment
        )

    }), 201


@app.route(
    "/api/appointments/<int:id>",
    methods=["PUT", "PATCH"]
)
@jwt_required
def api_update_appointment(id):

    appointment = db.get_or_404(
        Appointment,
        id
    )

    user = jwt_user()

    if (
        user.role == "doctor"
        and appointment.doctor_id != user.doctor_id
    ):

        return jsonify({
            "error": "Access denied"
        }), 403

    data = json_data()

    if not data:

        return jsonify({
            "error": "JSON body required"
        }), 400

    if "date" in data:

        new_date = parse_date(
            data["date"]
        )

        if not new_date:

            return jsonify({
                "error": "Invalid date"
            }), 400

        appointment.date = new_date

    if "diagnosis" in data:

        diagnosis = str(
            data["diagnosis"]
        ).strip()

        if not diagnosis:

            return jsonify({
                "error": "Diagnosis cannot be empty"
            }), 400

        appointment.diagnosis = diagnosis

    if "status" in data:

        status = str(
            data["status"]
        ).strip()

        if not status:

            return jsonify({
                "error": "Status cannot be empty"
            }), 400

        appointment.status = status

    if "recovery_date" in data:

        if data["recovery_date"]:

            recovery_date = parse_date(
                data["recovery_date"]
            )

            if not recovery_date:

                return jsonify({
                    "error": "Invalid recovery date"
                }), 400

            appointment_date = normalize_date(
                appointment.date
            )

            if (
                appointment_date
                and recovery_date < appointment_date
            ):

                return jsonify({
                    "error": (
                        "Recovery date cannot be "
                        "before appointment date"
                    )
                }), 400

            appointment.recovery_date = recovery_date

        else:

            appointment.recovery_date = None

    if user.role == "admin":

        if "patient_id" in data:

            patient_id = get_int(
                data["patient_id"]
            )

            if patient_id is None:

                return jsonify({
                    "error": "Invalid patient ID"
                }), 400

            if not db.session.get(
                Patient,
                patient_id
            ):

                return jsonify({
                    "error": "Patient not found"
                }), 404

            appointment.patient_id = patient_id

        if "doctor_id" in data:

            doctor_id = get_int(
                data["doctor_id"]
            )

            if doctor_id is None:

                return jsonify({
                    "error": "Invalid doctor ID"
                }), 400

            if not db.session.get(
                Doctor,
                doctor_id
            ):

                return jsonify({
                    "error": "Doctor not found"
                }), 404

            appointment.doctor_id = doctor_id

    db.session.commit()

    return jsonify({

        "message": "Appointment updated",

        "appointment": appointment_dict(
            appointment
        )

    }), 200


@app.route(
    "/api/appointments/<int:id>",
    methods=["DELETE"]
)
@admin_required_api
def api_delete_appointment(id):

    appointment = db.get_or_404(
        Appointment,
        id
    )

    db.session.delete(appointment)
    db.session.commit()

    return jsonify({
        "message": "Appointment deleted"
    }), 200


# =========================================================
# API APPOINTMENT EXCEL EXPORT
# =========================================================

@app.route(
    "/api/reports/appointments/export",
    methods=["GET"]
)
@jwt_required
def api_export_appointments():

    user = jwt_user()

    if user.role == "doctor":

        query = Appointment.query.filter_by(
            doctor_id=user.doctor_id
        )

    else:

        query = Appointment.query

    appointments_list = query.all()

    data = [
        appointment_dict(a)
        for a in appointments_list
    ]

    df = pd.DataFrame(data)

    if df.empty:

        df = pd.DataFrame(
            columns=[
                "id",
                "patient_id",
                "patient_name",
                "doctor_id",
                "doctor_name",
                "date",
                "diagnosis",
                "status",
                "recovery_date",
                "recovery_days"
            ]
        )

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Appointments"
        )

    output.seek(0)

    return send_file(

        output,

        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),

        as_attachment=True,

        download_name="appointments_report.xlsx"
    )


# =========================================================
# API ANALYTICS REPORT
# =========================================================

@app.route(
    "/api/reports/analytics",
    methods=["GET"]
)
@admin_required_api
def api_analytics_report():

    appointments_list = (
        Appointment.query.all()
    )

    data = [
        appointment_dict(a)
        for a in appointments_list
    ]

    if not data:

        return jsonify({

            "total_appointments": 0,

            "average_recovery_days": None,

            "status_counts": {}

        }), 200

    df = pd.DataFrame(data)

    recovery_days_series = (
        df["recovery_days"]
        .dropna()
    )

    avg_recovery = (

        float(
            np.mean(
                recovery_days_series
            )
        )

        if not recovery_days_series.empty

        else None
    )

    status_counts = (
        df["status"]
        .value_counts()
        .to_dict()
    )

    return jsonify({

        "total_appointments": len(df),

        "average_recovery_days": avg_recovery,

        "status_counts": status_counts

    }), 200


# =========================================================
# WEB ANALYTICS
# =========================================================

@app.route("/analytics")
@login_required
def analytics():

    user = current_web_user()

    # -----------------------------------------------------
    # Get appointments according to user role
    # -----------------------------------------------------

    if user.role == "doctor":

        appointments_list = (
            Appointment.query
            .filter_by(
                doctor_id=user.doctor_id
            )
            .all()
        )

    else:

        appointments_list = (
            Appointment.query.all()
        )

    # -----------------------------------------------------
    # Analytics variables
    # -----------------------------------------------------

    total_appointments = len(
        appointments_list
    )

    diagnosis_data = {}

    status_data = {}

    recovery_values = {}

    trend_data = {}

    doctor_data = []

    # -----------------------------------------------------
    # Process appointments
    # -----------------------------------------------------

    for appointment in appointments_list:

        # Diagnosis count
        diagnosis = (
            appointment.diagnosis
            or "Unknown"
        )

        diagnosis_data[diagnosis] = (
            diagnosis_data.get(
                diagnosis,
                0
            ) + 1
        )

        # Status count
        status = (
            appointment.status
            or "Unknown"
        )

        status_data[status] = (
            status_data.get(
                status,
                0
            ) + 1
        )

        # Recovery days
        recovery_days = (
            calculate_recovery_days(
                appointment
            )
        )

        if recovery_days is not None:

            recovery_values.setdefault(
                diagnosis,
                []
            ).append(
                recovery_days
            )

        # Appointment trend
        appointment_date = normalize_date(
            appointment.date
        )

        if appointment_date:

            month = appointment_date.strftime(
                "%Y-%m"
            )

            trend_data[month] = (
                trend_data.get(
                    month,
                    0
                ) + 1
            )

    # -----------------------------------------------------
    # Average recovery data
    # -----------------------------------------------------

    recovery_data = {

        diagnosis: round(
            sum(values) / len(values),
            2
        )

        for diagnosis, values
        in recovery_values.items()

        if values
    }

    # -----------------------------------------------------
    # Doctor performance
    # -----------------------------------------------------

    if user.role == "admin":

        doctors_list = Doctor.query.all()

    else:

        doctors_list = (
            [user.doctor]
            if user.doctor
            else []
        )

    for doctor in doctors_list:

        doctor_appointments = [

            appointment

            for appointment
            in appointments_list

            if appointment.doctor_id
            == doctor.id
        ]

        patients_treated = len(
            doctor_appointments
        )

        recovered = sum(

            1

            for appointment
            in doctor_appointments

            if str(
                appointment.status
                or ""
            ).lower()
            == "recovered"
        )

        recovery_rate = (

            round(
                recovered
                / patients_treated
                * 100,
                2
            )

            if patients_treated

            else 0
        )

        doctor_data.append({

            "doctor": doctor.name,

            "patients_treated":
                patients_treated,

            "recovered":
                recovered,

            "recovery_rate":
                recovery_rate
        })

    # -----------------------------------------------------
    # Render analytics page
    # -----------------------------------------------------

    return render_template(

        "analytics.html",

        total_appointments=
            total_appointments,

        diagnosis_data=
            diagnosis_data,

        status_data=
            status_data,

        recovery_data=
            recovery_data,

        trend_data=
            dict(
                sorted(
                    trend_data.items()
                )
            ),

        doctor_data=
            doctor_data
    )


# =========================================================
# WEB ANALYTICS CSV EXPORT
# =========================================================

@app.route(
    "/analytics/export/csv"
)
@login_required
def export_analytics_csv():

    user = current_web_user()

    if user.role == "doctor":

        appointments_list = (
            Appointment.query
            .filter_by(
                doctor_id=user.doctor_id
            )
            .all()
        )

    else:

        appointments_list = (
            Appointment.query.all()
        )

    rows = []

    for appointment in appointments_list:

        appointment_date = normalize_date(
            appointment.date
        )

        recovery_date = normalize_date(
            appointment.recovery_date
        )

        rows.append({

            "Appointment ID":
                appointment.id,

            "Patient ID":
                appointment.patient_id,

            "Patient Name": (

                appointment.patient.name

                if appointment.patient

                else ""
            ),

            "Doctor ID":
                appointment.doctor_id,

            "Doctor Name": (

                appointment.doctor.name

                if appointment.doctor

                else ""
            ),

            "Date": (

                appointment_date.isoformat()

                if appointment_date

                else ""
            ),

            "Diagnosis":
                appointment.diagnosis,

            "Status":
                appointment.status,

            "Recovery Date": (

                recovery_date.isoformat()

                if recovery_date

                else ""
            ),

            "Recovery Days":
                calculate_recovery_days(
                    appointment
                )
        })

    df = pd.DataFrame(rows)

    if df.empty:

        df = pd.DataFrame(
            columns=[

                "Appointment ID",

                "Patient ID",

                "Patient Name",

                "Doctor ID",

                "Doctor Name",

                "Date",

                "Diagnosis",

                "Status",

                "Recovery Date",

                "Recovery Days"
            ]
        )

    output = io.StringIO()

    df.to_csv(
        output,
        index=False
    )

    response = make_response(
        output.getvalue()
    )

    response.headers[
        "Content-Disposition"
    ] = (
        "attachment; "
        "filename=analytics.csv"
    )

    response.headers[
        "Content-Type"
    ] = "text/csv"

    return response


# =========================================================
# WEB ANALYTICS EXCEL EXPORT
# =========================================================

@app.route(
    "/analytics/export/excel"
)
@login_required
def export_analytics_excel():

    user = current_web_user()

    if user.role == "doctor":

        appointments_list = (
            Appointment.query
            .filter_by(
                doctor_id=user.doctor_id
            )
            .all()
        )

    else:

        appointments_list = (
            Appointment.query.all()
        )

    rows = []

    for appointment in appointments_list:

        appointment_date = normalize_date(
            appointment.date
        )

        recovery_date = normalize_date(
            appointment.recovery_date
        )

        rows.append({

            "Appointment ID":
                appointment.id,

            "Patient ID":
                appointment.patient_id,

            "Patient Name": (

                appointment.patient.name

                if appointment.patient

                else ""
            ),

            "Doctor ID":
                appointment.doctor_id,

            "Doctor Name": (

                appointment.doctor.name

                if appointment.doctor

                else ""
            ),

            "Date": (

                appointment_date.isoformat()

                if appointment_date

                else ""
            ),

            "Diagnosis":
                appointment.diagnosis,

            "Status":
                appointment.status,

            "Recovery Date": (

                recovery_date.isoformat()

                if recovery_date

                else ""
            ),

            "Recovery Days":
                calculate_recovery_days(
                    appointment
                )
        })

    df = pd.DataFrame(rows)

    if df.empty:

        df = pd.DataFrame(
            columns=[

                "Appointment ID",

                "Patient ID",

                "Patient Name",

                "Doctor ID",

                "Doctor Name",

                "Date",

                "Diagnosis",

                "Status",

                "Recovery Date",

                "Recovery Days"
            ]
        )

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Analytics"
        )

    output.seek(0)

    return send_file(

        output,

        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),

        as_attachment=True,

        download_name="hospital_analytics.xlsx"
    )


# =========================================================
# WEB ANALYTICS CSV UPLOAD
# =========================================================

@app.route(
    "/analytics/upload",
    methods=["GET", "POST"]
)
@login_required
def upload_analytics():

    # -----------------------------------------------------
    # GET request
    # -----------------------------------------------------

    if request.method == "GET":

        return render_template(

            "upload.html",

            columns=None,

            rows=None
        )

    # -----------------------------------------------------
    # Get uploaded file
    # -----------------------------------------------------

    file = request.files.get(
        "file"
    )

    if not file or file.filename == "":

        flash(
            "Please select a CSV file",
            "danger"
        )

        return redirect(
            url_for(
                "upload_analytics"
            )
        )

    # -----------------------------------------------------
    # Validate file extension
    # -----------------------------------------------------

    if not file.filename.lower().endswith(
        ".csv"
    ):

        flash(
            "Only CSV files are allowed",
            "danger"
        )

        return redirect(
            url_for(
                "upload_analytics"
            )
        )

    # -----------------------------------------------------
    # Read CSV
    # -----------------------------------------------------

    try:

        df = pd.read_csv(
            file
        )

        # Convert column names to strings
        df.columns = [

            str(column)

            for column
            in df.columns
        ]

        # Replace NaN values
        df = df.replace(
            {np.nan: ""}
        )

        columns = (
            df.columns.tolist()
        )

        rows = (
            df.to_dict(
                orient="records"
            )
        )

        flash(
            "CSV uploaded successfully",
            "success"
        )

        return render_template(

            "upload.html",

            columns=columns,

            rows=rows
        )

    except Exception as error:

        flash(

            f"Unable to read CSV file: {error}",

            "danger"
        )

        return redirect(
            url_for(
                "upload_analytics"
            )
        )


# =========================================================
# API STATUS
# =========================================================

@app.route(
    "/api/status",
    methods=["GET"]
)
def api_status():

    return jsonify({

        "status": "success",

        "message": (
            "Hospital Management System "
            "API is running"
        )

    }), 200


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def not_found(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({
            "error": "Resource not found"
        }), 404

    return render_template(
        "404.html"
    ), 404


@app.errorhandler(500)
def internal_error(error):

    db.session.rollback()

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({
            "error": "Internal server error"
        }), 500

    return render_template(
        "500.html"
    ), 500


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True
    )