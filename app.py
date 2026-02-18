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
# Intenta leer la API KEY desde los Secrets de Streamlit (para GitHub/Cloud)
# Si no existen, usa un valor por defecto o manual para local
if "API_KEY" in st.secrets:
    API_KEY = st.secrets["API_KEY"]
else:
    API_KEY = "TU_API_KEY_MANUAL_AQUI" 

EXCEL_NAME = "Inventario_Libros" 
SHEET_NAME = "para_subir" 

st.set_page_config(page_title="Catalogador Pro Movil", layout="wide")

if 'datos' not in st.session_state: 
    st.session_state.datos = None

# --- 2. FUNCIONES DE CONEXIÓN ---

def conectar_google_sheets():
    """Conexión segura a Google Sheets"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Si estamos en Streamlit Cloud, usamos los Secrets
    if "gcp_service_account" in st.secrets:
        creds_info = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    else:
        # Si estamos en local, usamos el archivo credentials.json
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
    return gspread.authorize(creds)

def get_model_vision():
    """Detecta el modelo disponible en tu cuenta"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        r = requests.get(url)
        modelos = r.json().get('models', [])
        for m in modelos:
            if "gemini-1.5-flash" in m['name'] and 'generateContent' in m.get('supportedGenerationMethods', []):
                return m['name']
        for m in modelos:
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                return m['name']
    except: pass
    return "models/gemini-1.5-flash"

# --- 3. LÓGICA DE IA ---

def analizar_imagenes_ia(imagenes_bytes):
    m_name = get_model_vision()
    url = f"https://generativelanguage.googleapis.com/v1beta/{m_name}:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    prompt_texto = """
    Actúa como experto bibliotecario. Analiza las fotos y devuelve exclusivamente un JSON. 
    Campos obligatorios: Autor (Apellido, Nombre), Titulo, Tematica, Categorias (CDU), Editorial, 
    Coleccion, Poblacion, Año, Primera_Edicion, ISBN, Paginas, Medidas, Peso, 
    Encuadernacion, Observaciones, Precio.
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
        
        # Limpieza de JSON con Regex
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        st.error(f"Error en análisis: {e}")
    return None

# --- 4. INTERFAZ ---

st.title("📸 Escáner de Libros para GitHub")

fotos = st.file_uploader("Capturar fotos (Cámara móvil)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if st.button("🔍 Analizar Libro", type="primary"):
    if fotos:
        with st.spinner("La IA está trabajando..."):
            imgs_bytes = [f.getvalue() for f in fotos]
            res = analizar_imagenes_ia(imgs_bytes)
            if res:
                st.session_state.datos = res
                st.success("¡Datos extraídos!")

if st.session_state.datos:
    d = st.session_state.datos
    col1, col2 = st.columns(2)
    
    with col1:
        f_autor = st.text_input("Autor", value=d.get("Autor", ""))
        f_titulo = st.text_input("Título", value=d.get("Titulo", ""))
        f_tem = st.text_input("Temática", value=d.get("Tematica", ""))
        f_cat = st.text_input("Categorías (CDU)", value=d.get("Categorias", ""))
        f_edi = st.text_input("Editorial", value=d.get("Editorial", ""))
        f_col = st.text_input("Colección", value=d.get("Coleccion", ""))
        f_pob = st.text_input("Población", value=d.get("Poblacion", ""))
        f_año = st.text_input("Año", value=d.get("Año", ""))

    with col2:
        f_pri = st.text_input("Primera edición", value=d.get("Primera_Edicion", ""))
        f_isbn = st.text_input("ISBN", value=d.get("ISBN", ""))
        f_pag = st.text_input("Páginas", value=d.get("Paginas", ""))
        f_med = st.text_input("Medidas", value=d.get("Medidas", ""))
        f_pes = st.text_input("Peso", value=d.get("Peso", ""))
        f_enc = st.text_input("Encuadernación", value=d.get("Encuadernacion", ""))
        f_pre = st.text_input("Precio", value=d.get("Precio", ""))
        f_obs = st.text_area("Observaciones", value=d.get("Observaciones", ""))

    if st.button("💾 Guardar en Sheets", use_container_width=True):
        try:
            gc = conectar_google_sheets()
            hoja = gc.open(EXCEL_NAME).worksheet(SHEET_NAME)
            
            fila = [
                len(hoja.get_all_values()), f_autor, f_titulo, f_tem, f_cat,
                f_edi, f_col, f_pob, f_año, f_pri, f_isbn, f_pag,
                f_med, f_pes, f_enc, f_obs, f_pre
            ]
            
            hoja.append_row(fila)
            st.balloons()
            st.success("¡Guardado correctamente!")
            st.session_state.datos = None
        except Exception as e:
            st.error(f"Error al guardar: {e}")