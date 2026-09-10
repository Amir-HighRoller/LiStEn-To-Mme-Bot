import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
AUDD_TOKEN = os.getenv("AUDD_TOKEN")

ACR_ACCESS_KEY = os.getenv("ACR_ACCESS_KEY")
ACR_ACCESS_SECRET = os.getenv("ACR_ACCESS_SECRET")
ACR_HOST = os.getenv("ACR_HOST")
ADMIN_USER_ID = int(
    os.getenv("ADMIN_USER_ID", "0")
)

ADMIN_USERNAME = os.getenv(
    "ADMIN_USERNAME"
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD"
)

ADMIN_SECRET_KEY = os.getenv(
    "ADMIN_SECRET_KEY"
)

def validate_config():
    required = {
        "ADMIN_USER_ID": ADMIN_USER_ID,
        "ADMIN_USERNAME": ADMIN_USERNAME,
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
        "ADMIN_SECRET_KEY": ADMIN_SECRET_KEY,
        "BOT_TOKEN": BOT_TOKEN,
        "AUDD_TOKEN": AUDD_TOKEN,
        "ACR_ACCESS_KEY": ACR_ACCESS_KEY,
        "ACR_ACCESS_SECRET": ACR_ACCESS_SECRET,
        "ACR_HOST": ACR_HOST,
    }

    missing = [
        name
        for name, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )