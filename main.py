from fastapi import FastAPI
app = FastAPI(title="Mizpah API")
@app.get("/")
def home():
    return {"message": "Mizpah API is live"}
@app.get("/health")
def health():
    return {"status": "ok"}