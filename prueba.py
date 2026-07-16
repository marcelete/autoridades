from google import genai
import os

# La clave se lee del entorno / .env (GEMINI_API_KEY_1). Nunca hardcodeada.
MI_API_KEY = os.environ.get("GEMINI_API_KEY_1", "")

try:
    print("Iniciando conexión con la API...")
    client = genai.Client(api_key=MI_API_KEY)
    
    print("Conexión exitosa. Listando modelos disponibles:")
    print("-" * 50)
    
    # Recorremos los modelos que la API nos devuelve
    for m in client.models.list():
        # Filtramos para ver solo los importantes
        if "gemini" in m.name.lower() or "flash" in m.name.lower():
            print(f"ID del modelo: {m.name}")
            print(f"  - Descripción: {m.description}")
            print("-" * 20)
            
except Exception as e:
    print(f"ERROR: No se pudo conectar: {e}")