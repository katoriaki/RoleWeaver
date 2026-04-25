import os

os.environ["PYTHONUTF8"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from role_chat_service import main


if __name__ == "__main__":
    main()
