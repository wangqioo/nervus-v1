import os
from pathlib import Path


from nervus_sdk import NervusApp

nervus = NervusApp("model-manager")





@nervus.state
async def get_state():
    return {"status": "ok"}


if __name__ == "__main__":
    nervus.run(port=int(os.getenv("APP_PORT", "8016")))
