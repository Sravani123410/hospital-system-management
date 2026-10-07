```python
from functools import wraps

from flask import jsonify

from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


jwt = JWTManager()


def hash_password(password):
    return generate_password_hash(password)


def check_password(password, password_hash):
    return check_password_hash(
        password_hash,
        password
    )


def generate_token(user_id, role):
    return create_access_token(
        identity=str(user_id),
        additional_claims={
            "role": role
        }
    )


def login_required(function):
    @wraps(function)
    @jwt_required()
    def wrapper(*args, **kwargs):
        return function(*args, **kwargs)

    return wrapper


def admin_required(function):
    @wraps(function)
    @jwt_required()
    def wrapper(*args, **kwargs):

        claims = get_jwt()

        if claims.get("role") != "admin":
            return jsonify({
                "error": "Admin access required"
            }), 403

        return function(*args, **kwargs)

    return wrapper


def get_current_user_id():
    return int(get_jwt_identity())


def get_current_user_role():
    claims = get_jwt()

    return claims.get("role")
```
