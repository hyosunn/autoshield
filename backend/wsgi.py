from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from apps import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5001)