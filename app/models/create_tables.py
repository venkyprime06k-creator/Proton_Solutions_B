# create_tables.py
from app.database.db import engine, Base
from app.models import user, session, conversation

Base.metadata.create_all(bind=engine)
print("Tables created successfully!")