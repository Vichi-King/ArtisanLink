import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")

    _db_url = os.getenv("DATABASE_URL")
    if _db_url and _db_url.startswith("mysql://"):
        _db_url = _db_url.replace("mysql://", "mysql+pymysql://", 1)

    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False