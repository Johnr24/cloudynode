from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Backend for wetransfer-grab is running."}
