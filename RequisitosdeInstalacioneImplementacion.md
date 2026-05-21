pip install -r requirements.txt
playwright install --with-deps chromium
uvicorn app:app --host 0.0.0.0 --port 7860
