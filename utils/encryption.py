import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

FERNET_KEY = os.getenv("FERNET_SECRET_KEY")

if not FERNET_KEY:
    raise RuntimeError(
        "FERNET_SECRET_KEY is missing. Add it to your .env file."
    )

cipher = Fernet(FERNET_KEY)


def encrypt(text: str) -> str:
    return cipher.encrypt(text.encode()).decode()


def decrypt(text: str) -> str:
    return cipher.decrypt(text.encode()).decode()


def mask_key(key: str) -> str:
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]

# # To generate a new Fernet key
# from cryptography.fernet import Fernet
# print(Fernet.generate_key().decode())
