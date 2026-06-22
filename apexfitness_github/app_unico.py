import enum
import os
import re
import secrets
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps

import jwt
import qrcode
from flask import Flask, Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, session, url_for
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_mail import Mail, Message
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, or_


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-in-production")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-jwt-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///apexfitness.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "apexfitness@gmail.com")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "Apex Fitness <apexfitness@gmail.com>")
    ACADEMY_PHONE = os.getenv("ACADEMY_PHONE", "+55 (83) 98689-2601")
    ACADEMY_EMAIL = os.getenv("ACADEMY_EMAIL", "apexfitness@gmail.com")
    ACADEMY_ADDRESS = os.getenv("ACADEMY_ADDRESS", "Av. Joao Cancio da Silva, 1240 - Manaira, Joao Pessoa - PB")
    PAYMENT_OWNER = os.getenv("PAYMENT_OWNER", "Victor Lucas Pedroza de Andrade")
    PAYMENT_CPF = os.getenv("PAYMENT_CPF", "715.313.634-74")
    PAYMENT_BANK = os.getenv("PAYMENT_BANK", "Mercado Pago")
    PAYMENT_AGENCY = os.getenv("PAYMENT_AGENCY", "0001")
    PAYMENT_ACCOUNT = os.getenv("PAYMENT_ACCOUNT", "23332177265")


class DevConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv("DEV_DATABASE_URL", "sqlite:///apexfitness_dev.db")
    WTF_CSRF_ENABLED = False
    TEMPLATES_AUTO_RELOAD = True


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
bcrypt = Bcrypt()
csrf = CSRFProtect()


# ---- app/models/entities.py ----
class Role(enum.Enum):
    DONO = "DONO"
    GERENTE_GERAL = "GERENTE_GERAL"
    GERENTE_ACADEMIA = "GERENTE_ACADEMIA"
    GERENTE_MERCADO = "GERENTE_MERCADO"
    ADMIN = "ADMIN"
    RECEPCAO = "RECEPCAO"
    PROFESSOR = "PROFESSOR"
    PERSONAL = "PERSONAL"
    NUTRICIONISTA = "NUTRICIONISTA"
    FISIOTERAPEUTA = "FISIOTERAPEUTA"
    ATENDENTE_MERCADO = "ATENDENTE_MERCADO"
    ALUNO = "ALUNO"


student_services = db.Table(
    "student_services",
    db.Column("student_id", db.Integer, db.ForeignKey("student_profiles.id")),
    db.Column("service_id", db.Integer, db.ForeignKey("services.id")),
)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False, index=True)
    phone = db.Column(db.String(30))
    cpf = db.Column(db.String(20), unique=True)
    rg = db.Column(db.String(30))
    address = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    reset_token = db.Column(db.String(255))
    reset_token_expires_at = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    student_profile = db.relationship("StudentProfile", foreign_keys="StudentProfile.user_id", back_populates="user", uselist=False)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password or "")


class Plan(TimestampMixin, db.Model):
    __tablename__ = "plans"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    description = db.Column(db.Text)
    monthly_price = db.Column(db.Numeric(10, 2), nullable=False)
    quarterly_price = db.Column(db.Numeric(10, 2), nullable=False)
    annual_price = db.Column(db.Numeric(10, 2), nullable=False)
    benefits = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class Service(TimestampMixin, db.Model):
    __tablename__ = "services"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(60), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image_url = db.Column(db.String(255))
    professional_role = db.Column(db.Enum(Role))
    is_active = db.Column(db.Boolean, default=True)


class StudentProfile(TimestampMixin, db.Model):
    __tablename__ = "student_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    sex = db.Column(db.String(30))
    age = db.Column(db.Integer)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"))
    billing_cycle = db.Column(db.String(30), default="monthly")
    account_status = db.Column(db.String(30), default="ATIVO")
    next_payment_at = db.Column(db.Date, default=lambda: datetime.utcnow().date() + timedelta(days=30))
    personal_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    nutritionist_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    physiotherapist_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = db.relationship("User", foreign_keys=[user_id], back_populates="student_profile")
    plan = db.relationship("Plan")
    services = db.relationship("Service", secondary=student_services)
    personal = db.relationship("User", foreign_keys=[personal_id])
    nutritionist = db.relationship("User", foreign_keys=[nutritionist_id])
    physiotherapist = db.relationship("User", foreign_keys=[physiotherapist_id])

    @property
    def is_delinquent(self):
        return self.account_status == "INADIMPLENTE"


class Payment(TimestampMixin, db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(40), default="PENDENTE", index=True)
    due_date = db.Column(db.Date, nullable=False)
    paid_at = db.Column(db.DateTime)
    receipt_pdf_path = db.Column(db.String(255))
    student = db.relationship("StudentProfile")


class ServiceRequest(TimestampMixin, db.Model):
    __tablename__ = "service_requests"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"))
    status = db.Column(db.String(30), default="PENDENTE", nullable=False, index=True)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decided_at = db.Column(db.DateTime)
    student = db.relationship("StudentProfile")
    service = db.relationship("Service")
    payment = db.relationship("Payment")


class TrainingPlan(TimestampMixin, db.Model):
    __tablename__ = "training_plans"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    base_type = db.Column(db.String(80))
    title = db.Column(db.String(140), nullable=False)
    exercises = db.Column(db.Text, nullable=False)
    observations = db.Column(db.Text)
    pdf_path = db.Column(db.String(255))
    student = db.relationship("StudentProfile")
    author = db.relationship("User")


class FoodPlan(TimestampMixin, db.Model):
    __tablename__ = "food_plans"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False)
    nutritionist_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    meals = db.Column(db.Text, nullable=False)
    schedules = db.Column(db.Text)
    observations = db.Column(db.Text)
    pdf_path = db.Column(db.String(255))
    student = db.relationship("StudentProfile")
    nutritionist = db.relationship("User")


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(60), nullable=False, index=True)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    minimum_stock = db.Column(db.Integer, default=5)
    image_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)


class StockMovement(TimestampMixin, db.Model):
    __tablename__ = "stock_movements"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    movement_type = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_value = db.Column(db.Numeric(10, 2))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product = db.relationship("Product")
    user = db.relationship("User")


class Sale(TimestampMixin, db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"))
    payment_method = db.Column(db.String(40), nullable=False)
    payment_status = db.Column(db.String(40), default="PAGO")
    total = db.Column(db.Numeric(10, 2), nullable=False)
    pix_key = db.Column(db.String(120))
    pix_qr_path = db.Column(db.String(255))
    card_authorization = db.Column(db.String(80))
    receipt_pdf_path = db.Column(db.String(255))
    user = db.relationship("User")
    student = db.relationship("StudentProfile")
    items = db.relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(db.Model):
    __tablename__ = "sale_items"
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product")


class CheckIn(TimestampMixin, db.Model):
    __tablename__ = "checkins"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False)
    entry_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    exit_at = db.Column(db.DateTime)
    qr_code = db.Column(db.String(255))
    blocked_reason = db.Column(db.String(255))
    student = db.relationship("StudentProfile")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(80), nullable=False, index=True)
    entity = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.String(80))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actor = db.relationship("User")


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    user = db.relationship("User")


class PdfDocument(TimestampMixin, db.Model):
    __tablename__ = "pdf_documents"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    document_type = db.Column(db.String(80), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    owner = db.relationship("User")


class AppSetting(db.Model):
    __tablename__ = "app_settings"
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")


# ---- app/utils/security.py ----
def roles_required(*roles):
    allowed = {Role[r] if isinstance(r, str) else r for r in roles}

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))
            if current_user.role != Role.ADMIN and current_user.role not in allowed:
                flash("Voce nao tem permissao para acessar esta area.", "error")
                return redirect(url_for("dashboard.home"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def admin_user():
    return current_user.is_authenticated and current_user.role == Role.ADMIN


def validate_cpf(cpf):
    numbers = re.sub(r"\D", "", cpf or "")
    if len(numbers) != 11 or numbers == numbers[0] * 11:
        return False

    def digit(part):
        total = sum(int(n) * w for n, w in zip(part, range(len(part) + 1, 1, -1)))
        rest = (total * 10) % 11
        return 0 if rest == 10 else rest

    return digit(numbers[:9]) == int(numbers[9]) and digit(numbers[:10]) == int(numbers[10])


def validate_phone(phone):
    return bool(re.fullmatch(r"\+?\d[\d\s().-]{9,24}", phone or ""))


def strong_password(password):
    return bool(password and len(password) >= 8 and re.search(r"[A-Za-z]", password) and re.search(r"\d", password))


def create_jwt(user):
    payload = {"sub": str(user.id), "role": user.role.value, "email": user.email}
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def jwt_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "", 1)
        try:
            request.jwt_payload = jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
        except Exception:
            return {"error": "invalid_token"}, 401
        return view(*args, **kwargs)

    return wrapped


def log_action(action, entity, entity_id=None, details=None):
    actor_id = current_user.id if current_user.is_authenticated else None
    db.session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr) if request else None,
        )
    )


