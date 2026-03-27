from fastapi import FastAPI
from app.modes.user_mode import start_user_encounter

app = FastAPI(title='ED MAS')


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/mode/user/encounter/start')
def mode_user_start(payload: dict):
    return start_user_encounter(payload)
