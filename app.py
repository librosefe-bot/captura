import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import requests
import base64
import re

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
# Prioriza la API KEY de los Secrets de Streamlit (Nube) sobre la manual (Local)
if "API_KEY" in st.secrets:
    API_KEY = st.secrets["API_KEY"]
else:
    # Coloca aquí tu clave para pruebas locales en el PC
    API_KEY = "TU_API_KEY_AQUI" 

EXCEL_NAME = "Inventario_Libros" 
SHEET_NAME = "para_subir" 

st.set_page_config(page_title="Catalogador Pro Libros", layout="wide")

if 'datos' not in st.session_state: 
    st.session_state.datos = None

# --- 2. FUNCIONES DE LIMPIEZA Y CONEXIÓN ---

def limpiar_dato(dato):
    """Elimina corchetes de listas y filtra textos de la IA"""
    if isinstance(dato, list):
        return ", ".join(map(str, dato))
    
    # Convierte a texto y quita corchetes residuales si los hay
    dato_str = str(dato) if dato and str(dato).lower() != "nan" and dato != "---" else ""
    dato_str = dato_str.replace("[", "").replace("]", "").strip()
    
    # Si la IA devuelve algo como "82 Literatura", intentamos limpiar el número inicial
    # Solo si el usuario quiere una limpieza estricta de la CDU
    return dato_str

def conectar_google_sheets():
    """Conecta a Google Sheets usando Secrets o archivo local"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    if "gcp_service_account" in st.secrets:
        # Modo Streamlit Cloud (GitHub)
        creds_info = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    else:
        # Modo Local (PC)
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
    return gspread.authorize(creds)

def get_model_vision():
    """Detecta el modelo Gemini con capacidad de visión"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        r = requests.get(url)
        modelos = r.json().get('models', [])
        for m in modelos:
            if "gemini-1.5-flash" in m['name'] and 'generateContent' in m.get('supportedGenerationMethods', []):
                return m['name']
    except: pass
    return "models/gemini-1.5-flash"

# --- 3. PROCESAMIENTO CON IA ---

def analizar_imagenes_ia(imagenes_bytes):
    m_name = get_model_vision()
    url = f"https://generativelanguage.googleapis.com/v1beta/{m_name}:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    # Instrucciones estrictas para evitar corchetes y números en la CDU
    prompt_texto = """
    Actúa como experto bibliotecario. Analiza las fotos y devuelve exclusivamente un JSON. 
    
    REGLAS DE FORMATO:
    1. Autor: Texto simple 'APELLIDO, Nombre'. PROHIBIDO usar listas [] o corchetes.
    2. Categorias: Solo la descripción textual de la CDU. PROHIBIDO incluir códigos numéricos. 
       Ejemplo: "Literatura francesa" (BIEN), "[840] Literatura" (MAL).
    3. Si no encuentras un dato, usa "---".
    
    Campos: Autor, Titulo, Tematica, Categorias, Editorial, Coleccion, Poblacion, Año, 
    Primera_Edicion, ISBN, Paginas, Medidas, Peso, Encuadernacion, Observaciones, Precio.
    """

    parts = [{"text": prompt_texto}]
    for img_bytes in imagenes_bytes:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(img_bytes).decode('utf-8')
            }
        })

    payload = {"contents": [{"parts": parts}]}
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        res = r.json()
        txt
