from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


# =========================================
# USER MODEL
# =========================================

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(80),
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
        db.ForeignKey(
            "doctors.id",
            ondelete="SET NULL"
        ),
        unique=True,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    doctor = db.relationship(
        "Doctor",
        back_populates="user",
        foreign_keys=[doctor_id]
    )

    def __repr__(self):
        return f"<User {self.username}>"


# =========================================
# PATIENT MODEL
# =========================================

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
        db.String(15),
        unique=True,
        nullable=False
    )

    appointments = db.relationship(
        "Appointment",
        back_populates="patient",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Patient {self.name}>"


# =========================================
# DOCTOR MODEL
# =========================================

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
        back_populates="doctor",
        lazy=True,
        cascade="all, delete-orphan"
    )

    user = db.relationship(
        "User",
        back_populates="doctor",
        uselist=False,
        cascade="save-update"
    )

    def __repr__(self):
        return f"<Doctor {self.name}>"


# =========================================
# APPOINTMENT MODEL
# =========================================

class Appointment(db.Model):

    __tablename__ = "appointments"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    patient_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "patients.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "doctors.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    date = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    diagnosis = db.Column(
        db.String(255),
        nullable=False
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="Under Treatment"
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    patient = db.relationship(
        "Patient",
        back_populates="appointments"
    )

    doctor = db.relationship(
        "Doctor",
        back_populates="appointments"
    )

    def __repr__(self):
        return f"<Appointment {self.id}>"