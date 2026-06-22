import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-in-production")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-jwt-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///apexfitness.db",
    )
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
    ACADEMY_PHONE = "+55 (83) 98689-2601"
    ACADEMY_EMAIL = "apexfitness@gmail.com"
    ACADEMY_ADDRESS = "Av. Joao Cancio da Silva, 1240 - Manaira, Joao Pessoa - PB"
    PAYMENT_OWNER = "Victor Lucas Pedroza de Andrade"
    PAYMENT_CPF = "715.313.634-74"
    PAYMENT_BANK = "Mercado Pago"
    PAYMENT_AGENCY = "0001"
    PAYMENT_ACCOUNT = "23332177265"


class DevConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv("DEV_DATABASE_URL", "sqlite:///apexfitness_dev.db")
    WTF_CSRF_ENABLED = False
    TEMPLATES_AUTO_RELOAD = True
