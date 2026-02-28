import os
import sys

import uvicorn

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=7860, reload=True)
