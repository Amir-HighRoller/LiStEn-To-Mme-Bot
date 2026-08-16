import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
AUDD_TOKEN = os.getenv("AUDD_TOKEN")

ACR_ACCESS_KEY = os.getenv("ACR_ACCESS_KEY")
ACR_ACCESS_SECRET = os.getenv("ACR_ACCESS_SECRET")
ACR_HOST = os.getenv("ACR_HOST")


def validate_config():
    required = {
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