def setting_value(key, default=""):
    setting = db.session.get(AppSetting, key)
    return setting.value if setting else default


def set_setting(key, value):
    setting = db.session.get(AppSetting, key)
    if not setting:
        setting = AppSetting(key=key)
    setting.value = "" if value is None else str(value)
    db.session.add(setting)


def setting_bool(value):
    return str(value).lower() in {"1", "true", "on", "yes", "sim"}


def apply_mail_settings(app):
    keys = {
        "MAIL_SERVER": app.config.get("MAIL_SERVER", ""),
        "MAIL_PORT": app.config.get("MAIL_PORT", 587),
        "MAIL_USE_TLS": app.config.get("MAIL_USE_TLS", True),
        "MAIL_USERNAME": app.config.get("MAIL_USERNAME", ""),
        "MAIL_PASSWORD": app.config.get("MAIL_PASSWORD", ""),
        "MAIL_DEFAULT_SENDER": app.config.get("MAIL_DEFAULT_SENDER", ""),
    }
    for key, default in keys.items():
        value = setting_value(key, default)
        if key == "MAIL_PORT":
            value = int(value or 587)
        elif key == "MAIL_USE_TLS":
            value = setting_bool(value)
        app.config[key] = value
    mail.init_app(app)


def billing_amount(plan, billing_cycle):
    if billing_cycle == "annual":
        return plan.annual_price
    if billing_cycle == "quarterly":
        return plan.quarterly_price
    return plan.monthly_price


def next_due_date(billing_cycle):
    days = {"monthly": 30, "quarterly": 90, "annual": 365}.get(billing_cycle, 30)
    return datetime.utcnow().date() + timedelta(days=days)


def confirm_payment(payment, method=None):
    payment.status = "PAGO"
    payment.paid_at = datetime.utcnow()
    payment.method = method or payment.method
    profile = payment.student
    service_request = ServiceRequest.query.filter_by(payment_id=payment.id).first()
    if service_request:
        service_request.status = "APROVADO"
        service_request.decided_at = datetime.utcnow()
        if service_request.service not in profile.services:
            profile.services.append(service_request.service)
        profile.account_status = "ATIVO" if profile.account_status == "PENDENTE" else profile.account_status
    else:
        profile.account_status = "ATIVO"
        profile.next_payment_at = next_due_date(profile.billing_cycle)
    db.session.add(payment)
    db.session.add(profile)
    return profile


def reject_payment(payment):
    payment.status = "RECUSADO"
    service_request = ServiceRequest.query.filter_by(payment_id=payment.id).first()
    if service_request:
        service_request.status = "RECUSADO"
        service_request.decided_at = datetime.utcnow()
    elif payment.student.account_status == "PENDENTE":
        payment.student.account_status = "BLOQUEADO"
    db.session.add(payment)


# ---- app/services/documents.py ----
def storage_folder(kind):
    folder = os.path.join(current_app.static_folder, kind)
    os.makedirs(folder, exist_ok=True)
    return folder


def generate_pdf(title, lines, filename_prefix):
    filename = f"{filename_prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    folder = storage_folder("pdfs")
    path = os.path.join(folder, filename)
    try:
        open(path, "ab").close()
        os.remove(path)
    except PermissionError:
        folder = os.path.join(tempfile.gettempdir(), "apexfitness", "pdfs")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
    pdf = canvas.Canvas(path, pagesize=A4)
    _, height = A4
    y = height - 72
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(72, y, title)
    y -= 36
    pdf.setFont("Helvetica", 11)
    for line in lines:
        if y < 72:
            pdf.showPage()
            y = height - 72
            pdf.setFont("Helvetica", 11)
        pdf.drawString(72, y, str(line)[:110])
        y -= 18
    pdf.save()
    return path


def generate_qr(payload, prefix="qr"):
    folder = storage_folder("qrcodes")
    filename = f"{prefix}_{uuid.uuid4().hex}.png"
    path = os.path.join(folder, filename)
    qrcode.make(payload).save(path)
    return path


# ---- app/services/mailer.py ----
def send_email(user, subject, body):
    db.session.add(Notification(user_id=user.id, title=subject, message=body))
    if not current_app.config.get("MAIL_PASSWORD"):
        current_app.logger.info("Email simulado para %s: %s", user.email, subject)
        return False
    try:
        mail.send(Message(subject=subject, recipients=[user.email], body=body))
        return True
    except Exception as exc:
        current_app.logger.exception("Falha ao enviar email para %s: %s", user.email, exc)
        return False


def account_created(user, raw_password):
    send_email(
        user,
        "Conta criada - Apex Fitness",
        f"Ola, {user.name}.\n\nSua conta foi criada.\nLogin: {user.email}\nSenha temporaria: {raw_password}",
    )


# ---- app/services/payments.py ----
def money(value):
    return f"R$ {Decimal(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pix_payload(amount, description):
    key = str(uuid.uuid4())
    payload = (
        f"PIX|BANCO={current_app.config['PAYMENT_BANK']}|AG={current_app.config['PAYMENT_AGENCY']}|"
        f"CONTA={current_app.config['PAYMENT_ACCOUNT']}|CPF={current_app.config['PAYMENT_CPF']}|"
        f"VALOR={amount}|DESC={description}|CHAVE={key}"
    )
    return key, generate_qr(payload, "pix")


# ---- app/services/seed.py ----
def user(email, name, role, password, **kwargs):
    found = User.query.filter_by(email=email).first()
    if found:
        return found
    obj = User(email=email, name=name, role=role, **kwargs)
    obj.set_password(password)
    db.session.add(obj)
    db.session.flush()
    return obj


def seed_database():
    if not Plan.query.first():
        db.session.add_all(
            [
                Plan(name="BASIC", description="Musculacao em horario comercial.", monthly_price=99, quarterly_price=279, annual_price=999, benefits="Musculacao;Horario comercial"),
                Plan(name="PREMIUM", description="Basic + Muay Thai, Pilates e Yoga.", monthly_price=169, quarterly_price=459, annual_price=1690, benefits="Musculacao;Muay Thai;Pilates;Yoga"),
                Plan(name="ELITE", description="Premium + personal, nutricionista, fisioterapeuta e VIP.", monthly_price=299, quarterly_price=819, annual_price=2990, benefits="Tudo premium;Personal;Nutricionista;Fisioterapeuta;VIP"),
            ]
        )
    if not Service.query.first():
        db.session.add_all(
            [
                Service(name="Muay Thai", category="Aulas", description="Defesa pessoal, resistencia e disciplina.", price=89, image_url="https://images.unsplash.com/photo-1549719386-74dfcbf7dbed?auto=format&fit=crop&w=900&q=80"),
                Service(name="Pilates", category="Aulas", description="Mobilidade, postura e fortalecimento.", price=120, image_url="https://images.unsplash.com/photo-1518611012118-696072aa579a?auto=format&fit=crop&w=900&q=80"),
                Service(name="Yoga", category="Aulas", description="Equilibrio, flexibilidade e respiracao.", price=99, image_url="https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=900&q=80"),
                Service(name="Personal", category="Profissionais", description="Treino individualizado.", price=250, professional_role=Role.PERSONAL, image_url="https://images.unsplash.com/photo-1571019613576-2b22c76fd955?auto=format&fit=crop&w=900&q=80"),
                Service(name="Nutricionista", category="Profissionais", description="Plano alimentar personalizado.", price=220, professional_role=Role.NUTRICIONISTA, image_url="https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&w=900&q=80"),
                Service(name="Fisioterapeuta", category="Profissionais", description="Prevencao e reabilitacao.", price=230, professional_role=Role.FISIOTERAPEUTA, image_url="https://images.unsplash.com/photo-1576091160550-2173dba999ef?auto=format&fit=crop&w=900&q=80"),
            ]
        )
    if not Product.query.first():
        db.session.add_all(
            [
                Product(name="Whey Protein Apex", category="Whey", description="Proteina concentrada premium.", price=129.90, stock=25, minimum_stock=5, image_url="https://images.unsplash.com/photo-1775199603078-e1d964929e10?auto=format&fit=crop&w=900&q=80"),
                Product(name="Creatina Monohidratada", category="Creatina", description="Creatina 300g.", price=89.90, stock=40, minimum_stock=8, image_url="https://images.unsplash.com/photo-1693996045435-af7c48b9cafb?auto=format&fit=crop&w=900&q=80"),
                Product(name="Pre-treino Nitro", category="Pre-treino", description="Energia e foco.", price=119.90, stock=18, minimum_stock=4, image_url="https://images.unsplash.com/photo-1704650311981-419f841421cc?auto=format&fit=crop&w=900&q=80"),
                Product(name="Hiper Mass", category="Hipercalorico", description="Ganho de massa.", price=139.90, stock=12, minimum_stock=3, image_url="https://images.unsplash.com/photo-1704650311190-7eeb9c4f6e11?auto=format&fit=crop&w=900&q=80"),
                Product(name="Multivitaminico", category="Vitaminas", description="Suporte diario.", price=59.90, stock=30, minimum_stock=8, image_url="https://images.unsplash.com/photo-1701201632697-7ec41bfee65f?auto=format&fit=crop&w=900&q=80"),
                Product(name="Barra Proteica", category="Barras proteicas", description="Snack funcional.", price=12.90, stock=80, minimum_stock=20, image_url="https://images.unsplash.com/photo-1742860866012-fc167d8366bf?auto=format&fit=crop&w=900&q=80"),
            ]
        )
    admin = user("admin@apexfitness.com", "Administrador Apex", Role.ADMIN, "admin123")
    user("recepcao@apexfitness.com", "Recepcao Apex", Role.RECEPCAO, "recepcao123")
    user("professor@apexfitness.com", "Professor Apex", Role.PROFESSOR, "professor123")
    user("gerente.academia@apexfitness.com", "Gerente Academia Apex", Role.GERENTE_ACADEMIA, "gerenteacademia123")
    user("gerente.loja@apexfitness.com", "Gerente Loja Apex", Role.GERENTE_MERCADO, "gerenteloja123")
    user("gerente.geral@apexfitness.com", "Gerente Geral Apex", Role.GERENTE_GERAL, "gerentegeral123")
    user("dono@apexfitness.com", "Dono Apex", Role.DONO, "dono12345")
    personal = user("personal@apexfitness.com", "Personal Apex", Role.PERSONAL, "personal123")
    nutritionist = user("nutri@apexfitness.com", "Nutricionista Apex", Role.NUTRICIONISTA, "nutri123")
    physio = user("fisio@apexfitness.com", "Fisioterapeuta Apex", Role.FISIOTERAPEUTA, "fisio123")
    user("mercado@apexfitness.com", "Atendente Mercado", Role.ATENDENTE_MERCADO, "mercado123")
    aluno = user("aluno@apexfitness.com", "Aluno Demo", Role.ALUNO, "aluno123", cpf="52998224725", phone="83986892601", address="Joao Pessoa")
    if not StudentProfile.query.filter_by(user_id=aluno.id).first():
        plan = Plan.query.filter_by(name="ELITE").first()
        profile = StudentProfile(user_id=aluno.id, sex="Nao informado", age=25, plan_id=plan.id, personal_id=personal.id, nutritionist_id=nutritionist.id, physiotherapist_id=physio.id)
        profile.services = Service.query.all()
        db.session.add(profile)
        db.session.flush()
        db.session.add(Payment(student_id=profile.id, amount=plan.monthly_price, method="PIX", status="PENDENTE", due_date=datetime.utcnow().date() + timedelta(days=10)))
    db.session.commit()


# ---- app/public/routes.py ----
public_bp = Blueprint("public", __name__)


@public_bp.before_request
def keep_logged_users_in_their_system():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))


@public_bp.get("/")
def index():
    return render_template("public/index.html", plans=Plan.query.filter_by(is_active=True).all(), services=Service.query.filter_by(is_active=True).all(), products=Product.query.filter_by(is_active=True).limit(6).all())


@public_bp.get("/sobre")
def about():
    return render_template("public/about.html")


@public_bp.get("/planos")
def plans():
    return render_template("public/plans.html", plans=Plan.query.filter_by(is_active=True).all())


@public_bp.route("/cadastro", methods=["GET", "POST"])
def signup():
    plans = Plan.query.filter_by(is_active=True).order_by(Plan.monthly_price).all()
    selected_plan = db.session.get(Plan, request.args.get("plan_id", type=int)) if request.args.get("plan_id") else None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        cpf = request.form.get("cpf", "")
        phone = request.form.get("phone", "")
        password = request.form.get("password", "")
        plan = db.session.get(Plan, int(request.form.get("plan_id"))) if request.form.get("plan_id") else None
        billing_cycle = request.form.get("billing_cycle") or "monthly"
        if User.query.filter_by(email=email).first():
            flash("Email ja cadastrado. Entre com sua conta ou recupere a senha.", "error")
        elif cpf and not validate_cpf(cpf):
            flash("CPF invalido.", "error")
        elif cpf and User.query.filter_by(cpf=cpf).first():
            flash("CPF ja cadastrado.", "error")
        elif phone and not validate_phone(phone):
            flash("Telefone invalido.", "error")
        elif not strong_password(password):
            flash("Senha deve ter 8 caracteres, letras e numeros.", "error")
        elif not plan:
            flash("Selecione um plano para continuar.", "error")
        else:
            aluno = User(
                name=request.form.get("name", "").strip(),
                email=email,
                cpf=cpf or None,
                rg=request.form.get("rg", "").strip(),
                phone=phone,
                address=request.form.get("address", "").strip(),
                role=Role.ALUNO,
            )
            aluno.set_password(password)
            db.session.add(aluno)
            db.session.flush()
            profile = StudentProfile(
                user_id=aluno.id,
                sex=request.form.get("sex"),
                age=int(request.form.get("age") or 0),
                plan_id=plan.id,
                billing_cycle=billing_cycle,
                account_status="PENDENTE",
            )
            db.session.add(profile)
            db.session.flush()
            db.session.add(Payment(student_id=profile.id, amount=billing_amount(plan, billing_cycle), method="RECEPCAO", status="PENDENTE", due_date=datetime.utcnow().date()))
            log_action("PUBLIC_SIGNUP", "StudentProfile", profile.id, plan.name)
            account_created(aluno, password)
            db.session.commit()
            flash("Conta criada. Passe na recepcao para confirmar pagamento e liberar sua entrada.", "success")
            return redirect(url_for("auth.login"))
    return render_template("public/signup.html", plans=plans, selected_plan=selected_plan)


@public_bp.get("/servicos")
def services():
    return render_template("public/services.html", services=Service.query.filter_by(is_active=True).all())


@public_bp.get("/produtos")
def products():
    return render_template("public/products.html", products=Product.query.filter_by(is_active=True).all())


@public_bp.get("/contato")
def contact():
    return render_template("public/contact.html", phone=current_app.config["ACADEMY_PHONE"], email=current_app.config["ACADEMY_EMAIL"], address=current_app.config["ACADEMY_ADDRESS"])


# ---- app/auth/routes.py ----
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/entrar", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    if request.method == "POST":
        if session.get("login_block_until", 0) > time.time():
            flash("Muitas tentativas. Aguarde 1 minuto.", "error")
            return render_template("auth/login.html")
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter(func.lower(User.email) == email).first()
        if user and user.is_active and user.check_password(request.form.get("password", "")):
            session.pop("login_failures", None)
            session.pop("login_block_until", None)
            user.last_login_at = datetime.utcnow()
            db.session.add(user)
            log_action("LOGIN", "User", user.id)
            db.session.commit()
            login_user(user, remember=True)
            return redirect(request.args.get("next") or url_for("dashboard.home"))
        session["login_failures"] = int(session.get("login_failures", 0)) + 1
        if session["login_failures"] >= 5:
            session["login_block_until"] = time.time() + 60
        flash("Email ou senha invalidos.", "error")
    return render_template("auth/login.html")


@auth_bp.get("/sair")
@login_required
def logout():
    log_action("LOGOUT", "User", current_user.id)
    db.session.commit()
    logout_user()
    session.pop("login_failures", None)
    session.pop("login_block_until", None)
    return redirect(url_for("public.index"))


@auth_bp.route("/recuperar-senha", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        user = User.query.filter(func.lower(User.email) == request.form.get("email", "").strip().lower()).first()
        if user:
            user.reset_token = secrets.token_urlsafe(32)
            user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=1)
            db.session.add(user)
            log_action("PASSWORD_RESET_REQUEST", "User", user.id)
            db.session.commit()
            link = url_for("auth.reset_password", token=user.reset_token, _external=True)
            send_email(user, "Redefinicao de senha - Apex Fitness", f"Acesse para redefinir sua senha: {link}")
            db.session.commit()
        flash("Se o email existir, enviaremos as instrucoes.", "success")
    return render_template("auth/forgot.html")


@auth_bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first_or_404()
    if not user.reset_token_expires_at or user.reset_token_expires_at < datetime.utcnow():
        flash("Token expirado.", "error")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        user.set_password(request.form.get("password"))
        user.reset_token = None
        user.reset_token_expires_at = None
        db.session.add(user)
        log_action("PASSWORD_RESET_DONE", "User", user.id)
        db.session.commit()
        return redirect(url_for("auth.login"))
    return render_template("auth/reset.html")


