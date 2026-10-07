```python
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "hospital-secret-key"
    )

    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY",
        "hospital-jwt-secret-key"
    )

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT can work with browser cookies and API headers
    JWT_TOKEN_LOCATION = ["cookies", "headers"]

    JWT_COOKIE_SECURE = False
    JWT_COOKIE_CSRF_PROTECT = False
```
