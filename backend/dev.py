"""Start the development API on the port configured in the root .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv
import uvicorn


if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    uvicorn.run("main:app", host="127.0.0.1", port=int(os.getenv("BACKEND_PORT", "8000")), reload=True)
