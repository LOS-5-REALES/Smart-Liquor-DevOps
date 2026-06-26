# app/auth.py
import os
import httpx

SUPABASE_URL      = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")


def login(email: str, password: str):
    print(f"[AUTH] Intentando login con: {email}")
    print(f"[AUTH] SUPABASE_URL: {SUPABASE_URL}")
    print(f"[AUTH] ANON_KEY existe: {bool(SUPABASE_ANON_KEY)}")

    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    body = {"email": email, "password": password}

    try:
        response = httpx.post(url, json=body, headers=headers)
        print(f"[AUTH] Status code: {response.status_code}")
        print(f"[AUTH] Response: {response.text[:200]}")

        if response.status_code == 200:
            data = response.json()
            print("[AUTH] Login exitoso")
            return data.get("user")
        else:
            error = response.json().get("error_description", "Credenciales incorrectas")
            print(f"[AUTH] Error: {error}")
            raise Exception(error)
    except Exception as ex:
        print(f"[AUTH] Excepcion: {ex}")
        raise