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
    API_KEY = "TU_API_KEY_AQUI" 

EXCEL_NAME = "Inventario_Libros" 
SHEET_NAME = "para_subir" 

st.set_page_config(page_title="Catalogador Multi-Foto", layout="wide")

# Inicializamos el almacén de datos para que no se pierdan al recargar
if 'datos' not in st.session_state: st.session_state.datos = None
if 'fotos_subidas' not in st.session_state: st.session_state.fotos_subidas = []

def limpiar_dato(dato):
    if isinstance(dato, list): return ", ".join(map(str, dato))
    d = str(dato) if dato and str(dato).lower() != "nan" and dato != "---" else ""
    return d.replace("[", "").replace("]", "").strip()

# --- 2. FUNCIÓN IA PARA VARIAS FOTOS ---

def analizar_varias_imagenes(lista_fotos):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    prompt_texto = """
    Analiza todas las fotos adjuntas de este libro y extrae la información para un catálogo bibliográfico.
    Devuelve exclusivamente un JSON con: Autor (APELLIDO, Nombre), Titulo, Tematica, 
    Categorias (Solo texto CDU), Editorial, Coleccion, Poblacion, Año, Primera_Edicion, 
    ISBN, Paginas, Medidas, Peso, Encuadernacion, Observaciones, Precio.
    Si un dato no es visible, pon '---'.
    """

    parts = [{"text": prompt_texto}]
    
    for foto in lista_fotos:
        # Convertimos cada foto a base64
        img_base64 = base64.b64encode(foto.getvalue()).decode('utf-8')
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": img_base64
            }
        })

    payload = {"contents": [{"parts": parts}]}
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=40)
        res = r.json()
        txt = res['candidates'][0]['content']['parts'][0]['text']
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except Exception as e:
        st.error(f"Error de la IA: {e}")
        return None

# --- 3. INTERFAZ ---

st.title("📚 Catalogador Inteligente")
st.write("Puedes tomar varias fotos (portada, contraportada, página de derechos).")

# Widget que permite múltiples archivos
fotos_nuevas = st.file_uploader("📷 Capturar o seleccionar imágenes", 
                               type=['jpg', 'jpeg', 'png'], 
                               accept_multiple_files=True,
                               key="uploader")

if fotos_nuevas:
    st.session_state.fotos_subidas = fotos_nuevas
    
    # Mostrar miniaturas de las fotos capturadas
    cols = st.columns(len(fotos_nuevas))
    for i, foto in enumerate(fotos_nuevas):
        with cols[i]:
            st.image(foto, width=150)
            # Opción para que el usuario guarde la foto en su dispositivo si quiere
            st.download_button("💾 Guardar", data=foto.getvalue(), file_name=f"libro_foto_{i}.jpg", mime="image/jpeg")

    if st.button("🔍 Analizar todas las fotos", type="primary", use_container_width=True):
        with st.spinner("La IA está procesando todas las imágenes..."):
            resultado = analizar_varias_imagenes(st.session_state.fotos_subidas)
            if resultado:
                st.session_state.datos = resultado
                st.success("¡Datos extraídos!")

# --- 4. FORMULARIO DE EDICIÓN ---

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

    if st.button("✅ Subir a Google Sheets", use_container_width=True, type="primary"):
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
            st.success("¡Datos guardados en la hoja!")
            # Limpiar todo para el siguiente libro
            st.session_state.datos = None
            st.session_state.fotos_subidas = []
        except Exception as e:
            st.error(f"Error: {e}")

if st.button("♻️ Limpiar y Nueva Captura"):
    st.session_state.datos = None
    st.session_state.fotos_subidas = []
    st.rerun()
