import os

DATABASE_URL = os.getenv("DATABASE_URL", "")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-for-local-development")
ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 7
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",")
