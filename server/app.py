import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from server import routes_engine, routes_data, routes_web

load_dotenv()
for d in ["data", "data/clips", "data/state"]:
    os.makedirs(d, exist_ok=True)
app = FastAPI(title="Pact")
app.mount("/static", StaticFiles(directory="server/static"), name="static")
app.mount("/clips", StaticFiles(directory="data/clips"), name="clips")
app.include_router(routes_engine.router)
app.include_router(routes_data.router)
app.include_router(routes_web.router)
