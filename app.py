import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import requests
import base64
import re
from PIL import Image
import io

# --- 1. CONFIGURACIÓN ---
if "API_KEY" in st.secrets:
    API_KEY = st.secrets["API_KEY"]
else:
    API_KEY = "AIzaSyBILmrsJrf4DFJNmw3WSNFByCc4SZ4v8ho" 

EXCEL_NAME = "Inventario_Libros" 
SHEET_NAME = "para_subir" 

st.set_page_config(page_title="Catalogador Pro", layout="wide")

# Inicializar estados si no existen
if 'datos' not in st.session_state: st.session_state.datos = None
if 'fotos_procesadas' not in st.session_state: st.session_state.fotos_procesadas = []

def limpiar_dato(dato):
    if isinstance(dato, list): return ", ".join(map(str, dato))
    d = str(dato) if dato and str(dato).lower() != "nan" and dato != "---" else ""
    return d.replace("[", "").replace("]", "").strip()

# --- 2. LÓGICA DE IA ---

def analizar_imagenes_ia(imagenes_bytes):
    # Usamos la versión estable de la URL que ya probamos
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    prompt_texto = """
    Analiza las fotos y devuelve exclusivamente un JSON. 
    Campos: Autor (APELLIDO, Nombre), Titulo, Tematica, Categorias (Texto CDU sin numeros), 
    Editorial, Coleccion, Poblacion, Año, Primera_Edicion, ISBN, Paginas, 
    Medidas, Peso, Encuadernacion, Observaciones, Precio.
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
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except: return None

# --- 3. INTERFAZ ---

st.title("📚 Escáner de Libros")

# Agregamos 'label_visibility' para que sea más limpio en móvil
# El parámetro 'key' ayuda a Streamlit a no perder el estado al capturar
fotos = st.file_uploader("📷 Toca para abrir cámara o subir", 
                         type=['jpg', 'jpeg', 'png'], 
                         accept_multiple_files=True,
                         key="camara_input")

if fotos:
    # Mostramos una vista previa pequeña para confirmar que la foto está "ahí"
    st.write(f"✅ {len(fotos)} imagen(es) lista(s) para procesar.")
    
    if st.button("🔍 Extraer Datos del Libro", type="primary"):
        with st.spinner("Leyendo las fotos..."):
            # Convertimos las fotos a bytes
            imgs_bytes = [f.read() for f in fotos]
            resultado = analizar_imagenes_ia(imgs_bytes)
            if resultado:
                st.session_state.datos = resultado
                st.success("¡Datos extraídos con éxito!")
            else:
                st.error("La IA no pudo leer la imagen. Intenta con más luz.")

# --- 4. FORMULARIO Y GUARDADO ---

if st.session_state.datos:
    d = st.session_state.datos
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        f_autor = st.text_input("Autor", value=limpiar_dato(d.get("Autor")))
        f_titulo = st.text_input("Título", value=limpiar_dato(d.get("Titulo")))
        f_tem = st.text_input("Temática", value=limpiar_dato(d.get("Tematica")))
        f_cat = st.text_input("Categorías (CDU)", value=limpiar_dato(d.get("Categorias")))
        f_edi = st.text_input("Editorial", value=limpiar_dato(d.get("Editorial")))
        f_col = st.text_input("Colección", value=limpiar_dato(d.get("Coleccion")))
        f_pob = st.text_input("Población", value=limpiar_dato(d.get("Poblacion")))
        f_año = st.text_input("Año", value=limpiar_dato(d.get("Año")))
    with col2:
        f_pri = st.text_input("Primera edición", value=limpiar_dato(d.get("Primera_Edicion")))
        f_isbn = st.text_input("ISBN", value=limpiar_dato(d.get("ISBN")))
        f_pag = st.text_input("Páginas", value=limpiar_dato(d.get("Paginas")))
        f_med = st.text_input("Medidas", value=limpiar_dato(d.get("Medidas")))
        f_pes = st.text_input("Peso", value=limpiar_dato(d.get("Peso")))
        f_enc = st.text_input("Encuadernación", value=limpiar_dato(d.get("Encuadernacion")))
        f_pre = st.text_input("Precio (€)", value=limpiar_dato(d.get("Precio")))
        f_obs = st.text_area("Observaciones", value=limpiar_dato(d.get("Observaciones")))

    if st.button("💾 Guardar en Google Sheets", use_container_width=True):
        try:
            # Conexión simplificada (asumiendo que los Secrets ya están puestos)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            if "gcp_service_account" in st.secrets:
                creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["gcp_service_account"]), scope)
            else:
                creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            
            gc = gspread.authorize(creds)
            hoja = gc.open(EXCEL_NAME).worksheet(SHEET_NAME)
            
            fila = [
                len(hoja.get_all_values()), f_autor, f_titulo, f_tem, f_cat,
                f_edi, f_col, f_pob, f_año, f_pri, f_isbn, f_pag,
                f_med, f_pes, f_enc, f_obs, f_pre
            ]
            
            hoja.append_row(fila)
            st.balloons()
            st.success("¡Guardado!")
            st.session_state.datos = None
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")
