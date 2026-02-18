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

st.set_page_config(page_title="Catalogador Pro Estable", layout="wide")

if 'datos' not in st.session_state: st.session_state.datos = None

def limpiar_dato(dato):
    if isinstance(dato, list): return ", ".join(map(str, dato))
    d = str(dato) if dato and str(dato).lower() != "nan" and dato != "---" else ""
    return d.replace("[", "").replace("]", "").strip()

# --- 2. FUNCIÓN DE COMPRESIÓN (NUEVA) ---

def optimizar_imagen(archivo_subido):
    """Reduce el peso de la imagen para que la IA no falle"""
    img = Image.open(archivo_subido)
    # Convertir a RGB (por si es PNG o HEIC)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    # Redimensionar si es muy grande (max 1600px)
    img.thumbnail((1600, 1600))
    
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80) # Calidad 80 es ideal
    return buffer.getvalue()

# --- 3. FUNCIÓN IA ---

def analizar_imagenes_lote(lista_archivos):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    prompt_texto = """
    Analiza estas imágenes de un libro y extrae: Autor (APELLIDO, Nombre), Titulo, Tematica, 
    Categorias (Solo texto CDU), Editorial, Coleccion, Poblacion, Año, Primera_Edicion, 
    ISBN, Paginas, Medidas, Peso, Encuadernacion, Observaciones, Precio.
    Devuelve estrictamente un JSON. Si falta un dato usa '---'.
    """

    parts = [{"text": prompt_texto}]
    
    try:
        for archivo in lista_archivos:
            # Optimizamos la imagen antes de enviarla
            img_optimada = optimizar_imagen(archivo)
            img_base64 = base64.b64encode(img_optimada).decode('utf-8')
            
            parts.append({
                "inline_data": {"mime_type": "image/jpeg", "data": img_base64}
            })

        payload = {"contents": [{"parts": parts}]}
        r = requests.post(url, headers=headers, json=payload, timeout=45)
        res = r.json()

        if 'candidates' in res and res['candidates']:
            txt = res['candidates'][0]['content']['parts'][0]['text']
            match = re.search(r'\{.*\}', txt, re.DOTALL)
            return json.loads(match.group(0))
        else:
            # Mostrar el error real de Google para diagnóstico
            st.error(f"Detalle del error: {res}")
            return None

    except Exception as e:
        st.error(f"Error en el proceso: {e}")
        return None

# --- 4. INTERFAZ ---

st.title("📚 Escáner Estable (Auto-Compresión)")
st.write("Sube imágenes de la galería o cámara (máx. 4 fotos para mejor resultado).")

archivos_cargados = st.file_uploader(
    "Selecciona fotos", 
    type=['jpg', 'jpeg', 'png'], 
    accept_multiple_files=True,
    key="multi_uploader"
)

if archivos_cargados:
    cols = st.columns(min(len(archivos_cargados), 4))
    for i, archivo in enumerate(archivos_cargados):
        with cols[i % 4]:
            st.image(archivo, use_container_width=True)

    if st.button("🔍 Procesar con IA", type="primary", use_container_width=True):
        with st.spinner("Optimizando fotos y analizando..."):
            resultado = analizar_imagenes_lote(archivos_cargados)
            if resultado:
                st.session_state.datos = resultado
                st.success("¡Lectura exitosa!")

# --- 5. FORMULARIO Y GUARDADO ---

if st.session_state.datos:
    d = st.session_state.datos
    st.divider()
    with st.form("revision"):
        c1, c2 = st.columns(2)
        with c1:
            f_autor = st.text_input("Autor", value=limpiar_dato(d.get("Autor")))
            f_titulo = st.text_input("Título", value=limpiar_dato(d.get("Titulo")))
            f_tem = st.text_input("Temática", value=limpiar_dato(d.get("Tematica")))
            f_cat = st.text_input("Categorías", value=limpiar_dato(d.get("Categorias")))
            f_edi = st.text_input("Editorial", value=limpiar_dato(d.get("Editorial")))
            f_col = st.text_input("Colección", value=limpiar_dato(d.get("Coleccion")))
            f_pob = st.text_input("Población", value=limpiar_dato(d.get("Poblacion")))
            f_año = st.text_input("Año", value=limpiar_dato(d.get("Año")))
        with c2:
            f_pri = st.text_input("Primera edición", value=limpiar_dato(d.get("Primera_Edicion")))
            f_isbn = st.text_input("ISBN", value=limpiar_dato(d.get("ISBN")))
            f_pag = st.text_input("Páginas", value=limpiar_dato(d.get("Paginas")))
            f_med = st.text_input("Medidas", value=limpiar_dato(d.get("Medidas")))
            f_pes = st.text_input("Peso", value=limpiar_dato(d.get("Peso")))
            f_enc = st.text_input("Encuadernación", value=limpiar_dato(d.get("Encuadernacion")))
            f_pre = st.text_input("Precio (€)", value=limpiar_dato(d.get("Precio")))
            f_obs = st.text_area("Observaciones", value=limpiar_dato(d.get("Observaciones")))
        
        btn = st.form_submit_button("💾 Guardar en Sheets", use_container_width=True)

    if btn:
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_json = st.secrets["gcp_service_account"] if "gcp_service_account" in st.secrets else None
            
            if creds_json:
                creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
            else:
                creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            
            gc = gspread.authorize(creds)
            hoja = gc.open(EXCEL_NAME).worksheet(SHEET_NAME)
            fila = [len(hoja.get_all_values()), f_autor, f_titulo, f_tem, f_cat, f_edi, f_col, f_pob, f_año, f_pri, f_isbn, f_pag, f_med, f_pes, f_enc, f_obs, f_pre]
            hoja.append_row(fila)
            st.balloons()
            st.session_state.datos = None
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")