@auth_bp.post("/token")
def token():
    user = User.query.filter(func.lower(User.email) == request.form.get("email", "").strip().lower()).first()
    if not user or not user.check_password(request.form.get("password", "")):
        return {"error": "invalid_credentials"}, 401
    return {"access_token": create_jwt(user), "role": user.role.value}


# ---- app/dashboard/routes.py ----
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


ACADEMY_MANAGER_ROLES = [
    Role.PROFESSOR,
    Role.RECEPCAO,
    Role.FISIOTERAPEUTA,
    Role.NUTRICIONISTA,
    Role.PERSONAL,
]
STAFF_ROLES = [role for role in Role if role != Role.ALUNO]


@dashboard_bp.get("/")
@login_required
def home():
    role_routes = {
        Role.ALUNO: "aluno.home",
        Role.RECEPCAO: "admin.reception",
        Role.PROFESSOR: "professor.home",
        Role.PERSONAL: "personal.home",
        Role.NUTRICIONISTA: "nutricionista.home",
        Role.FISIOTERAPEUTA: "fisioterapeuta.home",
        Role.ATENDENTE_MERCADO: "mercado.store",
        Role.GERENTE_ACADEMIA: "dashboard.academy_manager",
        Role.GERENTE_MERCADO: "dashboard.store_manager",
        Role.GERENTE_GERAL: "dashboard.general_manager",
        Role.DONO: "dashboard.owner",
    }
    if current_user.role in role_routes:
        return redirect(url_for(role_routes[current_user.role]))
    revenue = sum(Decimal(s.total) for s in Sale.query.all()) if Sale.query.count() else Decimal("0")
    return render_template(
        "dashboard/home.html",
        students=StudentProfile.query.count(),
        active_students=StudentProfile.query.filter_by(account_status="ATIVO").count(),
        delinquent=StudentProfile.query.filter_by(account_status="INADIMPLENTE").count(),
        products=Product.query.count(),
        users=User.query.count(),
        pending=Payment.query.filter_by(status="PENDENTE").count(),
        revenue=revenue,
        low_stock=Product.query.filter(Product.stock <= Product.minimum_stock).all(),
    )


