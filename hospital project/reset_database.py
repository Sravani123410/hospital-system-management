```python
from app import app
from models import db


with app.app_context():

    print("Removing old tables...")

    db.drop_all()

    print("Creating new tables...")

    db.create_all()

    print("Database reset completed successfully!")
```
