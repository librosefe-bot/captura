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

if 'datos' not in st.session_state: st.session_state.datos = None

def limpiar_dato(dato):
    if isinstance(dato, list): return ", ".join(map(str, dato))
    d = str(dato) if dato and str(dato).lower() != "nan" and dato != "---" else ""
    return d.replace("[", "").replace("]", "").strip()

# --- 2. FUNCIÓN IA MEJORADA ---

def analizar_imagenes_lote(lista_archivos):
    # Usamos la URL v1beta que es la más compatible con visión actualmente
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    prompt_texto = """
    Analiza estas imágenes de un libro. Extrae la información y devuélvela estrictamente en un objeto JSON:
    Campos: Autor (APELLIDO, Nombre), Titulo, Tematica, Categorias (Texto CDU sin numeros), 
    Editorial, Coleccion, Poblacion, Año, Primera_Edicion, ISBN, Paginas, 
    Medidas, Peso, Encuadernacion, Observaciones, Precio.
    Si no ves un dato, pon '---'. No escribas nada más que el JSON.
    """

    parts = [{"text": prompt_texto}]
    
    try:
        for archivo in lista_archivos:
            # IMPORTANTE: Volver al inicio del archivo antes de leerlo
            archivo.seek(0)
            img_bytes = archivo.read()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_base64
                }
            })
            # Resetear de nuevo para que Streamlit pueda mostrar la miniatura después
            archivo.seek(0)

        payload = {"contents": [{"parts": parts}]}
        r = requests.post(url, headers=headers, json=payload, timeout=45)
        res = r.json()

        if 'candidates' in res and res['candidates']:
            txt = res['candidates'][0]['content']['parts'][0]['text']
            match = re.search(r'\{.*\}', txt, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        else:
            # Si hay error de seguridad o bloqueo de contenido, aparecerá aquí
            st.error(f"La IA no generó respuesta. Motivo: {res.get('promptFeedback', 'Desconocido')}")
            return None

    except Exception as e:
        st.error(f"Error técnico: {e}")
        return None

# --- 3. INTERFAZ ---

st.title("📚 Escáner Profesional de Libros")
st.write("Sube imágenes de la galería o usa la cámara.")

archivos_cargados = st.file_uploader(
    "Selecciona fotos (Portada, lomo, página de créditos...)", 
    type=['jpg', 'jpeg', 'png'], 
    accept_multiple_files=True,
    key="multi_uploader"
)

if archivos_cargados:
    # Mostrar miniaturas
    cols = st.columns(min(len(archivos_cargados), 4))
    for i, archivo in enumerate(archivos_cargados):
        with cols[i % 4]:
            st.image(archivo, use_container_width=True)

    if st.button("🔍 Extraer Información con IA", type="primary", use_container_width=True):
        with st.spinner("La IA está leyendo los libros..."):
            resultado = analizar_imagenes_lote(archivos_cargados)
            if resultado:
                st.session_state.datos = resultado
                st.success("¡Información extraída!")

# --- 4. FORMULARIO Y GUARDADO ---

if st.session_state.datos:
    d = st.session_state.datos
    st.divider()
    
    with st.form("ficha_revision"):
        c1, c2 = st.columns(2)
        with c1:
            f_autor = st.text_input("Autor", value=limpiar_dato(d.get("Autor")))
            f_titulo = st.text_input("Título", value=limpiar_dato(d.get("Titulo")))
            f_tem = st.text_input("Temática", value=limpiar_dato(d.get("Tematica")))
            f_cat = st.text_input("Categorías (CDU)", value=limpiar_dato(d.get("Categorias")))
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
        
        btn_guardar = st.form_submit_button("💾 Guardar Libro en Google Sheets", use_container_width=True)

    if btn_guardar:
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
            st.success("¡Libro guardado!")
            st.session_state.datos = None
        except Exception as e:
            st.error(f"Error al conectar con Sheets: {e}")

if st.button("♻️ Reiniciar"):
    st.session_state.datos = None
    st.rerun()
