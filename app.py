import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import requests
import base64
import re

# --- 1. CONFIGURACIÓN ---
if "API_KEY" in st.secrets:
    API_KEY = st.secrets["API_KEY"]
else:
    API_KEY = "AIzaSyBILmrsJrf4DFJNmw3WSNFByCc4SZ4v8ho" 

EXCEL_NAME = "Inventario_Libros" 
SHEET_NAME = "para_subir" 

st.set_page_config(page_title="Catalogador Total", layout="wide")

# Inicializar estados de sesión
if 'datos' not in st.session_state: st.session_state.datos = None
if 'archivo_ids' not in st.session_state: st.session_state.archivo_ids = []

def limpiar_dato(dato):
    if isinstance(dato, list): return ", ".join(map(str, dato))
    d = str(dato) if dato and str(dato).lower() != "nan" and dato != "---" else ""
    return d.replace("[", "").replace("]", "").strip()

# --- 2. FUNCIÓN IA MULTI-IMAGEN ---

def analizar_imagenes_lote(lista_archivos):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    prompt_texto = """
    Analiza estas imágenes de un libro. Extrae: Autor (APELLIDO, Nombre), Titulo, Tematica, 
    Categorias (Solo texto CDU), Editorial, Coleccion, Poblacion, Año, Primera_Edicion, 
    ISBN, Paginas, Medidas, Peso, Encuadernacion, Observaciones, Precio.
    Devuelve estrictamente un JSON. Si falta un dato usa '---'.
    """

    parts = [{"text": prompt_texto}]
    for archivo in lista_archivos:
        img_base64 = base64.b64encode(archivo.read()).decode('utf-8')
        parts.append({
            "inline_data": {"mime_type": "image/jpeg", "data": img_base64}
        })
        archivo.seek(0) # Resetear puntero para poder volver a leerlo si hace falta

    payload = {"contents": [{"parts": parts}]}
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=40)
        res = r.json()
        txt = res['candidates'][0]['content']['parts'][0]['text']
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except Exception as e:
        st.error(f"Error IA: {e}")
        return None

# --- 3. INTERFAZ ---

st.title("📚 Catalogador Profesional")
st.write("Selecciona fotos de tu **galería** o usa la **cámara**.")

# El componente detecta automáticamente si es móvil para ofrecer Galería/Archivos o Cámara
archivos_cargados = st.file_uploader(
    "Selecciona una o varias imágenes (Fotos ya guardadas o Cámara)", 
    type=['jpg', 'jpeg', 'png'], 
    accept_multiple_files=True,
    key="multi_uploader"
)

if archivos_cargados:
    st.subheader(f"📸 Imágenes preparadas: {len(archivos_cargados)}")
    
    # Mostrar miniaturas para confirmar qué se ha subido
    cols = st.columns(min(len(archivos_cargados), 4))
    for i, archivo in enumerate(archivos_cargados):
        with cols[i % 4]:
            st.image(archivo, use_container_width=True)

    if st.button("🔍 Procesar Imágenes con IA", type="primary", use_container_width=True):
        with st.spinner("Analizando información..."):
            resultado = analizar_imagenes_lote(archivos_cargados)
            if resultado:
                st.session_state.datos = resultado
                st.success("¡Información extraída!")

# --- 4. FORMULARIO Y GUARDADO ---

if st.session_state.datos:
    d = st.session_state.datos
    st.divider()
    with st.form("ficha_libro"):
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
        
        guardar = st.form_submit_button("💾 Guardar en Google Sheets", use_container_width=True)

    if guardar:
        try:
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
            st.success("✅ ¡Libro registrado con éxito!")
            st.session_state.datos = None
        except Exception as e:
            st.error(f"Error al guardar: {e}")

if st.button("♻️ Reiniciar Todo"):
    st.session_state.datos = None
    st.rerun()
