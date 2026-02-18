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
        txt = res['candidates'][0]['content']['parts'][0]['text']
        
        # Extraer el bloque JSON puro del texto
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        st.error(f"Error analizando imágenes: {e}")
    return None

# --- 4. INTERFAZ ---

st.title("📚 Catalogador de Libros (IA)")
st.info("Sube fotos de la portada y página de créditos. En el móvil se abrirá la cámara.")

# Al usar accept_multiple_files, en el móvil permite capturar varias fotos
fotos = st.file_uploader("📷 Capturar / Subir Fotos", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if st.button("🔍 Extraer Datos", type="primary"):
    if fotos:
        with st.spinner("Analizando libro..."):
            imgs_bytes = [f.getvalue() for f in fotos]
            resultado = analizar_imagenes_ia(imgs_bytes)
            if resultado:
                st.session_state.datos = resultado
                st.success("¡Análisis listo!")
    else:
        st.warning("Captura al menos una foto.")

# --- 5. FORMULARIO Y GUARDADO ---

if st.session_state.datos:
    d = st.session_state.datos
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        f_autor = st.text_input("Autor (Apellido, Nombre)", value=limpiar_dato(d.get("Autor")))
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

    if st.button("💾 Subir a Sheets", use_container_width=True, type="primary"):
        try:
            gc = conectar_google_sheets()
            hoja = gc.open(EXCEL_NAME).worksheet(SHEET_NAME)
            
            # Se calcula el ID por fila
            nuevo_id = len(hoja.get_all_values())
            
            fila = [
                nuevo_id, f_autor, f_titulo, f_tem, f_cat,
                f_edi, f_col, f_pob, f_año, f_pri, f_isbn, f_pag,
                f_med, f_pes, f_enc, f_obs, f_pre
            ]
            
            hoja.append_row(fila)
            st.balloons()
            st.success(f"✅ ¡Guardado! ID asignado: {nuevo_id}")
            st.session_state.datos = None
        except Exception as e:
            st.error(f"Error al guardar: {e}")

if st.button("♻️ Reiniciar"):
    st.session_state.datos = None
    st.rerun()
