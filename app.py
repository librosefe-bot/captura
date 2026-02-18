import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import requests
import base64
import re
from PIL import Image
import io

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
# Se prioriza la API KEY de los Secrets de Streamlit para el despliegue en la nube
if "API_KEY" in st.secrets:
    API_KEY = st.secrets["API_KEY"]
else:
    # Cambia esto por tu clave real para pruebas locales
    API_KEY = "TU_API_KEY_AQUI" 

EXCEL_NAME = "Inventario_Libros" 
SHEET_NAME = "para_subir" 

st.set_page_config(page_title="Catalogador Pro Movil", layout="wide")

if 'datos' not in st.session_state: 
    st.session_state.datos = None

# --- 2. FUNCIONES DE LIMPIEZA Y CONEXIÓN ---

def limpiar_dato(dato):
    """Elimina corchetes de listas y limpia formatos de la IA"""
    if isinstance(dato, list):
        return ", ".join(map(str, dato))
    
    # Convierte a string y elimina corchetes residuales o valores vacíos
    dato_str = str(dato) if dato and str(dato).lower() != "nan" and dato != "---" else ""
    return dato_str.replace("[", "").replace("]", "").strip()

def conectar_google_sheets():
    """Conexión segura a Google Sheets (Local o Cloud)"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    if "gcp_service_account" in st.secrets:
        # En Streamlit Cloud usamos la configuración de Secrets
        creds_info = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    else:
        # En local usamos el archivo físico
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
    return gspread.authorize(creds)

def get_model_vision():
    """Detecta automáticamente el modelo Gemini con visión disponible"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        r = requests.get(url)
        modelos = r.json().get('models', [])
        # Prioridad para gemini-1.5-flash
        for m in modelos:
            if "gemini-1.5-flash" in m['name'] and 'generateContent' in m.get('supportedGenerationMethods', []):
                return m['name']
        for m in modelos:
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                return m['name']
    except: pass
    return "models/gemini-1.5-flash"

# --- 3. PROCESAMIENTO CON IA ---

def analizar_imagenes_ia(imagenes_bytes):
    m_name = get_model_vision()
    url = f"https://generativelanguage.googleapis.com/v1beta/{m_name}:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    # Prompt optimizado para evitar corchetes y números en la CDU
    prompt_texto = """
    Actúa como experto bibliotecario y tasador. Analiza las fotos y devuelve exclusivamente un JSON. 
    
    REGLAS ESTRICTAS DE FORMATO:
    1. Autor: Devuelve un texto simple 'APELLIDO, Nombre'. NO uses listas [].
    2. Categorias: Devuelve SOLO la descripción técnica de la CDU. NO incluyas números ni corchetes. 
       Ejemplo: "Literatura española" (Correcto), "[82] Literatura" (Incorrecto).
    3. Precio: Estima el valor en Euros.
    4. Campos: Autor, Titulo, Tematica, Categorias, Editorial, Coleccion, Poblacion, Año, Primera_Edicion, ISBN, Paginas, Medidas, Peso, Encuadernacion, Observaciones, Precio.
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
        txt = res['candidates'][0]['content']['parts'][0]['text']
        
        # Extraer JSON puro del texto de respuesta
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        st.error(f"Error en el análisis: {e}")
    return None

# --- 4. INTERFAZ DE USUARIO ---

st.title("📚 Catalogador Pro (Móvil & Cloud)")
st.write("Captura fotos del libro para extraer sus datos automáticamente.")

# Subida de imágenes (abre la cámara en móviles)
fotos = st.file_uploader("📷 Capturar Portada / Créditos", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if st.button("🔍 Analizar Libro", type="primary"):
    if fotos:
        with st.spinner("La IA está extrayendo los datos..."):
            imgs_bytes = [f.getvalue() for f in fotos]
            res = analizar_imagenes_ia(imgs_bytes)
            if res:
                st.session_state.datos = res
                st.success("¡Análisis completado!")
    else:
        st.warning("Por favor, captura o sube alguna foto.")

# --- 5. FORMULARIO DE REVISIÓN Y GUARDADO ---

if st.session_