@dashboard_bp.route("/gerente-academia", methods=["GET", "POST"])
@login_required
def academy_manager():
    if current_user.role not in {Role.GERENTE_ACADEMIA, Role.ADMIN}:
        return redirect(url_for("dashboard.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role_name = request.form.get("role")
        if role_name not in {role.name for role in ACADEMY_MANAGER_ROLES}:
            flash("Selecione um cargo profissional valido.", "error")
            return redirect(url_for("dashboard.academy_manager"))
        if User.query.filter_by(email=email).first():
            flash("Email ja cadastrado.", "error")
            return redirect(url_for("dashboard.academy_manager"))
        if not strong_password(password):
            flash("Senha deve ter 8 caracteres, letras e numeros.", "error")
            return redirect(url_for("dashboard.academy_manager"))
        user = User(
            name=request.form.get("name"),
            email=email,
            role=Role[role_name],
            phone=request.form.get("phone"),
            cpf=request.form.get("cpf"),
            rg=request.form.get("rg"),
            address=request.form.get("address"),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        log_action("CREATE", "User", user.id, user.role.value)
        account_created(user, password)
        db.session.commit()
        flash("Perfil profissional criado com login de acesso.", "success")
        return redirect(url_for("dashboard.academy_manager"))
    students = StudentProfile.query.order_by(StudentProfile.created_at.desc()).all()
    delinquent_students = StudentProfile.query.filter_by(account_status="INADIMPLENTE").order_by(StudentProfile.created_at.desc()).all()
    employees = User.query.filter(User.role.in_(STAFF_ROLES)).order_by(User.created_at.desc()).all()
    return render_template(
        "dashboard/academy_manager.html",
        students=students,
        active_students=StudentProfile.query.filter_by(account_status="ATIVO").count(),
        delinquent_students=delinquent_students,
        employees=employees,
        professional_roles=ACADEMY_MANAGER_ROLES,
    )


@dashboard_bp.get("/gerente-loja")
@login_required
def store_manager():
    if current_user.role not in {Role.GERENTE_MERCADO, Role.ADMIN}:
        return redirect(url_for("dashboard.home"))
    revenue = sum(Decimal(s.total) for s in Sale.query.all()) if Sale.query.count() else Decimal("0")
    return render_template(
        "dashboard/store_manager.html",
        products=Product.query.count(),
        low_stock=Product.query.filter(Product.stock <= Product.minimum_stock).all(),
        sales=Sale.query.order_by(Sale.created_at.desc()).all(),
        revenue=revenue,
    )


@dashboard_bp.get("/gerente-geral")
@login_required
def general_manager():
    if current_user.role not in {Role.GERENTE_GERAL, Role.ADMIN}:
        return redirect(url_for("dashboard.home"))
    revenue = sum(Decimal(s.total) for s in Sale.query.all()) if Sale.query.count() else Decimal("0")
    return render_template(
        "dashboard/general_manager.html",
        students=StudentProfile.query.order_by(StudentProfile.created_at.desc()).all(),
        active_students=StudentProfile.query.filter_by(account_status="ATIVO").count(),
        products=Product.query.order_by(Product.name).all(),
        users=User.query.filter(User.role.in_(STAFF_ROLES)).order_by(User.created_at.desc()).all(),
        sales=Sale.query.order_by(Sale.created_at.desc()).all(),
        pending=Payment.query.filter_by(status="PENDENTE").count(),
        revenue=revenue,
    )


@dashboard_bp.get("/dono")
@login_required
def owner():
    if current_user.role not in {Role.DONO, Role.ADMIN}:
        return redirect(url_for("dashboard.home"))
    revenue = sum(Decimal(s.total) for s in Sale.query.all()) if Sale.query.count() else Decimal("0")
    return render_template(
        "dashboard/owner.html",
        students=StudentProfile.query.order_by(StudentProfile.created_at.desc()).all(),
        products=Product.query.count(),
        users=User.query.filter(User.role.in_(STAFF_ROLES)).order_by(User.created_at.desc()).all(),
        sales=Sale.query.order_by(Sale.created_at.desc()).all(),
        pending=Payment.query.filter_by(status="PENDENTE").count(),
        revenue=revenue,
        low_stock=Product.query.filter(Product.stock <= Product.minimum_stock).all(),
    )


# ---- app/admin/routes.py ----
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/")
@roles_required("DONO", "GERENTE_GERAL", "ADMIN")
def home():
    return render_template("admin/home.html")


@admin_bp.route("/configuracoes-email", methods=["GET", "POST"])
@roles_required("DONO", "GERENTE_GERAL", "ADMIN")
def email_settings():
    if request.method == "POST":
        password = request.form.get("mail_password", "")
        current_password = setting_value("MAIL_PASSWORD", current_app.config.get("MAIL_PASSWORD", ""))
        values = {
            "MAIL_SERVER": request.form.get("mail_server", "").strip(),
            "MAIL_PORT": request.form.get("mail_port", "587").strip(),
            "MAIL_USE_TLS": "true" if request.form.get("mail_use_tls") else "false",
            "MAIL_USERNAME": request.form.get("mail_username", "").strip(),
            "MAIL_PASSWORD": password if password else current_password,
            "MAIL_DEFAULT_SENDER": request.form.get("mail_default_sender", "").strip(),
        }
        for key, value in values.items():
            set_setting(key, value)
        db.session.flush()
        apply_mail_settings(current_app)
        log_action("UPDATE", "AppSetting", "smtp")
        db.session.commit()
        if request.form.get("test_email"):
            recipient = request.form.get("test_email").strip()
            try:
                mail.send(Message(subject="Teste SMTP - Apex Fitness", recipients=[recipient], body="SMTP configurado com sucesso no Apex Fitness."))
                flash("Configuracao salva e email de teste enviado.", "success")
            except Exception as exc:
                flash(f"Configuracao salva, mas o teste falhou: {exc}", "error")
        else:
            flash("Configuracao de email salva.", "success")
        return redirect(url_for("admin.email_settings"))
    smtp = {
        "mail_server": current_app.config.get("MAIL_SERVER", ""),
        "mail_port": current_app.config.get("MAIL_PORT", 587),
        "mail_use_tls": current_app.config.get("MAIL_USE_TLS", True),
        "mail_username": current_app.config.get("MAIL_USERNAME", ""),
        "mail_default_sender": current_app.config.get("MAIL_DEFAULT_SENDER", ""),
        "has_password": bool(current_app.config.get("MAIL_PASSWORD")),
    }
    return render_template("admin/email_settings.html", smtp=smtp)


@admin_bp.route("/planos", methods=["GET", "POST"])
@roles_required("DONO", "GERENTE_GERAL", "ADMIN")
def plans_admin():
    if request.method == "POST":
        plan = Plan(
            name=request.form.get("name", "").strip(),
            description=request.form.get("description", "").strip(),
            monthly_price=request.form.get("monthly_price") or 0,
            quarterly_price=request.form.get("quarterly_price") or 0,
            annual_price=request.form.get("annual_price") or 0,
            benefits=request.form.get("benefits", "").strip(),
            is_active=bool(request.form.get("is_active")),
        )
        db.session.add(plan)
        db.session.flush()
        log_action("CREATE", "Plan", plan.id)
        db.session.commit()
        flash("Plano cadastrado.", "success")
        return redirect(url_for("admin.plans_admin"))
    return render_template("admin/plans.html", plans=Plan.query.order_by(Plan.created_at.desc()).all())


@admin_bp.post("/planos/<int:plan_id>/editar")
@roles_required("DONO", "GERENTE_GERAL", "ADMIN")
def edit_plan(plan_id):
    plan = db.session.get(Plan, plan_id) or abort(404)
    plan.name = request.form.get("name", "").strip()
    plan.description = request.form.get("description", "").strip()
    plan.monthly_price = request.form.get("monthly_price") or 0
    plan.quarterly_price = request.form.get("quarterly_price") or 0
    plan.annual_price = request.form.get("annual_price") or 0
    plan.benefits = request.form.get("benefits", "").strip()
    plan.is_active = bool(request.form.get("is_active"))
    log_action("UPDATE", "Plan", plan.id)
    db.session.commit()
    flash("Plano atualizado.", "success")
    return redirect(url_for("admin.plans_admin"))


@admin_bp.post("/planos/<int:plan_id>/excluir")
@roles_required("DONO", "GERENTE_GERAL", "ADMIN")
def delete_plan(plan_id):
    plan = db.session.get(Plan, plan_id) or abort(404)
    plan.is_active = False
    log_action("DELETE", "Plan", plan.id, "desativado")
    db.session.commit()
    flash("Plano removido do catalogo.", "success")
    return redirect(url_for("admin.plans_admin"))


@admin_bp.route("/servicos", methods=["GET", "POST"])
@roles_required("DONO", "GERENTE_GERAL", "ADMIN", "GERENTE_ACADEMIA")
def services_admin():
    if request.method == "POST":
        service = Service(
            name=request.form.get("name", "").strip(),
            category=request.form.get("category", "").strip(),
            description=request.form.get("description", "").strip(),
            price=request.form.get("price") or 0,
            image_url=request.form.get("image_url", "").strip(),
            professional_role=Role[request.form.get("professional_role")] if request.form.get("professional_role") else None,
            is_active=bool(request.form.get("is_active")),
        )
        db.session.add(service)
        db.session.flush()
        log_action("CREATE", "Service", service.id)
        db.session.commit()
        flash("Servico cadastrado.", "success")
        return redirect(url_for("admin.services_admin"))
    professional_roles = [Role.PERSONAL, Role.NUTRICIONISTA, Role.FISIOTERAPEUTA, Role.PROFESSOR]
    return render_template("admin/services.html", services=Service.query.order_by(Service.created_at.desc()).all(), professional_roles=professional_roles)


@admin_bp.post("/servicos/<int:service_id>/editar")
@roles_required("DONO", "GERENTE_GERAL", "ADMIN", "GERENTE_ACADEMIA")
def edit_service(service_id):
    service = db.session.get(Service, service_id) or abort(404)
    service.name = request.form.get("name", "").strip()
    service.category = request.form.get("category", "").strip()
    service.description = request.form.get("description", "").strip()
    service.price = request.form.get("price") or 0
    service.image_url = request.form.get("image_url", "").strip()
    service.professional_role = Role[request.form.get("professional_role")] if request.form.get("professional_role") else None
    service.is_active = bool(request.form.get("is_active"))
    log_action("UPDATE", "Service", service.id)
    db.session.commit()
    flash("Servico atualizado.", "success")
    return redirect(url_for("admin.services_admin"))


@admin_bp.post("/servicos/<int:service_id>/excluir")
@roles_required("DONO", "GERENTE_GERAL", "ADMIN", "GERENTE_ACADEMIA")
def delete_service(service_id):
    service = db.session.get(Service, service_id) or abort(404)
    service.is_active = False
    log_action("DELETE", "Service", service.id, "desativado")
    db.session.commit()
    flash("Servico removido do catalogo.", "success")
    return redirect(url_for("admin.services_admin"))


@admin_bp.route("/recepcao", methods=["GET", "POST"])
@roles_required("RECEPCAO", "ADMIN", "DONO", "GERENTE_GERAL", "GERENTE_ACADEMIA")
def reception():
    q = request.args.get("q", "").strip()
    students_query = StudentProfile.query.join(User, StudentProfile.user_id == User.id)
    if q:
        students_query = students_query.filter(or_(User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"), User.cpf.ilike(f"%{q}%")))
    students = students_query.order_by(StudentProfile.created_at.desc()).limit(80).all()
    pending_payments = Payment.query.filter_by(status="PENDENTE").order_by(Payment.created_at.desc()).all()
    service_requests = ServiceRequest.query.filter_by(status="PENDENTE").order_by(ServiceRequest.created_at.desc()).all()
    today = datetime.utcnow().date()
    return render_template("admin/reception.html", students=students, pending_payments=pending_payments, service_requests=service_requests, today=today, q=q)


@admin_bp.post("/alunos/<int:profile_id>/autorizar")
@roles_required("RECEPCAO", "ADMIN", "DONO", "GERENTE_GERAL", "GERENTE_ACADEMIA")
def authorize_student(profile_id):
    profile = db.session.get(StudentProfile, profile_id) or abort(404)
    for payment in Payment.query.filter_by(student_id=profile.id, status="PENDENTE").all():
        confirm_payment(payment, request.form.get("method"))
    if not Payment.query.filter_by(student_id=profile.id, status="PENDENTE").first():
        profile.account_status = "ATIVO"
        profile.next_payment_at = next_due_date(profile.billing_cycle)
    log_action("AUTHORIZE_ACCESS", "StudentProfile", profile.id)
    db.session.commit()
    flash("Aluno autorizado. A entrada pela academia foi liberada.", "success")
    return redirect(url_for("admin.reception"))


@admin_bp.post("/pagamentos/<int:payment_id>/confirmar")
@roles_required("RECEPCAO", "ADMIN", "DONO", "GERENTE_GERAL", "GERENTE_ACADEMIA")
def confirm_pending_payment(payment_id):
    payment = db.session.get(Payment, payment_id) or abort(404)
    confirm_payment(payment, request.form.get("method"))
    log_action("CONFIRM_PAYMENT", "Payment", payment.id)
    db.session.commit()
    flash("Pagamento confirmado.", "success")
    return redirect(url_for("admin.reception"))


@admin_bp.post("/pagamentos/<int:payment_id>/recusar")
@roles_required("RECEPCAO", "ADMIN", "DONO", "GERENTE_GERAL", "GERENTE_ACADEMIA")
def reject_pending_payment(payment_id):
    payment = db.session.get(Payment, payment_id) or abort(404)
    reject_payment(payment)
    log_action("REJECT_PAYMENT", "Payment", payment.id)
    db.session.commit()
    flash("Pagamento recusado.", "success")
    return redirect(url_for("admin.reception"))


@admin_bp.route("/alunos/novo", methods=["GET", "POST"])
@roles_required("RECEPCAO", "ADMIN", "DONO", "GERENTE_GERAL", "GERENTE_ACADEMIA")
def create_student():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        cpf = request.form.get("cpf", "")
        phone = request.form.get("phone", "")
        password = request.form.get("password", "")
        if User.query.filter_by(email=email).first():
            flash("Email ja cadastrado.", "error")
        elif cpf and not validate_cpf(cpf):
            flash("CPF invalido.", "error")
        elif phone and not validate_phone(phone):
            flash("Telefone invalido.", "error")
        elif not strong_password(password):
            flash("Senha deve ter 8 caracteres, letras e numeros.", "error")
        else:
            user = User(name=request.form.get("name"), email=email, cpf=cpf, rg=request.form.get("rg"), phone=phone, address=request.form.get("address"), role=Role.ALUNO)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            profile = StudentProfile(
                user_id=user.id,
                sex=request.form.get("sex"),
                age=int(request.form.get("age") or 0),
                plan_id=request.form.get("plan_id"),
                billing_cycle=request.form.get("billing_cycle"),
                personal_id=request.form.get("personal_id") or None,
                nutritionist_id=request.form.get("nutritionist_id") or None,
                physiotherapist_id=request.form.get("physiotherapist_id") or None,
            )
            for service_id in request.form.getlist("service_ids"):
                service = db.session.get(Service, int(service_id))
                if service:
                    profile.services.append(service)
            db.session.add(profile)
            db.session.flush()
            log_action("CREATE", "StudentProfile", profile.id)
            account_created(user, password)
            db.session.commit()
            flash("Aluno cadastrado e email enviado/simulado.", "success")
            return redirect(url_for("admin.reception"))
    professionals = User.query.filter(User.role.in_([Role.PERSONAL, Role.NUTRICIONISTA, Role.FISIOTERAPEUTA])).all()
    return render_template("admin/create_student.html", plans=Plan.query.all(), services=Service.query.all(), professionals=professionals)


@admin_bp.route("/usuarios", methods=["GET", "POST"])
@roles_required("DONO", "GERENTE_GERAL", "ADMIN")
def users():
    if request.method == "POST":
        role = Role[request.form.get("role")]
        user = User(name=request.form.get("name"), email=request.form.get("email").strip().lower(), role=role, phone=request.form.get("phone"), cpf=request.form.get("cpf"), rg=request.form.get("rg"), address=request.form.get("address"))
        user.set_password(request.form.get("password"))
        db.session.add(user)
        db.session.flush()
        log_action("CREATE", "User", user.id, role.value)
        account_created(user, request.form.get("password"))
        db.session.commit()
        return redirect(url_for("admin.users"))
    return render_template("admin/users.html", users=User.query.order_by(User.created_at.desc()).all(), roles=Role)


@admin_bp.route("/produtos", methods=["GET", "POST"])
@roles_required("DONO", "GERENTE_MERCADO", "ADMIN")
def products():
    if request.method == "POST":
        product = Product(name=request.form.get("name"), category=request.form.get("category"), description=request.form.get("description"), price=request.form.get("price"), stock=int(request.form.get("stock") or 0), minimum_stock=int(request.form.get("minimum_stock") or 5), image_url=request.form.get("image_url"), is_active=bool(request.form.get("is_active")))
        db.session.add(product)
        db.session.flush()
        log_action("CREATE", "Product", product.id)
        db.session.commit()
        return redirect(url_for("admin.products"))
    return render_template("admin/products.html", products=Product.query.order_by(Product.name).all())


@admin_bp.post("/produtos/<int:product_id>/editar")
@roles_required("DONO", "GERENTE_MERCADO", "ADMIN")
def edit_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    product.name = request.form.get("name")
    product.category = request.form.get("category")
    product.description = request.form.get("description")
    product.price = request.form.get("price") or 0
    product.stock = int(request.form.get("stock") or 0)
    product.minimum_stock = int(request.form.get("minimum_stock") or 5)
    product.image_url = request.form.get("image_url")
    product.is_active = bool(request.form.get("is_active"))
    log_action("UPDATE", "Product", product.id)
    db.session.commit()
    flash("Produto atualizado.", "success")
    return redirect(url_for("admin.products"))


@admin_bp.post("/produtos/<int:product_id>/excluir")
@roles_required("DONO", "GERENTE_MERCADO", "ADMIN")
def delete_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    product.is_active = False
    log_action("DELETE", "Product", product.id, "desativado")
    db.session.commit()
    flash("Produto removido do catalogo.", "success")
    return redirect(url_for("admin.products"))


@admin_bp.post("/produtos/movimento")
@roles_required("DONO", "GERENTE_MERCADO", "ADMIN")
def product_movement():
    product = db.session.get(Product, int(request.form.get("product_id")))
    quantity = int(request.form.get("quantity") or 0)
    movement_type = request.form.get("movement_type")
    product.stock += quantity if movement_type == "ENTRADA" else -quantity
    movement = StockMovement(product_id=product.id, movement_type=movement_type, quantity=quantity, unit_value=request.form.get("unit_value") or 0, user_id=current_user.id)
    db.session.add(movement)
    db.session.flush()
    log_action("STOCK_MOVEMENT", "StockMovement", movement.id)
    db.session.commit()
    return redirect(url_for("admin.products"))


@admin_bp.get("/logs")
@roles_required("DONO", "GERENTE_GERAL", "ADMIN")
def logs():
    return render_template("admin/logs.html", logs=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(250).all())


@admin_bp.get("/relatorios/<kind>")
@roles_required("DONO", "GERENTE_GERAL", "ADMIN", "GERENTE_MERCADO", "GERENTE_ACADEMIA")
def reports(kind):
    sources = {
        "financeiro": [f"Pagamento {p.id} | {p.status} | R$ {p.amount}" for p in Payment.query.all()],
        "estoque": [f"{p.name} | {p.category} | estoque {p.stock}" for p in Product.query.order_by(Product.name).all()],
        "alunos": [f"{s.user.name} | {s.account_status} | {s.plan.name if s.plan else '-'}" for s in StudentProfile.query.all()],
        "inadimplentes": [f"{s.user.name} | proximo pagamento {s.next_payment_at}" for s in StudentProfile.query.filter_by(account_status="INADIMPLENTE").all()],
        "funcionarios": [f"{u.name} | {u.email} | {u.role.value}" for u in User.query.filter(User.role != Role.ALUNO).order_by(User.name).all()],
        "profissionais": [f"{u.name} | {u.email} | {u.role.value}" for u in User.query.filter(User.role != Role.ALUNO).order_by(User.name).all()],
        "vendas": [f"Venda {s.id} | {s.student.user.name if s.student else '-'} | {s.payment_method} | {s.payment_status} | R$ {s.total}" for s in Sale.query.order_by(Sale.created_at.desc()).all()],
        "logs": [f"{l.created_at} | {l.action} | {l.entity} | {l.ip_address}" for l in AuditLog.query.order_by(AuditLog.created_at.desc()).limit(500).all()],
    }
    path = generate_pdf(f"Relatorio {kind}", sources.get(kind, ["Sem dados."]), f"relatorio_{kind}")
    log_action("REPORT_PDF", "PdfDocument", kind, path)
    db.session.commit()
    flash(f"Relatorio gerado: {path}", "success")
    return redirect(url_for("dashboard.home"))


# ---- app/aluno/routes.py ----
aluno_bp = Blueprint("aluno", __name__, url_prefix="/aluno")


@aluno_bp.get("/")
@roles_required("ALUNO")
def home():
    return render_template("aluno/home.html", profile=current_user.student_profile)


@aluno_bp.get("/minha-conta")
@login_required
def account():
    profile = current_user.student_profile
    payments = Payment.query.filter_by(student_id=profile.id).order_by(Payment.due_date.desc()).all() if profile else []
    return render_template("aluno/account.html", user=current_user, profile=profile, payments=payments)


@aluno_bp.get("/treinos")
@roles_required("ALUNO")
def trainings():
    query = TrainingPlan.query
    if not admin_user():
        query = query.filter_by(student_id=current_user.student_profile.id)
    return render_template("aluno/trainings.html", trainings=query.all())


@aluno_bp.get("/treinos/<int:training_id>/pdf")
@roles_required("ALUNO")
def training_pdf(training_id):
    training = db.session.get(TrainingPlan, training_id)
    if not training or (not admin_user() and training.student_id != current_user.student_profile.id) or not training.pdf_path:
        abort(404)
    if not os.path.exists(training.pdf_path):
        flash("PDF do treino nao encontrado.", "error")
        return redirect(url_for("aluno.trainings"))
    return send_file(training.pdf_path, as_attachment=request.args.get("download") == "1", download_name=f"{training.title}.pdf")


@aluno_bp.post("/treinos/<int:training_id>/excluir")
@roles_required("ALUNO")
def delete_training(training_id):
    training = db.session.get(TrainingPlan, training_id)
    if not training or (not admin_user() and training.student_id != current_user.student_profile.id):
        abort(404)

    pdf_path = training.pdf_path
    db.session.delete(training)
    log_action("DELETE", "TrainingPlan", training_id)
    db.session.commit()

    if pdf_path and os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError:
            pass

    flash("Treino excluido com sucesso.", "success")
    return redirect(url_for("aluno.trainings"))


@aluno_bp.get("/plano-alimentar")
@roles_required("ALUNO")
def food():
    query = FoodPlan.query
    if not admin_user():
        query = query.filter_by(student_id=current_user.student_profile.id)
    return render_template("aluno/food.html", plans=query.all())


@aluno_bp.get("/plano-alimentar/<int:plan_id>/pdf")
@roles_required("ALUNO")
def food_pdf(plan_id):
    plan = db.session.get(FoodPlan, plan_id)
    if not plan or (not admin_user() and plan.student_id != current_user.student_profile.id) or not plan.pdf_path:
        abort(404)
    if not os.path.exists(plan.pdf_path):
        flash("PDF do plano alimentar nao encontrado.", "error")
        return redirect(url_for("aluno.food"))
    return send_file(plan.pdf_path, as_attachment=request.args.get("download") == "1", download_name=f"{plan.title}.pdf")


@aluno_bp.post("/plano-alimentar/<int:plan_id>/excluir")
@roles_required("ALUNO")
def delete_food(plan_id):
    plan = db.session.get(FoodPlan, plan_id)
    if not plan or (not admin_user() and plan.student_id != current_user.student_profile.id):
        abort(404)

    pdf_path = plan.pdf_path
    db.session.delete(plan)
    log_action("DELETE", "FoodPlan", plan_id)
    db.session.commit()

    if pdf_path and os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError:
            pass

    flash("Plano alimentar excluido com sucesso.", "success")
    return redirect(url_for("aluno.food"))


@aluno_bp.get("/fisioterapia")
@roles_required("ALUNO")
def physiotherapy_documents():
    query = PdfDocument.query.filter_by(document_type="fisioterapia")
    if not admin_user():
        query = query.filter_by(owner_id=current_user.id)
    documents = query.order_by(PdfDocument.created_at.desc()).all()
    return render_template("aluno/physiotherapy.html", documents=documents)


@aluno_bp.get("/fisioterapia/<int:document_id>/pdf")
@roles_required("ALUNO")
def physiotherapy_pdf(document_id):
    document = db.session.get(PdfDocument, document_id)
    if not document or (not admin_user() and document.owner_id != current_user.id) or document.document_type != "fisioterapia":
        abort(404)
    if not os.path.exists(document.path):
        flash("PDF da fisioterapia nao encontrado.", "error")
        return redirect(url_for("aluno.physiotherapy_documents"))
    return send_file(document.path, as_attachment=request.args.get("download") == "1", download_name=f"{document.title}.pdf")


@aluno_bp.get("/servicos")
@roles_required("ALUNO")
def services():
    profile = current_user.student_profile
    available_services = Service.query.filter_by(is_active=True).order_by(Service.category, Service.name).all()
    requests = ServiceRequest.query.filter_by(student_id=profile.id).order_by(ServiceRequest.created_at.desc()).all() if profile else []
    return render_template("aluno/services.html", profile=profile, available_services=available_services, requests=requests)


@aluno_bp.post("/servicos/<int:service_id>/solicitar")
@roles_required("ALUNO")
def request_service(service_id):
    profile = current_user.student_profile
    service = db.session.get(Service, service_id) or abort(404)
    if not profile:
        flash("Admin pode visualizar esta pagina, mas solicitacao de servico exige um aluno.", "error")
        return redirect(url_for("aluno.services"))
    if not service.is_active:
        abort(404)
    if service in profile.services:
        flash("Voce ja possui esse servico ativo.", "success")
        return redirect(url_for("aluno.services"))
    pending = ServiceRequest.query.filter_by(student_id=profile.id, service_id=service.id, status="PENDENTE").first()
    if pending:
        flash("Esse servico ja esta aguardando confirmacao da recepcao.", "success")
        return redirect(url_for("aluno.services"))
    payment = Payment(student_id=profile.id, amount=service.price, method="RECEPCAO", status="PENDENTE", due_date=datetime.utcnow().date())
    db.session.add(payment)
    db.session.flush()
    db.session.add(ServiceRequest(student_id=profile.id, service_id=service.id, payment_id=payment.id, status="PENDENTE"))
    log_action("REQUEST_SERVICE", "Service", service.id)
    db.session.commit()
    flash("Servico solicitado. Passe na recepcao para confirmar pagamento e ativar.", "success")
    return redirect(url_for("aluno.services"))


@aluno_bp.get("/produtos")
@roles_required("ALUNO")
def products():
    return render_template("public/products.html", products=Product.query.filter_by(is_active=True).all())


@aluno_bp.route("/checkin", methods=["GET", "POST"])
@roles_required("ALUNO")
def checkin():
    profile = current_user.student_profile
    if not profile or profile.account_status != "ATIVO":
        flash("Check-in bloqueado. Confirme seu cadastro e pagamento na recepcao.", "error")
        checks = CheckIn.query.filter_by(student_id=profile.id).order_by(CheckIn.entry_at.desc()).all() if profile else []
        return render_template("aluno/checkin.html", checks=checks)
    if request.method == "POST" and current_user.is_authenticated and profile and hasattr(current_user, "id"):
        active = CheckIn.query.filter_by(student_id=profile.id, exit_at=None).first()
        if active:
            active.exit_at = datetime.utcnow()
            log_action("CHECKOUT", "CheckIn", active.id)
        else:
            check = CheckIn(student_id=profile.id, qr_code=generate_qr(f"APEX-CHECKIN:{profile.id}", "checkin"))
            db.session.add(check)
            db.session.flush()
            log_action("CHECKIN", "CheckIn", check.id)
        db.session.commit()
        return redirect(url_for("aluno.checkin"))
    return render_template("aluno/checkin.html", checks=CheckIn.query.filter_by(student_id=profile.id).order_by(CheckIn.entry_at.desc()).all())


@aluno_bp.get("/financeiro")
@roles_required("ALUNO")
def finance_history():
    profile = current_user.student_profile
    payments = Payment.query
    requests = ServiceRequest.query
    if not admin_user():
        payments = payments.filter_by(student_id=profile.id)
        requests = requests.filter_by(student_id=profile.id)
    return render_template("aluno/finance.html", payments=payments.order_by(Payment.due_date.desc()).all(), requests=requests.order_by(ServiceRequest.created_at.desc()).all())


# ---- app/professor/routes.py ----
professor_bp = Blueprint("professor", __name__, url_prefix="/professor")


@professor_bp.get("/")
@roles_required("PROFESSOR")
def home():
    return render_template("professor/home.html")


@professor_bp.route("/treinos/criar", methods=["GET", "POST"])
@roles_required("PROFESSOR", "PERSONAL")
def create_training():
    if request.method == "POST":
        student_id = request.form.get("student_id")
        title = request.form.get("title", "").strip()
        exercises = request.form.get("exercises", "").strip()
        if not student_id:
            flash("Selecione um aluno para enviar o treino.", "error")
            return redirect(url_for("professor.create_training"))
        if not title or not exercises:
            flash("Preencha o titulo e os exercicios antes de enviar.", "error")
            return redirect(url_for("professor.create_training"))
        student = db.session.get(StudentProfile, int(student_id))
        if not student:
            flash("Aluno nao encontrado.", "error")
            return redirect(url_for("professor.create_training"))
        pdf = generate_pdf(title, exercises.splitlines(), "treino")
        plan = TrainingPlan(student_id=student.id, author_id=current_user.id, base_type=request.form.get("base_type"), title=title, exercises=exercises, observations=request.form.get("observations"), pdf_path=pdf)
        db.session.add(plan)
        db.session.add(Notification(user_id=student.user_id, title="Novo treino", message=f"Seu treino {title} foi publicado."))
        db.session.flush()
        log_action("CREATE", "TrainingPlan", plan.id)
        send_email(student.user, "Novo treino - Apex Fitness", f"Seu treino {title} esta disponivel.")
        db.session.commit()
        flash("Treino gerado em PDF e enviado para o aluno.", "success")
        return redirect(url_for("professor.create_training"))
    return render_template("professor/create_training.html", students=StudentProfile.query.all())


# ---- app/personal/routes.py ----
personal_bp = Blueprint("personal", __name__, url_prefix="/personal")


@personal_bp.get("/")
@roles_required("PERSONAL")
def home():
    query = StudentProfile.query
    if not admin_user():
        query = query.filter_by(personal_id=current_user.id)
    return render_template("personal/home.html", students=query.all())


# ---- app/nutricionista/routes.py ----
nutricionista_bp = Blueprint("nutricionista", __name__, url_prefix="/nutricionista")


@nutricionista_bp.route("/", methods=["GET", "POST"])
@roles_required("NUTRICIONISTA")
def home():
    students = StudentProfile.query.all() if admin_user() else StudentProfile.query.filter_by(nutritionist_id=current_user.id).all()
    if request.method == "POST":
        student_id = request.form.get("student_id")
        title = request.form.get("title", "").strip()
        meals = request.form.get("meals", "").strip()
        if not student_id:
            flash("Selecione um aluno para enviar o plano alimentar.", "error")
            return redirect(url_for("nutricionista.home"))
        if not title or not meals:
            flash("Preencha o titulo e as refeicoes antes de enviar.", "error")
            return redirect(url_for("nutricionista.home"))
        student = db.session.get(StudentProfile, int(student_id))
        if not student:
            flash("Aluno nao encontrado.", "error")
            return redirect(url_for("nutricionista.home"))
        pdf = generate_pdf(title, meals.splitlines(), "plano_alimentar")
        plan = FoodPlan(student_id=student.id, nutritionist_id=current_user.id, title=title, meals=meals, schedules=request.form.get("schedules"), observations=request.form.get("observations"), pdf_path=pdf)
        db.session.add(plan)
        db.session.add(Notification(user_id=student.user_id, title="Novo plano alimentar", message=f"Seu plano {title} foi publicado."))
        db.session.flush()
        log_action("CREATE", "FoodPlan", plan.id)
        send_email(student.user, "Novo plano alimentar - Apex Fitness", f"Seu plano {title} esta disponivel.")
        db.session.commit()
        flash("Plano alimentar gerado em PDF e enviado para o aluno.", "success")
        return redirect(url_for("nutricionista.home"))
    return render_template("nutricionista/home.html", students=students)


# ---- app/fisioterapeuta/routes.py ----
fisioterapeuta_bp = Blueprint("fisioterapeuta", __name__, url_prefix="/fisioterapeuta")


@fisioterapeuta_bp.route("/", methods=["GET", "POST"])
@roles_required("FISIOTERAPEUTA")
def home():
    students = StudentProfile.query.all() if admin_user() else StudentProfile.query.filter_by(physiotherapist_id=current_user.id).all()
    if request.method == "POST":
        student_id = request.form.get("student_id")
        if not student_id:
            flash("Selecione um aluno antes de gerar o PDF.", "error")
            return redirect(url_for("fisioterapeuta.home"))
        student = db.session.get(StudentProfile, int(student_id))
        observations = request.form.get("observations", "").strip()
        if not student:
            flash("Aluno nao encontrado.", "error")
            return redirect(url_for("fisioterapeuta.home"))
        pdf = generate_pdf("Plano de reabilitacao", observations.splitlines(), "reabilitacao")
        document = PdfDocument(owner_id=student.user_id, document_type="fisioterapia", path=pdf, title="Plano de reabilitacao")
        db.session.add(document)
        db.session.add(Notification(user_id=student.user_id, title="Novo PDF da fisioterapia", message="Seu plano de reabilitacao esta disponivel."))
        db.session.flush()
        log_action("CREATE", "PdfDocument", document.id)
        db.session.commit()
        flash("Plano de recuperacao gerado e enviado ao aluno.", "success")
        return redirect(url_for("fisioterapeuta.home"))
    return render_template("fisioterapeuta/home.html", students=students)


# ---- app/mercado/routes.py ----
mercado_bp = Blueprint("mercado", __name__, url_prefix="/mercado")


def cart_items():
    cart = session.get("cart", {})
    items, total = [], Decimal("0")
    for product_id, qty in cart.items():
        product = db.session.get(Product, int(product_id))
        if product:
            quantity = int(qty)
            subtotal = Decimal(product.price) * quantity
            total += subtotal
            items.append({"product": product, "quantity": quantity, "subtotal": subtotal})
    return items, total


@mercado_bp.route("/", methods=["GET", "POST"])
@roles_required("ATENDENTE_MERCADO", "GERENTE_MERCADO", "ADMIN")
def store():
    if request.method == "POST":
        session["sale_student_id"] = int(request.form.get("student_id")) if request.form.get("student_id") else None
        session["cart"] = {}
        return redirect(url_for("mercado.store"))
    selected = db.session.get(StudentProfile, session.get("sale_student_id")) if session.get("sale_student_id") else None
    items, total = cart_items()
    return render_template("mercado/store.html", students=StudentProfile.query.all(), selected=selected, products=Product.query.filter_by(is_active=True).all(), items=items, total=total)


@mercado_bp.post("/adicionar/<int:product_id>")
@roles_required("ATENDENTE_MERCADO", "GERENTE_MERCADO", "ADMIN")
def add(product_id):
    if not session.get("sale_student_id"):
        flash("Selecione um aluno cadastrado antes de vender.", "error")
        return redirect(url_for("mercado.store"))
    product = db.session.get(Product, product_id)
    quantity = int(request.form.get("quantity") or 1)
    cart = session.get("cart", {})
    if not product or product.stock < quantity + int(cart.get(str(product_id), 0)):
        flash("Estoque insuficiente.", "error")
    else:
        cart[str(product_id)] = int(cart.get(str(product_id), 0)) + quantity
        session["cart"] = cart
    return redirect(url_for("mercado.store"))


@mercado_bp.get("/remover/<int:product_id>")
@roles_required("ATENDENTE_MERCADO", "GERENTE_MERCADO", "ADMIN")
def remove(product_id):
    cart = session.get("cart", {})
    cart.pop(str(product_id), None)
    session["cart"] = cart
    return redirect(url_for("mercado.store"))


@mercado_bp.post("/finalizar")
@roles_required("ATENDENTE_MERCADO", "GERENTE_MERCADO", "ADMIN")
def checkout():
    student = db.session.get(StudentProfile, session.get("sale_student_id"))
    items, total = cart_items()
    if not student or not items:
        flash("Selecione aluno e produtos.", "error")
        return redirect(url_for("mercado.store"))
    method = request.form.get("payment_method")
    pix_key, pix_qr = pix_payload(total, "Venda Apex Fitness") if method == "PIX" else (None, None)
    sale = Sale(user_id=current_user.id, student_id=student.id, payment_method=method, payment_status=request.form.get("payment_status") or "PAGO", total=total, pix_key=pix_key, pix_qr_path=pix_qr, card_authorization=request.form.get("card_authorization"))
    db.session.add(sale)
    db.session.flush()
    lines = [f"Aluno: {student.user.name}", f"Operador: {current_user.name}", f"Pagamento: {method}", f"Status: {sale.payment_status}"]
    for item in items:
        product = item["product"]
        product.stock -= item["quantity"]
        db.session.add(SaleItem(sale_id=sale.id, product_id=product.id, quantity=item["quantity"], unit_price=product.price, subtotal=item["subtotal"]))
        db.session.add(StockMovement(product_id=product.id, movement_type="SAIDA", quantity=item["quantity"], unit_value=product.price, user_id=current_user.id))
        lines.append(f"{product.name} x{item['quantity']} - {money(item['subtotal'])}")
        if product.stock <= product.minimum_stock:
            for admin in User.query.filter(User.role.in_([Role.ADMIN, Role.DONO, Role.GERENTE_MERCADO])):
                send_email(admin, "Estoque baixo", f"{product.name} esta com {product.stock} unidades.")
    lines += [f"Total: {money(total)}", f"PIX: {pix_key or '-'}"]
    sale.receipt_pdf_path = generate_pdf("Comprovante Apex Fitness", lines, "venda")
    send_email(student.user, "Pagamento aprovado - Apex Fitness", f"Sua compra foi registrada.\nTotal: {money(total)}")
    log_action("CREATE", "Sale", sale.id, f"Total {total}")
    db.session.commit()
    session["cart"] = {}
    session.pop("sale_student_id", None)
    return render_template("mercado/receipt.html", sale=sale)


# ---- app/financeiro/routes.py ----
financeiro_bp = Blueprint("financeiro", __name__, url_prefix="/financeiro")


@financeiro_bp.get("/")
@roles_required("DONO", "GERENTE_GERAL", "ADMIN")
def home():
    revenue = sum(Decimal(p.amount) for p in Payment.query.filter_by(status="PAGO").all()) + sum(Decimal(s.total) for s in Sale.query.all())
    expenses = revenue * Decimal("0.35")
    profit = revenue - expenses
    return render_template("financeiro/home.html", revenue=revenue, expenses=expenses, profit=profit, students=StudentProfile.query.count(), delinquent=StudentProfile.query.filter_by(account_status="INADIMPLENTE").count())


# ---- app/routes/api.py ----
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


@api_bp.get("/health")
def health():
    return {"status": "ok", "service": "Apex Fitness"}


@api_bp.get("/catalogo")
def catalog():
    return {
        "plans": [{"id": p.id, "name": p.name, "monthly_price": float(p.monthly_price)} for p in Plan.query.filter_by(is_active=True)],
        "services": [{"id": s.id, "name": s.name, "price": float(s.price)} for s in Service.query.filter_by(is_active=True)],
        "products": [{"id": p.id, "name": p.name, "price": float(p.price), "stock": p.stock} for p in Product.query.filter_by(is_active=True)],
    }


@api_bp.get("/me")
@jwt_required
def me():
    user = db.session.get(User, int(request.jwt_payload["sub"]))
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role.value}


def create_app(config_class=None):
    config_class = config_class or (DevConfig if os.getenv("APEX_DEV", "true").lower() == "true" else Config)
    app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    mail.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    for bp in [
        public_bp,
        auth_bp,
        dashboard_bp,
        admin_bp,
        aluno_bp,
        professor_bp,
        personal_bp,
        nutricionista_bp,
        fisioterapeuta_bp,
        mercado_bp,
        financeiro_bp,
        api_bp,
    ]:
        app.register_blueprint(bp)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.after_request
    def secure_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: https://images.unsplash.com https://unsplash.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none';"
        )
        return response

    with app.app_context():
        db.create_all()
        apply_mail_settings(app)
        seed_database()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "5002")), debug=False)
