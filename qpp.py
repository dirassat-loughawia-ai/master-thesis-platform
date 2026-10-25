import streamlit as st
import pandas as pd
import os
import requests
import urllib.parse
import random
import string
from datetime import datetime
from io import BytesIO
import zipfile
from streamlit_gsheets import GSheetsConnection

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.utils import ImageReader

import arabic_reshaper
from bidi.algorithm import get_display
import qrcode

# --- 1. ط¥ط¹ط¯ط§ط¯ط§طھ ط§ظ„طµظپط­ط© ط§ظ„ط£ط³ط§ط³ظٹط© ---
st.set_page_config(
    page_title="ظ…ظ†طµط© ط¥ط¯ط§ط±ط© ظ…ط°ظƒط±ط§طھ ط§ظ„ظ…ط§ط³طھط± - ط¬ط§ظ…ط¹ط© ط§ظ„ظˆط§ط¯ظٹ",
    page_icon="ًںژ“",
    layout="wide"
)

# ط±ط§ط¨ط· GitHub Raw ظ„ط¬ظ„ط¨ ط§ظ„ط£ظٹظ‚ظˆظ†ط§طھ ظˆط§ظ„طھظˆظ‚ظٹط¹ط§طھ ظ…ط¨ط§ط´ط± ط£ظˆظ†ظ„ط§ظٹظ†
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/USERNAME/REPOSITORY/main/" # ظ‚ظ… ط¨طھط¹ط¯ظٹظ„ ط§ط³ظ… ط§ظ„ظ…ط³طھط®ط¯ظ… ظˆط§ظ„ظ…ط³طھظˆط¯ط¹ ط¥ظ† ظ„ط²ظ…

SPREADSHEET_ID = "1GvS4BE2WL18peY97GAfjRJz9LdZTCZYWlV7P-QsJpOQ"
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyM9CVCiTLW5dcPZp13N4moSCpt_to-kc7o8ZPQCQPX3AjU_SV0fLXm7wNT5odtkWoyZA/exec"

SHEET_TEACHERS = "ظ‚ط§ط¦ظ…ط© ط§ظ„ط£ط³ط§طھط°ط©"
SHEET_ADMINS = "ظƒظ„ظ…ط§طھ ظ…ط±ظˆط± ط§ظ„ظ…ط³ط¤ظˆظ„ظٹظ†"
SHEET_STUDENTS = "ظ‚ظˆط§ط¦ظ… ط§ظ„ط·ظ„ط¨ط©"
SHEET_TITLES = "ط§ظ„ط¹ظ†ط§ظˆظٹظ† ط§ظ„ظ…ط³ط¬ظ„ط©"
SHEET_MOD_REQUESTS = "ط·ظ„ط¨ط§طھ ط§ظ„طھط¹ط¯ظٹظ„"
SHEET_FINAL_REGISTRATIONS = "ط§ظ„طھط³ط¬ظٹظ„ط§طھ ط§ظ„ظ†ظ‡ط§ط¦ظٹط©"
SHEET_ATTEST_NUMBERS = "ط±ظ‚ظ… ط§ظ„ط¥ظپط§ط¯ط©"
SHEET_VISITORS = "ط¹ط¯ط§ط¯ ط§ظ„ط²ظˆط§ط±"

SPECIALTIES = ["ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©", "ط£ط¯ط¨ ط¹ط±ط¨ظٹ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±", "ظ†ظ‚ط¯ ط­ط¯ظٹط« ظ…ط¹ط§طµط±", "ط£ط¯ط¨ ط´ط¹ط¨ظٹ"]
MASTER_SUPER_PASS = "0000"
ATTESTATION_PASS = "20262027"

def prevent_sleep_mode():
    st.markdown("""
        <script>
            function keepAlive() { fetch(window.location.href); }
            setInterval(keepAlive, 300000);
        </script>
    """, unsafe_allow_html=True)

prevent_sleep_mode()

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    conn = None

def clean_df_columns(df):
    if not df.empty:
        df = df.fillna("").astype(str)
        df.columns = [str(col).strip().replace("_", " ") for col in df.columns]
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df

def load_data_from_sheet(worksheet_name):
    st.cache_data.clear()
    if conn is not None:
        try:
            df = conn.read(worksheet=worksheet_name, ttl=0)
            if not df.empty:
                return clean_df_columns(df)
        except Exception:
            pass

    try:
        encoded_name = urllib.parse.quote(worksheet_name.strip())
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
        df = pd.read_csv(url, encoding='utf-8')
        return clean_df_columns(df)
    except Exception:
        return pd.DataFrame()

def send_payload_to_script(payload):
    try:
        response = requests.post(WEB_APP_URL, json=payload, timeout=20)
        st.cache_data.clear()
        if response.status_code == 200:
            try:
                return response.json()
            except Exception:
                return {"status": "success", "message": response.text}
        return None
    except Exception as e:
        st.error(f"ط®ط·ط£ ظپظٹ ط§ظ„ط§طھطµط§ظ„ ط§ظ„ط³ط­ط§ط¨ظٹ: {e}")
        return None

# ط¯ط§ظ„ط© طھظˆظ„ظٹط¯ ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط© ط§ظ„ط¹ط´ظˆط§ط¦ظٹ (4 ط­ط±ظˆظپ + 4 ط£ط±ظ‚ط§ظ…)
def generate_form_code():
    letters = ''.join(random.choices(string.ascii_uppercase, k=4))
    digits = ''.join(random.choices(string.digits, k=4))
    return f"{letters}-{digits}"

# --- 2. ط¥ط¯ط§ط±ط© ط¹ط¯ط§ط¯ ط§ظ„ط²ظˆط§ط± ط§ظ„ط³ط­ط§ط¨ظٹ ط§ظ„ظ…طھط·ظˆط± ---
def update_and_get_visitor_count():
    if 'visitor_counted' not in st.session_state:
        st.session_state.visitor_counted = True
        payload = {"action": "increment_counter", "sheet_name": SHEET_VISITORS}
        send_payload_to_script(payload)
    
    df_vis = load_data_from_sheet(SHEET_VISITORS)
    if not df_vis.empty:
        try:
            val = int(df_vis.iloc[0, 0])
            return val
        except Exception:
            return len(df_vis) + 1
    return 1

# --- 3. ط¥ط¯ط§ط±ط© ط±ظ‚ظ… ط§ظ„ط¥ظپط§ط¯ط© ظپظٹ ظ‚ط§ط¹ط¯ط© ط§ظ„ط¨ظٹط§ظ†ط§طھ ---
def get_next_attestation_number(teacher_name):
    df_att = load_data_from_sheet(SHEET_ATTEST_NUMBERS)
    current_year = datetime.now().strftime("%Y")
    
    if not df_att.empty:
        t_col = [c for c in df_att.columns if "ط£ط³طھط§ط°" in c or "ط§ط³طھط§ط°" in c]
        if t_col:
            matched = df_att[df_att[t_col[0]].astype(str).str.strip() == str(teacher_name).strip()]
            if not matched.empty and "ط±ظ‚ظ… ط§ظ„ط¥ظپط§ط¯ط©" in matched.columns:
                return str(matched["ط±ظ‚ظ… ط§ظ„ط¥ظپط§ط¯ط©"].values[0])
        next_num = len(df_att) + 1
    else:
        next_num = 1
        
    att_code = f"ط¥.طھ/{current_year}/{next_num:04d}"
    
    row_data = {"ط§ط³ظ… ط§ظ„ط£ط³طھط§ط°": teacher_name, "ط±ظ‚ظ… ط§ظ„ط¥ظپط§ط¯ط©": att_code, "طھط§ط±ظٹط® ط§ظ„ط¥طµط¯ط§ط±": datetime.now().strftime("%Y-%m-%d %H:%M")}
    payload = {"action": "append", "sheet_name": SHEET_ATTEST_NUMBERS, "row_data": list(row_data.values())}
    send_payload_to_script(payload)
    
    return att_code

def save_data_to_sheet(row_data_dict, worksheet_name):
    if worksheet_name == SHEET_FINAL_REGISTRATIONS:
        ordered_keys = ["ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©", "ط§ط³ظ… ط§ظ„ط£ط³طھط§ط°", "طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨", "ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 1", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ 1", "ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 2", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ 2", "ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©", "طھط§ط±ظٹط® ط§ظ„طھط³ط¬ظٹظ„", "ظƒظˆط¯ ط§ظ„طھط­ظ‚ظ‚"]
        row_values = [str(row_data_dict.get(k, "")).strip() for k in ordered_keys]
    else:
        row_values = [str(v).strip() for v in row_data_dict.values()]

    payload = {
        "action": "append",
        "sheet_name": worksheet_name,
        "row_data": row_values
    }
    res = send_payload_to_script(payload)
    return res is not None

def delete_registration_from_sheet(orig_title):
    payload = {
        "action": "delete_row",
        "sheet_name": SHEET_FINAL_REGISTRATIONS,
        "key_val": str(orig_title).strip()
    }
    res = send_payload_to_script(payload)
    return res is not None

def update_registration_in_sheet(orig_title, row_data_dict):
    ordered_keys = ["ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©", "ط§ط³ظ… ط§ظ„ط£ط³طھط§ط°", "طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨", "ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 1", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ 1", "ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 2", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ 2", "ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©", "طھط§ط±ظٹط® ط§ظ„طھط³ط¬ظٹظ„", "ظƒظˆط¯ ط§ظ„طھط­ظ‚ظ‚"]
    row_values = [str(row_data_dict.get(k, "")).strip() for k in ordered_keys]
    payload = {
        "action": "update_row",
        "sheet_name": SHEET_FINAL_REGISTRATIONS,
        "key_val": str(orig_title).strip(),
        "row_data": row_values
    }
    res = send_payload_to_script(payload)
    return res is not None

def update_title_in_sheets_after_approval(teacher_name, orig_title, new_title):
    payload = {
        "action": "update_title_everywhere",
        "teacher": str(teacher_name).strip(),
        "orig_title": str(orig_title).strip(),
        "new_title": str(new_title).strip()
    }
    res = send_payload_to_script(payload)
    return res is not None

def update_mod_request_status_in_sheet(orig_title, status, handler, teacher_name="", new_title=""):
    payload = {
        "action": "update_status",
        "sheet_name": SHEET_MOD_REQUESTS,
        "orig_title": str(orig_title).strip(),
        "status": str(status).strip(),
        "handler": str(handler).strip()
    }
    res = send_payload_to_script(payload)
    success = res is not None
    if success and "ظ…ظ‚ط¨ظˆظ„" in status and teacher_name and new_title:
        update_title_in_sheets_after_approval(teacher_name, orig_title, new_title)
    return success

# --- 4. ط¥ط¹ط¯ط§ط¯ ط§ظ„ط®ط· ط§ظ„ط¹ط±ط¨ظٹ ظˆطµظˆط± ط§ظ„ظ…ط³طھظ†ط¯ط§طھ ---
def setup_arabic_font():
    local_fonts = ["trado.ttf", "Traditional Arabic.ttf", "Traditional-Arabic.ttf", "Amiri-Regular.ttf", "arial.ttf"]
    for font_p in local_fonts:
        if os.path.exists(font_p):
            try:
                pdfmetrics.registerFont(TTFont('TraditionalArabic', font_p))
                pdfmetrics.registerFont(TTFont('TraditionalArabic-Bold', font_p))
                return 'TraditionalArabic', 'TraditionalArabic-Bold'
            except Exception:
                pass

    try:
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Regular.ttf"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            with open("trado.ttf", "wb") as f:
                f.write(r.content)
            pdfmetrics.registerFont(TTFont('TraditionalArabic', "trado.ttf"))
            pdfmetrics.registerFont(TTFont('TraditionalArabic-Bold', "trado.ttf"))
            return 'TraditionalArabic', 'TraditionalArabic-Bold'
    except Exception:
        pass

    return 'Helvetica', 'Helvetica-Bold'

ARABIC_FONT, ARABIC_FONT_BOLD = setup_arabic_font()

def reshape_arabic(text):
    if text is None or pd.isna(text):
        return ""
    txt_str = str(text).strip()
    if txt_str == "" or txt_str.lower() in ["nan", "none", "null"]:
        return ""
    reshaped_text = arabic_reshaper.reshape(txt_str)
    return get_display(reshaped_text)

@st.cache_data(ttl=3600)
def get_image_bytes(image_filename):
    if os.path.exists(image_filename):
        try:
            with open(image_filename, "rb") as f:
                return f.read()
        except Exception:
            pass
    try:
        url = GITHUB_RAW_BASE_URL + image_filename
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.content
    except Exception:
        pass
    return None

def make_reportlab_image(image_filename, width, height):
    b_data = get_image_bytes(image_filename)
    if b_data:
        try:
            buf = BytesIO(b_data)
            return RLImage(buf, width=width, height=height)
        except Exception:
            pass
    return None

def draw_header_icons(can, page_width, page_height):
    b1 = get_image_bytes("ICON1.png")
    if b1:
        try:
            can.drawImage(ImageReader(BytesIO(b1)), page_width - 80, page_height - 75, width=50, height=50, mask='auto')
        except Exception: pass

    b2 = get_image_bytes("ICON2.png")
    if b2:
        try:
            can.drawImage(ImageReader(BytesIO(b2)), 30, page_height - 75, width=50, height=50, mask='auto')
        except Exception: pass

# --- 5. طھظˆظ„ظٹط¯ ط§ظ„ظ€ QR Code ظˆط¨ظ†ط§ط، ظ…ظ„ظپط§طھ PDF ---
def generate_qr_code_image(data_text):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=1,
    )
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ط¯ط§ظ„ط© طھظˆظ„ظٹط¯ ط§ط³طھظ…ط§ط±ط© ط§ظ„طھط³ط¬ظٹظ„ ط§ظ„ظ…ط¹ط¯ظ„ط© ط¨ط§ظ„ظƒط§ظ…ظ„ ظˆظپظ‚ ط§ظ„ظ…ط·ظ„ظˆط¨ط§طھ
def generate_pdf_document(form_code, teacher_name, specialty, st1_name, st1_reg, st2_name, st2_reg, title, qr_code_str):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    page_width, page_height = letter
    center_x = page_width / 2.0

    can.setLineWidth(2)
    can.rect(20, 20, page_width - 40, page_height - 40)

    draw_header_icons(can, page_width, page_height)

    # طھظƒط¨ظٹط± ط§ظ„طھط±ظˆظٹط³ط©
    can.setFont(ARABIC_FONT_BOLD, 15)
    can.drawCentredString(center_x, page_height - 38, reshape_arabic("ط§ظ„ط¬ظ…ظ‡ظˆط±ظٹط© ط§ظ„ط¬ط²ط§ط¦ط±ظٹط© ط§ظ„ط¯ظٹظ…ظ‚ط±ط§ط·ظٹط© ط§ظ„ط´ط¹ط¨ظٹط©"))
    can.setFont(ARABIC_FONT_BOLD, 14)
    can.drawCentredString(center_x, page_height - 55, reshape_arabic("ظˆط²ط§ط±ط© ط§ظ„طھط¹ظ„ظٹظ… ط§ظ„ط¹ط§ظ„ظٹ ظˆط§ظ„ط¨ط­ط« ط§ظ„ط¹ظ„ظ…ظٹ"))
    can.setFont(ARABIC_FONT_BOLD, 15)
    can.drawCentredString(center_x, page_height - 73, reshape_arabic("ط¬ط§ظ…ط¹ط© ط§ظ„ظˆط§ط¯ظٹ - ظƒظ„ظٹط© ط§ظ„ط¢ط¯ط§ط¨ ظˆط§ظ„ظ„ط؛ط§طھ"))

    can.setLineWidth(1)
    can.line(30, page_height - 82, page_width - 30, page_height - 82)

    can.setFont(ARABIC_FONT_BOLD, 13)
    can.drawRightString(page_width - 40, page_height - 100, reshape_arabic("ظ‚ط³ظ… ط§ظ„ظ„ط؛ط© ظˆط§ظ„ط£ط¯ط¨ ط§ظ„ط¹ط±ط¨ظٹ"))
    
    # طھظƒط¨ظٹط± ط§ظ„ط³ظ†ط© ط§ظ„ط¬ط§ظ…ط¹ظٹط© ظˆط¥ط¨ط±ط§ط² ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©
    can.setFont(ARABIC_FONT_BOLD, 14)
    can.drawString(40, page_height - 100, reshape_arabic("ط§ظ„ط³ظ†ط© ط§ظ„ط¬ط§ظ…ط¹ظٹط©: 2026-2027"))
    can.setFont(ARABIC_FONT_BOLD, 12)
    can.drawRightString(page_width - 40, page_height - 118, reshape_arabic(f"ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©: {form_code}"))

    can.setFont(ARABIC_FONT_BOLD, 26)
    can.drawCentredString(center_x, page_height - 155, reshape_arabic("ط§ط³طھظ…ط§ط±ط© طھط³ط¬ظٹظ„ ظ…ط°ظƒط±ط© ظ…ط§ط³طھط±"))
    
    can.setFont(ARABIC_FONT_BOLD, 15)
    can.drawCentredString(center_x, page_height - 188, reshape_arabic(f"ط§ظ„طھط®طµطµ: {specialty}"))

    can.setFont(ARABIC_FONT_BOLD, 16)
    can.drawCentredString(center_x, page_height - 218, reshape_arabic(f"ط§ظ„ط£ط³طھط§ط° ط§ظ„ظ…ط´ط±ظپ: {teacher_name}"))
    
    # طھظƒط¨ظٹط± ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط© ظˆط¥ط¯ط±ط§ط¬ ط³ط·ط± ظپط§ط±ط؛ ظ‚ط¨ظ„ظ‡ ظˆط¨ط¹ط¯ظ‡
    can.setFont(ARABIC_FONT_BOLD, 18)
    can.drawCentredString(center_x, page_height - 250, reshape_arabic("ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©:"))
    
    rect_y = page_height - 335
    can.setLineWidth(1.5)
    can.rect(40, rect_y, page_width - 80, 68)
    
    can.setFont(ARABIC_FONT_BOLD, 17)
    can.drawCentredString(center_x, rect_y + 26, reshape_arabic(f"آ« {title} آ»"))

    # ط³ط·ط± ظپط§ط±ط؛ ط¨ط¹ط¯ ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط© ظ‚ط¨ظ„ ط§ظ„ط§ظ†طھظ‚ط§ظ„ ظ„ظ„ط·ط§ظ„ط¨
    y_st = page_height - 395
    can.setFont(ARABIC_FONT_BOLD, 13)
    
    s1_clean = str(st1_name).strip() if st1_name else ""
    r1_clean = str(st1_reg).strip() if st1_reg else ""
    str_st1 = f"ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط£ظˆظ„: {s1_clean}" + (f" (ط±ظ‚ظ… ط§ظ„طھط³ط¬ظٹظ„: {r1_clean})" if r1_clean else "")
    can.drawRightString(page_width - 50, y_st, reshape_arabic(str_st1))
    
    s2_clean = str(st2_name).strip() if st2_name else ""
    r2_clean = str(st2_reg).strip() if st2_reg else ""
    if s2_clean and s2_clean.lower() not in ["", "---", "nan", "none", "null", "ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ"]:
        str_st2 = f"ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط«ط§ظ†ظٹ: {s2_clean}" + (f" (ط±ظ‚ظ… ط§ظ„طھط³ط¬ظٹظ„: {r2_clean})" if r2_clean else "")
        can.drawRightString(page_width - 50, y_st - 28, reshape_arabic(str_st2))

    # ط§ظ„طھظˆظ‚ظٹط¹ط§طھ: ط±ط¦ظٹط³ ط§ظ„ظ‚ط³ظ… ط¨ط¬ط§ظ†ط¨ ط§ظ„ظ…ط´ط±ظپ ظپظٹ ظ†ظپط³ ط§ظ„ط³ط·ط±طŒ ط«ظ… طھظˆظ‚ظٹط¹ ظ…ط³ط¤ظˆظ„ ط§ظ„ط´ط¹ط¨ط© ط¨ط­ط¬ظ… ظ…ظ„ط§ط¦ظ…
    y_sig1 = y_st - 80
    can.setFont(ARABIC_FONT_BOLD, 12)
    can.drawRightString(page_width - 50, y_sig1, reshape_arabic("طھظˆظ‚ظٹط¹ ط§ظ„ظ…ط´ط±ظپ (QR Code):"))
    can.drawString(center_x - 40, y_sig1, reshape_arabic("طھظˆظ‚ظٹط¹ ط±ط¦ظٹط³ ط§ظ„ظ‚ط³ظ…:"))

    qr_buf = generate_qr_code_image(qr_code_str)
    can.drawImage(ImageReader(qr_buf), page_width - 160, y_sig1 - 90, width=70, height=70)

    sign1_b = get_image_bytes("sign1.png")
    if sign1_b:
        try:
            can.drawImage(ImageReader(BytesIO(sign1_b)), center_x - 60, y_sig1 - 75, width=95, height=48, mask='auto')
        except Exception:
            pass

    y_sig2 = y_sig1 - 95
    can.setFont(ARABIC_FONT_BOLD, 14)
    can.drawCentredString(center_x, y_sig2, reshape_arabic("طھظˆظ‚ظٹط¹ ظ…ط³ط¤ظˆظ„ ط§ظ„ط´ط¹ط¨ط©:"))

    sign_file = "sign2.png" if "ظ„ط³ط§ظ†ظٹط§طھ" in str(specialty) else "sign3.png"
    sign_b = get_image_bytes(sign_file)
    if sign_b:
        try:
            can.drawImage(ImageReader(BytesIO(sign_b)), center_x - 50, y_sig2 - 65, width=100, height=50, mask='auto')
        except Exception:
            pass

    can.setFont(ARABIC_FONT_BOLD, 12)
    can.drawCentredString(center_x, 35, reshape_arabic("ط§ظ„ط³ظ†ط© ط§ظ„ط¬ط§ظ…ط¹ظٹط©: 2026-2027"))

    can.save()
    packet.seek(0)
    return packet.getvalue()

# ط¯ط§ظ„ط© طھظˆظ„ظٹط¯ ط¥ظپط§ط¯ط© طھط£ط·ظٹط± ط§ظ„ظ…ط°ظƒط±ط§طھ ط§ظ„ظ…ط­ط³ظ†ط© ط¨ط§ظ„ظƒط§ظ…ظ„
def generate_supervision_attestation_pdf(teacher_name, df_teacher_memos):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=30, 
        leftMargin=30, 
        topMargin=20, 
        bottomMargin=20
    )
    
    header_style = ParagraphStyle('HeaderStyle', fontName=ARABIC_FONT_BOLD, fontSize=13, alignment=TA_CENTER, leading=19)
    intro_style = ParagraphStyle('IntroStyle', fontName=ARABIC_FONT, fontSize=13, alignment=TA_CENTER, leading=22)
    teacher_style = ParagraphStyle('TeacherStyle', fontName=ARABIC_FONT_BOLD, fontSize=16, alignment=TA_CENTER, leading=24)
    cell_style = ParagraphStyle('TableCell', fontName=ARABIC_FONT, fontSize=11, alignment=TA_CENTER, leading=16)
    header_cell_style = ParagraphStyle('HeaderCell', fontName=ARABIC_FONT_BOLD, fontSize=12, alignment=TA_CENTER, textColor=colors.white)

    story = []
    attestation_code = get_next_attestation_number(teacher_name)
    
    # طھط­ط³ظٹظ† ط§ظ„طھط±ظˆظٹط³ط© ظˆط±ظ‚ظ… ط§ظ„ط¥ظپط§ط¯ط© ظپظٹ ط§ظ„ظ‡ط§ظ…ط´ ط§ظ„ط£ط¹ظ„ظ‰ ط¬ظ‡ط© ط§ظ„ظٹظ…ظٹظ† ظ…ظ‚ط§ط¨ظ„ط§ظ‹ ظ„ظ€ ظ‚ط³ظ… ط§ظ„ظ„ط؛ط© ظˆط§ظ„ط£ط¯ط¨ ط§ظ„ط¹ط±ط¨ظٹ
    def on_first_page(can, doc):
        page_width, page_height = letter
        draw_header_icons(can, page_width, page_height)
        can.setFont(ARABIC_FONT_BOLD, 12)
        can.drawRightString(page_width - 35, page_height - 30, reshape_arabic(f"ط±ظ‚ظ… ط§ظ„ط¥ظپط§ط¯ط©: {attestation_code}"))
        can.drawRightString(page_width - 35, page_height - 45, reshape_arabic("ظ‚ط³ظ… ط§ظ„ظ„ط؛ط© ظˆط§ظ„ط£ط¯ط¨ ط§ظ„ط¹ط±ط¨ظٹ"))
        
        # ط±ط³ظ… ط§ظ„ط¥ط·ط§ط± ط§ظ„ظ…ط­ظٹط· ط§ظ„ظƒط§ظ…ظ„
        can.setLineWidth(1.5)
        can.rect(18, 18, page_width - 36, page_height - 36)

    story.append(Paragraph(reshape_arabic("ط§ظ„ط¬ظ…ظ‡ظˆط±ظٹط© ط§ظ„ط¬ط²ط§ط¦ط±ظٹط© ط§ظ„ط¯ظٹظ…ظ‚ط±ط§ط·ظٹط© ط§ظ„ط´ط¹ط¨ظٹط©"), header_style))
    story.append(Paragraph(reshape_arabic("ظˆط²ط§ط±ط© ط§ظ„طھط¹ظ„ظٹظ… ط§ظ„ط¹ط§ظ„ظٹ ظˆط§ظ„ط¨ط­ط« ط§ظ„ط¹ظ„ظ…ظٹ"), header_style))
    story.append(Paragraph(reshape_arabic("ط¬ط§ظ…ط¹ط© ط§ظ„ظˆط§ط¯ظٹ - ظƒظ„ظٹط© ط§ظ„ط¢ط¯ط§ط¨ ظˆط§ظ„ظ„ط؛ط§طھ"), ParagraphStyle('UnivStyle', fontName=ARABIC_FONT_BOLD, fontSize=14, alignment=TA_CENTER, leading=20)))
    story.append(Spacer(1, 15))

    # ط¥ظ†ط²ط§ظ„ ط¥ظپط§ط¯ط© طھط£ط·ظٹط± ط¨ط³ط·ط±
    story.append(Spacer(1, 15))
    title_text = Paragraph(reshape_arabic("ط¥ظپط§ط¯ط© طھط£ط·ظٹط± ظ…ط°ظƒط±ط§طھ ظ…ط§ط³طھط±"), ParagraphStyle('AttTitle', fontName=ARABIC_FONT_BOLD, fontSize=22, alignment=TA_CENTER, textColor=colors.HexColor('#0f172a')))
    title_table = Table([[title_text]], colWidths=[530])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
    ]))
    story.append(title_table)
    
    # ط¥ظ†ط²ط§ظ„ ط§ظ„ظپظ‚ط±ط© ط§ظ„ظ†طµظٹط© ط¨ط³ط·ط±
    story.append(Spacer(1, 20))

    # ط§ظ„طھط±طھظٹط¨ ظˆط§ظ„ط£ط³ط·ط± ط§ظ„ظ…ط·ظ„ظˆط¨ط© ظ„ط¯ظٹط¨ط§ط¬ط© ط§ظ„ط¥ظپط§ط¯ط©
    line1 = reshape_arabic("ظٹظپظٹط¯ ط§ظ„ط³ظٹط¯ ط±ط¦ظٹط³ ظ‚ط³ظ… ط§ظ„ظ„ط؛ط© ظˆط§ظ„ط£ط¯ط¨ ط§ظ„ط¹ط±ط¨ظٹ ط£ظ† ط§ظ„ط£ط³طھط§ط°(ط©)")
    line2 = f"<b>{reshape_arabic(teacher_name)}</b>"
    line3 = reshape_arabic("طھظ€/ظ€طھط´ط±ظپ ط¹ظ„ظ‰ ظ…ط°ظƒط±ط§طھ ظ…ط§ط³طھط± ط®ظ„ط§ظ„ ط§ظ„ط³ظ†ط© ط§ظ„ط¬ط§ظ…ط¹ظٹط© 2026-2027طŒ ظƒظ…ط§ ظ‡ظˆ ظ…ط¨ظٹظ† ط£ط¯ظ†ط§ظ‡")

    story.append(Paragraph(line1, intro_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(line2, teacher_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(line3, intro_style))
    story.append(Spacer(1, 18))

    qr_memos_info = f"ط¥ظپط§ط¯ط© طھط£ط·ظٹط± ظ…ط°ظƒط±ط§طھ ظ…ط§ط³طھط±\nط±ظ‚ظ… ط§ظ„ط¥ظپط§ط¯ط©: {attestation_code}\nط§ظ„ط£ط³طھط§ط° ط§ظ„ظ…ط´ط±ظپ: {teacher_name}\nط¹ط¯ط¯ ط§ظ„ظ…ط°ظƒط±ط§طھ: {len(df_teacher_memos)}\nطھط§ط±ظٹط® ط§ظ„ط¥طµط¯ط§ط±: {datetime.now().strftime('%Y-%m-%d')}"

    primary_specialty = "ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©"
    if not df_teacher_memos.empty:
        raw_headers = ["ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©", "ط§ظ„طھط®طµطµ", "ط§ظ„ط±ظ‚ظ…"]
        table_data = [[Paragraph(reshape_arabic(h), header_cell_style) for h in raw_headers]]

        spec_col = [c for c in df_teacher_memos.columns if "طھط®طµطµ" in c or "ط§ظ„طھط®طµطµ" in c]
        spec_col_name = spec_col[0] if spec_col else "طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨"
        
        primary_specialty = str(df_teacher_memos.iloc[0].get(spec_col_name, "ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©")).strip()

        for idx, (_, row) in enumerate(df_teacher_memos.iterrows(), 1):
            memo_title = str(row.get("ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©", "")).strip()
            memo_spec = str(row.get(spec_col_name, "")).strip()
            qr_memos_info += f"\n{idx}. {memo_title} ({memo_spec})"

            row_cells = [
                Paragraph(reshape_arabic(memo_title), cell_style),
                Paragraph(reshape_arabic(memo_spec), cell_style),
                Paragraph(str(idx), cell_style)
            ]
            table_data.append(row_cells)

        t = Table(table_data, colWidths=[335, 160, 35])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

    story.append(Spacer(1, 40))
    curr_date_str = datetime.now().strftime("%Y/%m/%d")
    story.append(Paragraph(reshape_arabic(f"ط­ط±ط± ط¨ط§ظ„ظˆط§ط¯ظٹ ظپظٹ: {curr_date_str}"), ParagraphStyle('DateStyle', fontName=ARABIC_FONT_BOLD, fontSize=13, alignment=TA_CENTER)))
    story.append(Spacer(1, 15))

    # طھظƒط¨ظٹط± ط­ط¬ظ… ظ…ط³ط¤ظˆظ„ ط§ظ„ط´ط¹ط¨ط© ظˆط±ط¦ظٹط³ ط§ظ„ظ‚ط³ظ… ظˆط§ظ„ط£ط®طھط§ظ… ظˆط§ظ„ط¥ظ…ط¶ط§ط،ط§طھ
    sign1_img = make_reportlab_image("sign1.png", width=110, height=55)
    sign1_element = sign1_img if sign1_img else Paragraph("", intro_style)

    sign_file = "sign2.png" if "ظ„ط³ط§ظ†ظٹط§طھ" in primary_specialty else "sign3.png"
    sign_dept_img = make_reportlab_image(sign_file, width=110, height=55)
    sign_dept_element = sign_dept_img if sign_dept_img else Paragraph("", intro_style)

    qr_att_buf = generate_qr_code_image(qr_memos_info)
    qr_img = RLImage(qr_att_buf, width=75, height=75)
    
    sig_table_data = [
        [
            Paragraph(reshape_arabic("ط±ط¦ظٹط³ ط§ظ„ظ‚ط³ظ…"), ParagraphStyle('SigLeft', fontName=ARABIC_FONT_BOLD, fontSize=15, alignment=TA_CENTER)),
            Paragraph(reshape_arabic("ط±ظ…ط² ط§ظ„طھط­ظ‚ظ‚ (QR Code)"), ParagraphStyle('SigCenter', fontName=ARABIC_FONT_BOLD, fontSize=11, alignment=TA_CENTER)),
            Paragraph(reshape_arabic("ظ…ط³ط¤ظˆظ„ ط§ظ„ط´ط¹ط¨ط©"), ParagraphStyle('SigRight', fontName=ARABIC_FONT_BOLD, fontSize=15, alignment=TA_CENTER))
        ],
        [
            sign1_element,
            qr_img,
            sign_dept_element
        ]
    ]
    sig_table = Table(sig_table_data, colWidths=[185, 160, 185])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sig_table)

    doc.build(story, onFirstPage=on_first_page)
    buffer.seek(0)
    return buffer.getvalue()

def generate_general_report_pdf(df_data, selected_specs, title_prefix="ط§ظ„طھظ‚ط±ظٹط± ط§ظ„ط¹ط§ظ…"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    
    header_style = ParagraphStyle('HeaderStyle', fontName=ARABIC_FONT_BOLD, fontSize=11, alignment=TA_CENTER, leading=16)
    title_style = ParagraphStyle('ReportTitle', fontName=ARABIC_FONT_BOLD, fontSize=14, alignment=TA_CENTER, leading=18, spaceAfter=15)
    cell_style = ParagraphStyle('TableCell', fontName=ARABIC_FONT, fontSize=9, alignment=TA_CENTER, leading=12)
    header_cell_style = ParagraphStyle('HeaderCell', fontName=ARABIC_FONT_BOLD, fontSize=10, alignment=TA_CENTER, textColor=colors.white)

    story = []
    
    def on_first_page(can, doc):
        page_width, page_height = letter
        draw_header_icons(can, page_width, page_height)

    story.append(Paragraph(reshape_arabic("ط§ظ„ط¬ظ…ظ‡ظˆط±ظٹط© ط§ظ„ط¬ط²ط§ط¦ط±ظٹط© ط§ظ„ط¯ظٹظ…ظ‚ط±ط§ط·ظٹط© ط§ظ„ط´ط¹ط¨ظٹط©"), header_style))
    story.append(Paragraph(reshape_arabic("ظˆط²ط§ط±ط© ط§ظ„طھط¹ظ„ظٹظ… ط§ظ„ط¹ط§ظ„ظٹ ظˆط§ظ„ط¨ط­ط« ط§ظ„ط¹ظ„ظ…ظٹ"), header_style))
    story.append(Paragraph(reshape_arabic("ط¬ط§ظ…ط¹ط© ط§ظ„ظˆط§ط¯ظٹ"), header_style))
    story.append(Paragraph(reshape_arabic("ظƒظ„ظٹط© ط§ظ„ط¢ط¯ط§ط¨ ظˆط§ظ„ظ„ط؛ط§طھ"), header_style))
    story.append(Paragraph(reshape_arabic("ظ‚ط³ظ… ط§ظ„ظ„ط؛ط© ظˆط§ظ„ط£ط¯ط¨ ط§ظ„ط¹ط±ط¨ظٹ"), header_style))
    story.append(Spacer(1, 10))

    spec_col = [c for c in df_data.columns if "طھط®طµطµ" in c or "ط§ظ„طھط®طµطµ" in c]
    spec_col_name = spec_col[0] if spec_col else "طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨"
    
    df_filtered = df_data[df_data[spec_col_name].isin(selected_specs)].copy() if (selected_specs and spec_col_name in df_data.columns) else df_data.copy()
    specs_str = " - ".join(selected_specs) if selected_specs else "ط¬ظ…ظٹط¹ ط§ظ„طھط®طµطµط§طھ"
    
    story.append(Paragraph(reshape_arabic(f"{title_prefix} ظ„طھط³ط¬ظٹظ„ط§طھ ظ…ط°ظƒط±ط§طھ ط§ظ„ظ…ط§ط³طھط±"), title_style))
    story.append(Paragraph(reshape_arabic(f"ط§ظ„ط³ظ†ط© ط§ظ„ط¬ط§ظ…ط¹ظٹط©: 2026-2027 | ط§ظ„طھط®طµطµط§طھ: {specs_str}"), header_style))
    story.append(Spacer(1, 15))

    if not df_filtered.empty:
        raw_headers = ["ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©", "ط§ظ„ط·ظ„ط¨ط© ط§ظ„ظ…ط³ط¬ظ„ظˆظ†", "ط§ظ„طھط®طµطµ", "ط§ظ„ظ…ط´ط±ظپ", "ظ…"]
        table_data = [[Paragraph(reshape_arabic(h), header_cell_style) for h in raw_headers]]

        for idx, (_, row) in enumerate(df_filtered.iterrows(), 1):
            c_col_st1 = [c for c in df_filtered.columns if "ط·ط§ظ„ط¨" in c and "1" in c]
            c_col_r1 = [c for c in df_filtered.columns if "طھط³ط¬ظٹظ„" in c and "1" in c]
            c_col_st2 = [c for c in df_filtered.columns if "ط·ط§ظ„ط¨" in c and "2" in c]
            c_col_r2 = [c for c in df_filtered.columns if "طھط³ط¬ظٹظ„" in c and "2" in c]

            st1_name = str(row.get(c_col_st1[0], '') if c_col_st1 else row.get('ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 1', '')).strip()
            st1_reg = str(row.get(c_col_r1[0], '') if c_col_r1 else row.get('ط±ظ‚ظ… طھط³ط¬ظٹظ„ 1', '')).strip()
            st1_str = f"{st1_name} ({st1_reg})" if st1_reg else st1_name

            st2_name = str(row.get(c_col_st2[0], '') if c_col_st2 else row.get('ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 2', '')).strip()
            st2_reg = str(row.get(c_col_r2[0], '') if c_col_r2 else row.get('ط±ظ‚ظ… طھط³ط¬ظٹظ„ 2', '')).strip()
            st2_str = f"{st2_name} ({st2_reg})" if (st2_name and st2_name.lower() not in ['---', 'nan', 'none', 'null', 'ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ']) else ''
            
            students_comb = f"{st1_str}\n{st2_str}" if st2_str else st1_str

            row_cells = [
                Paragraph(reshape_arabic(str(row.get("ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©", ""))), cell_style),
                Paragraph(reshape_arabic(students_comb), cell_style),
                Paragraph(reshape_arabic(str(row.get(spec_col_name, ""))), cell_style),
                Paragraph(reshape_arabic(str(row.get("ط§ط³ظ… ط§ظ„ط£ط³طھط§ط°", ""))), cell_style),
                Paragraph(str(idx), cell_style)
            ]
            table_data.append(row_cells)

        t = Table(table_data, colWidths=[150, 160, 100, 105, 25])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        story.append(t)
    else:
        story.append(Paragraph(reshape_arabic("ظ„ط§ طھظˆط¬ط¯ طھط³ط¬ظٹظ„ط§طھ ظ…ط·ط§ط¨ظ‚ط© ظ„ظ„طھط®طµطµط§طھ ط§ظ„ظ…ط®طھط§ط±ط©."), title_style))

    doc.build(story, onFirstPage=on_first_page)
    buffer.seek(0)
    return buffer.getvalue()

# --- 6. ط§ظ„ظˆط§ط¬ظ‡ط© ظˆطھطµظ…ظٹظ… ط§ظ„طھط·ط¨ظٹظ‚ ---
st.markdown("""
<style>
    html, body, [class*="css"], div[data-testid="stAppViewContainer"] {
        direction: rtl; text-align: right; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc;
    }
    .stSelectbox, .stTextInput, .stNumberInput, .stRadio, .stButton, .stDownloadButton, .stCheckbox { direction: rtl; text-align: right; }
    div[data-baseweb="select"] { direction: rtl; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #e2e8f0; padding: 8px; border-radius: 12px; }
    .stTabs [data-baseweb="tab"] { height: 48px; background-color: #ffffff; border-radius: 8px; color: #1e293b; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #1e3a8a !important; color: #ffffff !important; }
    .main-header { background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); color: white; padding: 24px; border-radius: 16px; text-align: center; margin-bottom: 20px; }
    .status-msg-success { background-color: #f0fdf4; border-right: 4px solid #22c55e; color: #15803d; padding: 16px; border-radius: 8px; font-weight: bold; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

visitor_count = update_and_get_visitor_count()

st.markdown(f"""
<div class="main-header">
    <h1 style="margin:0; font-size:2.2rem;">ًںژ“ ظ…ظ†طµط© ط¥ط¯ط§ط±ط© ظ…ط°ظƒط±ط§طھ ط§ظ„ظ…ط§ط³طھط± (ط§ظ„ط³ط­ط§ط¨ظٹط©)</h1>
    <p style="margin:5px 0 0 0; font-size:1.1rem; opacity:0.9;">ظ‚ط³ظ… ط§ظ„ظ„ط؛ط© ظˆط§ظ„ط£ط¯ط¨ ط§ظ„ط¹ط±ط¨ظٹ - ظƒظ„ظٹط© ط§ظ„ط¢ط¯ط§ط¨ ظˆط§ظ„ظ„ط؛ط§طھ - ط¬ط§ظ…ط¹ط© ط§ظ„ظˆط§ط¯ظٹ</p>
    <div style="margin-top:10px; font-size:0.95rem; background:rgba(255,255,255,0.15); display:inline-block; padding:4px 15px; border-radius:20px;">
        ًں‘پï¸ڈ ط¥ط¬ظ…ط§ظ„ظٹ ط¹ط¯ط¯ ط§ظ„ط²ظٹط§ط±ط§طھ: <b>{visitor_count}</b>
    </div>
</div>
""", unsafe_allow_html=True)

tab_teacher, tab_spec_admin, tab_dept_admin = st.tabs([
    "ًں‘¨â€چًںڈ« ظپط¶ط§ط، ط§ظ„ط£ط³طھط§ط°", 
    "ًں‘¨â€چًں’¼ ظپط¶ط§ط، ظ…ط³ط¤ظˆظ„ظٹ ط§ظ„طھط®طµطµط§طھ", 
    "ًںڈ›ï¸ڈ ظپط¶ط§ط، ظ…ط³ط¤ظˆظ„ظژظٹ ط§ظ„ط´ط¹ط¨طھظٹظ†"
])

# ==========================================
# 1- ظپط¶ط§ط، ط§ظ„ط£ط³طھط§ط°
# ==========================================
with tab_teacher:
    if 'teacher_logged_in' not in st.session_state:
        st.session_state.teacher_logged_in = False
        st.session_state.current_teacher = ""

    t_sub_tab1, t_sub_tab2, t_sub_tab_edit, t_sub_tab_registered, t_sub_tab3, t_sub_tab4, t_sub_tab5 = st.tabs([
        "ًں”گ ط§ظ„ط¯ط®ظˆظ„ ط¥ظ„ظ‰ ط­ط³ط§ط¨ظٹ", 
        "ًں“‌ طھط³ط¬ظٹظ„ ظ…ط°ظƒط±ط© ظ…ط§ط³طھط±", 
        "âœڈï¸ڈ طھطµط­ظٹط­/طھط¹ط¯ظٹظ„ طھط³ط¬ظٹظ„",
        "ًں“ڑ ط§ظ„ط¹ظ†ط§ظˆظٹظ† ط§ظ„ظ…ط³ط¬ظ„ط© ظˆط§ظ„طھط­ظ…ظٹظ„",
        "ًں“© ط·ظ„ط¨ طھط¹ط¯ظٹظ„ ط¹ظ†ظˆط§ظ†",
        "ًں“ٹ ظ…طھط§ط¨ط¹ط© ط·ظ„ط¨ط§طھ ط§ظ„طھط¹ط¯ظٹظ„",
        "ًں“œ ط¥ظپط§ط¯ط© طھط£ط·ظٹط± ط§ظ„ظ…ط°ظƒط±ط§طھ"
    ])

    with t_sub_tab1:
        st.subheader("طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ظ„ظ„ط£ط³طھط§ط°")
        df_teachers = load_data_from_sheet(SHEET_TEACHERS)
        
        if st.session_state.teacher_logged_in:
            st.markdown(f"""
            <div class="status-msg-success">
                ط£ط³طھط§ط°ظ†ط§ ط§ظ„ظ…ط­طھط±ظ… ({st.session_state.current_teacher}) ظ„ظ‚ط¯ طھظ… طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ط¨ظ†ط¬ط§ط­.
            </div>
            """, unsafe_allow_html=True)
            if st.button("ًں”´ طھط³ط¬ظٹظ„ ط§ظ„ط®ط±ظˆط¬", key="btn_logout_teacher_v55"):
                st.session_state.clear()
                st.rerun()
        else:
            name_col, pass_col = None, None
            if not df_teachers.empty:
                for c in df_teachers.columns:
                    if "ط§ظ„ط§ط³ظ…" in c or "ط§ظ„ظ„ظ‚ط¨" in c: name_col = c
                    if "ظƒظ„ظ…ط©" in c or "ط§ظ„ظ…ط±ظˆط±" in c: pass_col = c
            
            if df_teachers.size > 0 and name_col:
                teacher_list = df_teachers[name_col].dropna().unique().tolist()
                selected_teacher = st.selectbox("ط§ط®طھط± ط§ط³ظ… ط§ظ„ط£ط³طھط§ط°:", ["-- ط§ط®طھط± ط§ط³ظ…ظƒ --"] + teacher_list, key="sb_t_login_v55")
                input_pass = st.text_input("ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط±:", type="password", key="inp_t_pass_v55")
                
                if st.button("ط§ظ„ط¯ط®ظˆظ„ ط¥ظ„ظ‰ ط­ط³ط§ط¨ظٹ ًںڑ€", key="btn_t_login_v55"):
                    if selected_teacher != "-- ط§ط®طھط± ط§ط³ظ…ظƒ --":
                        real_pass = df_teachers[df_teachers[name_col] == selected_teacher][pass_col].values if pass_col else []
                        if str(input_pass) == MASTER_SUPER_PASS or (len(real_pass) > 0 and str(real_pass[0]) == str(input_pass)):
                            st.session_state.teacher_logged_in = True
                            st.session_state.current_teacher = selected_teacher.strip()
                            st.session_state.saved_successfully = False
                            st.toast("âœ… طھظ… طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ط¨ظ†ط¬ط§ط­!")
                            st.rerun()
                        else:
                            st.error("â‌Œ ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط؛ظٹط± طµط­ظٹط­ط©!")

    with t_sub_tab2:
        if not st.session_state.teacher_logged_in:
            st.info("âڑ ï¸ڈ ظٹط±ط¬ظ‰ طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ط£ظˆظ„ط§ظ‹ ظ…ظ† ظ„ط³ط§ظ† 'ط§ظ„ط¯ط®ظˆظ„ ط¥ظ„ظ‰ ط­ط³ط§ط¨ظٹ'.")
        else:
            current_teacher_name = st.session_state.current_teacher.strip()
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            
            t_col_name = [c for c in df_final.columns if "ط£ط³طھط§ط°" in c or "ط§ط³طھط§ط°" in c]
            teacher_col = t_col_name[0] if t_col_name else "ط§ط³ظ… ط§ظ„ط£ط³طھط§ط°"

            teacher_registrations_count = 0
            if not df_final.empty and teacher_col in df_final.columns:
                teacher_registrations_count = len(df_final[df_final[teacher_col].astype(str).str.strip() == current_teacher_name])

            if st.session_state.get('saved_successfully', False):
                st.success(f"ط£ط³طھط§ط°ظ†ط§ ط§ظ„ظƒط±ظٹظ…طŒ ظ„ظ‚ط¯ طھظ… -ط¨ظ†ط¬ط§ط­- طھط³ط¬ظٹظ„ ظ…ط°ظƒط±طھظƒظ… ظˆطھظˆظ„ظٹط¯ ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط© ({st.session_state.last_form_code}) ظˆظƒظˆط¯ ط§ظ„ط§ط¹طھظ…ط§ط¯ ط§ظ„ط¢ظ„ظٹ (QR Code).")
                
                pdf_data = generate_pdf_document(
                    st.session_state.last_form_code,
                    current_teacher_name, 
                    st.session_state.last_spec, 
                    st.session_state.last_st1_n, st.session_state.last_st1_r,
                    st.session_state.last_st2_n, st.session_state.last_st2_r,
                    st.session_state.last_title,
                    qr_code_str=st.session_state.last_qr_str
                )
                
                st.download_button("ًں–¨ï¸ڈ طھط­ظ…ظٹظ„ ط§ط³طھظ…ط§ط±ط© ط§ظ„طھط³ط¬ظٹظ„ ط§ظ„ظ…ط¹طھظ…ط¯ط© ط¨ط§ظ„ظƒظˆط¯ط¨ط§ط± (PDF)", data=pdf_data, file_name=f"ط§ط³طھظ…ط§ط±ط©_{current_teacher_name}.pdf", mime="application/pdf", key="dl_pdf_v55")
                
                if st.button("ًں“‌ طھط³ط¬ظٹظ„ ظ…ط°ظƒط±ط© ط£ط®ط±ظ‰", key="reset_reg_v55"):
                    if teacher_registrations_count >= 3:
                        st.error(f"â‌Œ ط§ظ„ط£ط³طھط§ط° ط§ظ„ظپط§ط¶ظ„ {current_teacher_name}طŒ ظ„ظ‚ط¯ ط¨ظ„ط؛طھ ط§ظ„ط­ط¯ ط§ظ„ط£ظ‚طµظ‰ ط§ظ„ظ…ط³ظ…ظˆط­ ط¨ظ‡ ظ„طھط³ط¬ظٹظ„ ط§ظ„ظ…ط°ظƒط±ط§طھ (03 ظ…ط°ظƒط±ط§طھ).")
                    else:
                        st.session_state.saved_successfully = False
                        st.rerun()
            elif teacher_registrations_count >= 3:
                st.error(f"â‌Œ ط§ظ„ط£ط³طھط§ط° ط§ظ„ظپط§ط¶ظ„ {current_teacher_name}طŒ ظ„ظ‚ط¯ ط¨ظ„ط؛طھ ط§ظ„ط­ط¯ ط§ظ„ط£ظ‚طµظ‰ ط§ظ„ظ…ط³ظ…ظˆط­ ط¨ظ‡ ظ„طھط³ط¬ظٹظ„ ط§ظ„ظ…ط°ظƒط±ط§طھ (03 ظ…ط°ظƒط±ط§طھ).")
            else:
                st.subheader(f"ظ…ط°ظƒط±ط§طھ ط§ظ„ط£ط³طھط§ط°: {current_teacher_name} (ط§ظ„ظ…ط³ط¬ظ„ط© ط­ط§ظ„ظٹط§ظ‹: {teacher_registrations_count} ظ…ظ† 3)")
                selected_spec = st.selectbox("ط§ط®طھط± ط§ظ„طھط®طµطµ:", SPECIALTIES, key="sb_spec_v55")
                df_students = load_data_from_sheet(SHEET_STUDENTS)

                students_options = []
                spec_col_map = {
                    "ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©": ("طھط®طµطµ ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©"),
                    "ط£ط¯ط¨ ط¹ط±ط¨ظٹ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±": ("طھط®طµطµ ط£ط¯ط¨ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ط£ط¯ط¨ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±"),
                    "ظ†ظ‚ط¯ ط­ط¯ظٹط« ظ…ط¹ط§طµط±": ("طھط®طµطµ ظ†ظ‚ط¯ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ظ†ظ‚ط¯ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±"),
                    "ط£ط¯ط¨ ط´ط¹ط¨ظٹ": ("طھط®طµطµ ط£ط¯ط¨ ط´ط¹ط¨ظٹ", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ط£ط¯ط¨ ط´ط¹ط¨ظٹ")
                }

                if not df_students.empty and selected_spec in spec_col_map:
                    n_col_target, r_col_target = spec_col_map[selected_spec]
                    n_col = [c for c in df_students.columns if n_col_target.replace(" ", "") in c.replace(" ", "") or n_col_target.replace(" ", "_") in c.replace(" ", "_")]
                    r_col = [c for c in df_students.columns if r_col_target.replace(" ", "") in c.replace(" ", "") or r_col_target.replace(" ", "_") in c.replace(" ", "_")]

                    if n_col and r_col:
                        for _, row in df_students.iterrows():
                            s_n = str(row[n_col[0]]).strip()
                            s_r = str(row[r_col[0]]).strip()
                            if s_n and s_n != 'nan':
                                students_options.append(f"{s_n} - {s_r}")

                col_s1, col_s2 = st.columns(2)
                with col_s1: st1 = st.selectbox("ط§ط®طھط± ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط£ظˆظ„ (ط¥ط¬ط¨ط§ط±ظٹ):", ["-- ط§ط®طھط± ط§ظ„ط·ط§ظ„ط¨ --"] + students_options, key="st1_v55")
                st2_opts = [s for s in students_options if s != st1]
                with col_s2: st2 = st.selectbox("ط§ط®طھط± ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط«ط§ظ†ظٹ (ط§ط®طھظٹط§ط±ظٹ):", ["-- ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ --"] + st2_opts, key="st2_v55")

                df_titles = load_data_from_sheet(SHEET_TITLES)
                available_titles = []
                if not df_titles.empty:
                    for i in range(0, len(df_titles.columns) - 1, 2):
                        tit_c = df_titles.columns[i]
                        tch_c = df_titles.columns[i+1]
                        matched = df_titles[df_titles[tch_c].astype(str).str.strip() == current_teacher_name]
                        if not matched.empty:
                            available_titles.extend(matched[tit_c].dropna().unique().tolist())

                selected_title_dropdown = st.selectbox("ط§ط®طھط± ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط© ط§ظ„ط®ط§طµط© ط¨ظƒ:", ["-- ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† --"] + available_titles, key="sb_title_v55")

                if st.button("ًں’¾ ط­ظپط¸ ظˆطھظˆظ‚ظٹط¹ ط§ظ„ط§ط³طھظ…ط§ط±ط© ط¢ظ„ظٹط§ظ‹ ط¨ط§ظ„ظ€ QR Code", key="btn_save_v55"):
                    if st1 != "-- ط§ط®طھط± ط§ظ„ط·ط§ظ„ط¨ --" and selected_title_dropdown != "-- ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† --":
                        st1_n = st1.split(" - ")[0].strip()
                        st1_r = st1.split(" - ")[1].strip() if " - " in st1 else ""
                        st2_n = st2.split(" - ")[0].strip() if st2 != "-- ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ --" else ""
                        st2_r = st2.split(" - ")[1].strip() if " - " in st2 and st2 != "-- ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ --" else ""

                        already_registered = False
                        if not df_final.empty:
                            c_col_st1 = [c for c in df_final.columns if "ط·ط§ظ„ط¨" in c and "1" in c]
                            c_col_st2 = [c for c in df_final.columns if "ط·ط§ظ„ط¨" in c and "2" in c]
                            reg_st1 = df_final[c_col_st1[0]].dropna().tolist() if c_col_st1 else []
                            reg_st2 = df_final[c_col_st2[0]].dropna().tolist() if c_col_st2 else []
                            all_reg_students = [str(s).strip() for s in reg_st1 + reg_st2 if str(s).strip()]
                            
                            if st1_n in all_reg_students or (st2_n and st2_n in all_reg_students):
                                already_registered = True

                        if already_registered:
                            st.error("â‌Œ طھظ†ط¨ظٹظ‡: ط£ط­ط¯ ط§ظ„ط·ط§ظ„ط¨ظٹظ† ط§ظ„ظ…ط®طھط§ط±ط© ظ…ط³ط¬ظ„ ط¨ط§ظ„ظپط¹ظ„ ظپظٹ ظ…ط°ظƒط±ط© ط£ط®ط±ظ‰ ط¨ط§ظ„ظ‚ط§ط¹ط¯ط©!")
                        else:
                            f_code = generate_form_code()
                            st2_str_qr = f"\nط§ظ„ط·ط§ظ„ط¨ 2: {st2_n} ({st2_r})" if st2_n else "\nط§ظ„ط·ط§ظ„ط¨ 2: ظ„ط§ ظٹظˆط¬ط¯"
                            qr_content = f"ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©: {f_code}\nط§ظ„ظ…ط´ط±ظپ: {current_teacher_name}\nط§ظ„طھط®طµطµ: {selected_spec}\nط§ظ„ط¹ظ†ظˆط§ظ†: {selected_title_dropdown.strip()}\nط§ظ„ط·ط§ظ„ط¨ 1: {st1_n} ({st1_r}){st2_str_qr}\nطھط§ط±ظٹط® ط§ظ„ط§ط¹طھظ…ط§ط¯: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

                            summary_data = {
                                "ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©": f_code,
                                "ط§ط³ظ… ط§ظ„ط£ط³طھط§ط°": current_teacher_name,
                                "طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨": selected_spec,
                                "ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 1": st1_n,
                                "ط±ظ‚ظ… طھط³ط¬ظٹظ„ 1": st1_r,
                                "ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 2": st2_n,
                                "ط±ظ‚ظ… طھط³ط¬ظٹظ„ 2": st2_r,
                                "ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©": selected_title_dropdown.strip(),
                                "طھط§ط±ظٹط® ط§ظ„طھط³ط¬ظٹظ„": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "ظƒظˆط¯ ط§ظ„طھط­ظ‚ظ‚": qr_content
                            }
                            if save_data_to_sheet(summary_data, SHEET_FINAL_REGISTRATIONS):
                                st.session_state.saved_successfully = True
                                st.session_state.last_form_code = f_code
                                st.session_state.last_spec = selected_spec
                                st.session_state.last_st1_n = st1_n
                                st.session_state.last_st1_r = st1_r
                                st.session_state.last_st2_n = st2_n
                                st.session_state.last_st2_r = st2_r
                                st.session_state.last_title = selected_title_dropdown
                                st.session_state.last_qr_str = qr_content
                                st.toast("âœ… طھظ… ط­ظپط¸ ط¹ظ†ظˆط§ظ† ظˆط§ط³طھظ…ط§ط±ط© ط§ظ„ظ…ط°ظƒط±ط© ط¨ظ†ط¬ط§ط­ ظپظٹ ظ‚ط§ط¹ط¯ط© ط§ظ„ط¨ظٹط§ظ†ط§طھ!")
                                st.rerun()

    with t_sub_tab_edit:
        if st.session_state.teacher_logged_in:
            teacher_curr = str(st.session_state.current_teacher).strip()
            st.subheader("âœڈï¸ڈ طھطµط­ظٹط­ ط£ط®ط·ط§ط، ط§ظ„طھط³ط¬ظٹظ„")
            
            df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final_all.empty:
                t_col_name = [c for c in df_final_all.columns if "ط£ط³طھط§ط°" in c or "ط§ط³طھط§ط°" in c]
                if t_col_name:
                    my_reg = df_final_all[df_final_all[t_col_name[0]].astype(str).str.strip() == teacher_curr].copy()
                    if not my_reg.empty:
                        reg_titles = my_reg["ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©"].tolist() if "ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©" in my_reg.columns else []
                        selected_title_to_edit = st.selectbox("ط§ط®طھط± ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط© ظ„طھطµط­ظٹط­ظ‡ط§:", ["-- ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† --"] + reg_titles, key="sb_edit_title_select_v55")
                        
                        if selected_title_to_edit != "-- ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† --":
                            target_row = my_reg[my_reg["ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©"] == selected_title_to_edit].iloc[0]
                            st.info(f"ًں“چ **ط§ظ„ظ…ط¹ظ„ظˆظ…ط§طھ ط§ظ„ط­ط§ظ„ظٹط©:** ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©: `{target_row.get('ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©', '')}` | ط§ظ„طھط®طµطµ: `{target_row.get('طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨', '')}` | ط§ظ„ط¹ظ†ظˆط§ظ†: `{target_row.get('ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©', '')}`")
                            
                            edit_spec = st.selectbox("طھط¹ط¯ظٹظ„ ط§ظ„طھط®طµطµ:", SPECIALTIES, index=SPECIALTIES.index(target_row.get('طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨', SPECIALTIES[0])) if target_row.get('طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨') in SPECIALTIES else 0, key="sb_edit_spec_v55")
                            
                            df_titles = load_data_from_sheet(SHEET_TITLES)
                            available_titles = []
                            if not df_titles.empty:
                                for i in range(0, len(df_titles.columns) - 1, 2):
                                    tit_c = df_titles.columns[i]
                                    tch_c = df_titles.columns[i+1]
                                    matched = df_titles[df_titles[tch_c].astype(str).str.strip() == teacher_curr]
                                    if not matched.empty:
                                        available_titles.extend(matched[tit_c].dropna().unique().tolist())

                            curr_title = target_row.get('ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©', '')
                            if curr_title not in available_titles: available_titles.append(curr_title)

                            edit_title = st.selectbox("طھطµط­ظٹط­ ط§ط®طھظٹط§ط± ط§ظ„ط¹ظ†ظˆط§ظ†:", available_titles, index=available_titles.index(curr_title) if curr_title in available_titles else 0, key="sb_edit_title_v55")
                            
                            df_students = load_data_from_sheet(SHEET_STUDENTS)
                            students_options = []
                            spec_col_map = {
                                "ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©": ("طھط®طµطµ ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©"),
                                "ط£ط¯ط¨ ط¹ط±ط¨ظٹ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±": ("طھط®طµطµ ط£ط¯ط¨ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ط£ط¯ط¨ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±"),
                                "ظ†ظ‚ط¯ ط­ط¯ظٹط« ظ…ط¹ط§طµط±": ("طھط®طµطµ ظ†ظ‚ط¯ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ظ†ظ‚ط¯ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±"),
                                "ط£ط¯ط¨ ط´ط¹ط¨ظٹ": ("طھط®طµطµ ط£ط¯ط¨ ط´ط¹ط¨ظٹ", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ط£ط¯ط¨ ط´ط¹ط¨ظٹ")
                            }

                            if not df_students.empty and edit_spec in spec_col_map:
                                n_col_target, r_col_target = spec_col_map[edit_spec]
                                n_col = [c for c in df_students.columns if n_col_target.replace(" ", "") in c.replace(" ", "") or n_col_target.replace(" ", "_") in c.replace(" ", "_")]
                                r_col = [c for c in df_students.columns if r_col_target.replace(" ", "") in c.replace(" ", "") or r_col_target.replace(" ", "_") in c.replace(" ", "_")]
                                if n_col and r_col:
                                    for _, row in df_students.iterrows():
                                        s_n = str(row[n_col[0]]).strip()
                                        s_r = str(row[r_col[0]]).strip()
                                        if s_n and s_n != 'nan': students_options.append(f"{s_n} - {s_r}")

                            c_col_st1 = [c for c in target_row.index if "ط·ط§ظ„ط¨" in c and "1" in c]
                            c_col_r1 = [c for c in target_row.index if "طھط³ط¬ظٹظ„" in c and "1" in c]
                            c_col_st2 = [c for c in target_row.index if "ط·ط§ظ„ط¨" in c and "2" in c]
                            c_col_r2 = [c for c in target_row.index if "طھط³ط¬ظٹظ„" in c and "2" in c]

                            st1_v = target_row.get(c_col_st1[0], '') if c_col_st1 else target_row.get('ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 1', '')
                            r1_v = target_row.get(c_col_r1[0], '') if c_col_r1 else target_row.get('ط±ظ‚ظ… طھط³ط¬ظٹظ„ 1', '')
                            st2_v = target_row.get(c_col_st2[0], '') if c_col_st2 else target_row.get('ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 2', '')
                            r2_v = target_row.get(c_col_r2[0], '') if c_col_r2 else target_row.get('ط±ظ‚ظ… طھط³ط¬ظٹظ„ 2', '')

                            c_st1 = f"{st1_v} - {r1_v}"
                            c_st2 = f"{st2_v} - {r2_v}" if st2_v else "-- ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ --"

                            if c_st1 not in students_options and st1_v: students_options.append(c_st1)

                            col_es1, col_es2 = st.columns(2)
                            with col_es1: edit_st1 = st.selectbox("طھطµط­ظٹط­ ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط£ظˆظ„:", students_options, index=students_options.index(c_st1) if c_st1 in students_options else 0, key="sb_edit_st1_v55")
                            st2_edit_opts = ["-- ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ --"] + [s for s in students_options if s != edit_st1]
                            with col_es2: edit_st2 = st.selectbox("طھطµط­ظٹط­ ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط«ط§ظ†ظٹ:", st2_edit_opts, index=st2_edit_opts.index(c_st2) if c_st2 in st2_edit_opts else 0, key="sb_edit_st2_v55")

                            if st.button("ًں’¾ ط­ظپط¸ ط§ظ„طھطµط­ظٹط­ط§طھ ظˆط§ظ„طھط¹ط¯ظٹظ„ط§طھ", key="btn_save_edit_v55"):
                                existing_form_code = target_row.get('ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©', generate_form_code())
                                updated_data = {
                                    "ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©": existing_form_code,
                                    "ط§ط³ظ… ط§ظ„ط£ط³طھط§ط°": teacher_curr,
                                    "طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨": edit_spec,
                                    "ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 1": edit_st1.split(" - ")[0].strip(),
                                    "ط±ظ‚ظ… طھط³ط¬ظٹظ„ 1": edit_st1.split(" - ")[1].strip() if " - " in edit_st1 else "",
                                    "ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 2": edit_st2.split(" - ")[0].strip() if edit_st2 != "-- ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ --" else "",
                                    "ط±ظ‚ظ… طھط³ط¬ظٹظ„ 2": edit_st2.split(" - ")[1].strip() if " - " in edit_st2 and edit_st2 != "-- ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ --" else "",
                                    "ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©": edit_title.strip(),
                                    "طھط§ط±ظٹط® ط§ظ„طھط³ط¬ظٹظ„": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "ظƒظˆط¯ ط§ظ„طھط­ظ‚ظ‚": target_row.get('ظƒظˆط¯ ط§ظ„طھط­ظ‚ظ‚', '')
                                }
                                if update_registration_in_sheet(selected_title_to_edit, updated_data):
                                    st.success("âœ… طھظ… طھطµط­ظٹط­ ط¨ظٹط§ظ†ط§طھ ط§ظ„طھط³ط¬ظٹظ„ ظˆطھط­ط¯ظٹط« ط§ظ„ط´ظٹطھ ط³ط­ط§ط¨ظٹط§ظ‹ ط¨ظ†ط¬ط§ط­!")
                                    st.toast("âœ… طھظ…طھ ط¹ظ…ظ„ظٹط© طھط¹ط¯ظٹظ„ ط¨ظٹط§ظ†ط§طھ ط§ظ„طھط³ط¬ظٹظ„ ط¨ظ†ط¬ط§ط­!")
                                    st.rerun()

    with t_sub_tab_registered:
        if st.session_state.teacher_logged_in:
            teacher_curr = str(st.session_state.current_teacher).strip()
            st.subheader(f"ًں“ڑ ط§ظ„ط¹ظ†ط§ظˆظٹظ† ط§ظ„ظ…ط³ط¬ظ„ط© ظˆط§ظ„طھط­ظ…ظٹظ„ ط¨ط§ط³ظ… ط§ظ„ط£ط³طھط§ط°: {teacher_curr}")
            if st.button("ًں”„ طھط­ط¯ظٹط« ط§ظ„ظ‚ط§ط¦ظ…ط©", key="btn_ref_reg_v55"):
                st.cache_data.clear()
                st.toast("ًں”„ طھظ… طھط­ط¯ظٹط« ط§ظ„ظ‚ط§ط¦ظ…ط© ط¨ظ†ط¬ط§ط­!")
                st.rerun()

            df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final_all.empty:
                t_col_name = [c for c in df_final_all.columns if "ط£ط³طھط§ط°" in c or "ط§ط³طھط§ط°" in c]
                if t_col_name:
                    df_final_all["ط§ط³ظ…_ظ†ط¸ظٹظپ"] = df_final_all[t_col_name[0]].astype(str).str.strip()
                    my_reg = df_final_all[df_final_all["ط§ط³ظ…_ظ†ط¸ظٹظپ"] == teacher_curr].drop(columns=["ط§ط³ظ…_ظ†ط¸ظٹظپ"]).copy()
                    if not my_reg.empty:
                        my_reg.index = range(1, len(my_reg) + 1)
                        st.dataframe(my_reg, use_container_width=True)

                        st.markdown("---")
                        col_p1, col_del = st.columns(2)
                        with col_p1:
                            st.markdown("### ًں–¨ï¸ڈ ط·ط¨ط§ط¹ط© ظˆط§ط³طھط®ط±ط§ط¬ ط§ظ„ط§ط³طھظ…ط§ط±ط© ط§ظ„ظ…ط¹طھظ…ط¯ط©")
                            titles_list_for_print = my_reg["ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©"].dropna().tolist() if "ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©" in my_reg.columns else []
                            selected_title_to_print = st.selectbox("ط§ط®طھط± ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط© ظ„طھط­ظ…ظٹظ„ ط§ط³طھظ…ط§ط±طھظ‡ط§:", ["-- ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† --"] + titles_list_for_print, key="sb_print_reg_v55")
                            
                            if selected_title_to_print != "-- ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† --":
                                p_row = my_reg[my_reg["ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©"] == selected_title_to_print].iloc[0]
                                
                                c_col_st1 = [c for c in p_row.index if "ط·ط§ظ„ط¨" in c and "1" in c]
                                c_col_r1 = [c for c in p_row.index if "طھط³ط¬ظٹظ„" in c and "1" in c]
                                c_col_st2 = [c for c in p_row.index if "ط·ط§ظ„ط¨" in c and "2" in c]
                                c_col_r2 = [c for c in p_row.index if "طھط³ط¬ظٹظ„" in c and "2" in c]

                                st1_v = p_row.get(c_col_st1[0], '') if c_col_st1 else p_row.get('ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 1', '')
                                r1_v = p_row.get(c_col_r1[0], '') if c_col_r1 else p_row.get('ط±ظ‚ظ… طھط³ط¬ظٹظ„ 1', '')
                                st2_v = p_row.get(c_col_st2[0], '') if c_col_st2 else p_row.get('ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 2', '')
                                r2_v = p_row.get(c_col_r2[0], '') if c_col_r2 else p_row.get('ط±ظ‚ظ… طھط³ط¬ظٹظ„ 2', '')

                                spec_val = p_row.get("طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨", "")
                                title_val = p_row.get("ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©", "")
                                form_code_val = p_row.get("ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©", generate_form_code())
                                
                                st2_qr_txt = f"\nط§ظ„ط·ط§ظ„ط¨ 2: {st2_v} ({r2_v})" if st2_v else "\nط§ظ„ط·ط§ظ„ط¨ 2: ظ„ط§ ظٹظˆط¬ط¯"
                                qr_code_val = f"ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©: {form_code_val}\nط§ظ„ظ…ط´ط±ظپ: {teacher_curr}\nط§ظ„طھط®طµطµ: {spec_val}\nط§ظ„ط¹ظ†ظˆط§ظ†: {title_val}\nط§ظ„ط·ط§ظ„ط¨ 1: {st1_v} ({r1_v}){st2_qr_txt}\nطھط§ط±ظٹط® ط§ظ„ط§ط¹طھظ…ط§ط¯: {p_row.get('طھط§ط±ظٹط® ط§ظ„طھط³ط¬ظٹظ„', datetime.now().strftime('%Y-%m-%d %H:%M'))}"

                                pdf_bytes_row = generate_pdf_document(
                                    form_code_val,
                                    teacher_curr,
                                    spec_val,
                                    st1_v,
                                    r1_v,
                                    st2_v,
                                    r2_v,
                                    title_val,
                                    qr_code_str=qr_code_val
                                )

                                st.download_button(
                                    label=f"ًں–¨ï¸ڈ طھط­ظ…ظٹظ„ ط§ط³طھظ…ط§ط±ط© آ«{selected_title_to_print[:20]}...آ» ظ…ط¹ ط§ظ„ظƒظˆط¯ط¨ط§ط±",
                                    data=pdf_bytes_row,
                                    file_name=f"ط§ط³طھظ…ط§ط±ط©_{teacher_curr}.pdf",
                                    mime="application/pdf",
                                    key="btn_dl_registered_pdf_v55"
                                )

                        with col_del:
                            st.markdown("### ًں—‘ï¸ڈ ط¥ظ„ط؛ط§ط، ظˆط­ط°ظپ طھط³ط¬ظٹظ„ ظ…ط°ظƒط±ط©")
                            title_to_del = st.selectbox("ط§ط®طھط± ط§ظ„ظ…ط°ظƒط±ط© طھظ…ط§ظ…ط§ (ط­ط³ط¨ ط§ظ„ط¹ظ†ظˆط§ظ†):", ["-- ط§ط®طھط± ط§ظ„ظ…ط°ظƒط±ط© ظ„ظ„ط­ط°ظپ --"] + my_reg["ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©"].tolist(), key="sb_del_title_v55")
                            if title_to_del != "-- ط§ط®طھط± ط§ظ„ظ…ط°ظƒط±ط© ظ„ظ„ط­ط°ظپ --":
                                confirm_del = st.checkbox("ط£ط¤ظƒط¯ ط±ط؛ط¨طھظٹ ظپظٹ ط­ط°ظپ ظ‡ط°ظ‡ ط§ظ„ظ…ط°ظƒط±ط© ظ†ظ‡ط§ط¦ظٹط§ظ‹ ظ…ظ† ظ‚ط§ط¹ط¯ط© ط§ظ„ط¨ظٹط§ظ†ط§طھ âڑ ï¸ڈ", key="chk_confirm_del_v55")
                                if st.button("â‌Œ ط­ط°ظپ ط§ظ„ظ…ط°ظƒط±ط© ظ†ظ‡ط§ط¦ظٹط§ظ‹", key="btn_delete_reg_v55"):
                                    if confirm_del:
                                        if delete_registration_from_sheet(title_to_del):
                                            st.success("طھظ… ط­ط°ظپ ط§ظ„ظ…ط°ظƒط±ط© ظ†ظ‡ط§ط¦ظٹط§ظ‹ ظ…ظ† ظ‚ط§ط¹ط¯ط© ط§ظ„ط¨ظٹط§ظ†ط§طھ!")
                                            st.toast("ًں—‘ï¸ڈ طھظ… ط­ط°ظپ ط§ظ„طھط³ط¬ظٹظ„ ط¨ظ†ط¬ط§ط­!")
                                            st.rerun()

    with t_sub_tab3:
        if st.session_state.teacher_logged_in:
            st.subheader("ًں“© طھظ‚ط¯ظٹظ… ط·ظ„ط¨ طھط¹ط¯ظٹظ„ ط·ظپظٹظپ ط¹ظ„ظ‰ ط¹ظ†ظˆط§ظ† ظ…ط°ظƒط±ط©")
            teacher_curr = str(st.session_state.current_teacher).strip()
            
            selected_spec_mod = st.selectbox("ط§ط®طھط± ط§ظ„طھط®طµطµ ط§ظ„ظ…ط±طھط¨ط· ط¨ط§ظ„ط¹ظ†ظˆط§ظ†:", SPECIALTIES, key="sb_mod_spec_v55")
            
            df_titles = load_data_from_sheet(SHEET_TITLES)
            my_titles = []
            if not df_titles.empty:
                for i in range(0, len(df_titles.columns) - 1, 2):
                    tit_c = df_titles.columns[i]
                    tch_c = df_titles.columns[i+1]
                    matched = df_titles[df_titles[tch_c].astype(str).str.strip() == teacher_curr]
                    if not matched.empty:
                        my_titles.extend(matched[tit_c].dropna().unique().tolist())

            orig_t = st.selectbox("ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط£طµظ„ظٹ ط§ظ„ظ…ط±ط§ط¯ طھط¹ط¯ظٹظ„ظ‡:", ["-- ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط£طµظ„ظٹ --"] + my_titles, key="sb_mod_orig_dropdown_v55")
            new_t = st.text_input("ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط¬ط¯ظٹط¯ ط§ظ„ظ…ظ‚طھط±ط­:", key="inp_mod_new_v55")

            if st.button("ط¥ط±ط³ط§ظ„ ط·ظ„ط¨ ط§ظ„طھط¹ط¯ظٹظ„ ظ„ظ…ط³ط¤ظˆظ„ ط§ظ„طھط®طµطµ ًں“¤", key="btn_mod_send_v55"):
                if orig_t != "-- ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط£طµظ„ظٹ --" and new_t.strip():
                    new_mod = {
                        "ط§ظ„ط£ط³طھط§ط°": teacher_curr,
                        "ط§ظ„طھط®طµطµ": selected_spec_mod,
                        "ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط£طµظ„ظٹ": orig_t.strip(),
                        "ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط¬ط¯ظٹط¯": new_t.strip(),
                        "ط§ظ„ط­ط§ظ„ط©": "ظپظٹ ط§ظ„ط§ظ†طھط¸ط§ط±",
                        "ظ…ط¹ط§ظ„ط¬_ط§ظ„ط·ظ„ط¨": "ظپظٹ ط§ظ„ط§ظ†طھط¸ط§ط±"
                    }
                    if save_data_to_sheet(new_mod, SHEET_MOD_REQUESTS):
                        st.success("طھظ… ط¥ط±ط³ط§ظ„ ط§ظ„ط·ظ„ط¨ ظˆط­ظپط¸ظ‡ ط¨ظ†ط¬ط§ط­!")
                        st.toast("ًں“© طھظ… ط¥ط±ط³ط§ظ„ ط·ظ„ط¨ ط§ظ„طھط¹ط¯ظٹظ„ ط¨ظ†ط¬ط§ط­ ظ„ظ…ط³ط¤ظˆظ„ ط§ظ„طھط®طµطµ!")
                        st.rerun()

    with t_sub_tab4:
        if st.session_state.teacher_logged_in:
            st.subheader("ًں“ٹ ظ…طھط§ط¨ط¹ط© ط·ظ„ط¨ط§طھ ط§ظ„طھط¹ط¯ظٹظ„ ظˆط§ظ„ظ‚ط±ط§ط±ط§طھ ط§ظ„ظ…طھط®ط°ط©")
            teacher_curr = str(st.session_state.current_teacher).strip()
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            if not df_mod.empty:
                t_col = [c for c in df_mod.columns if "ط£ط³طھط§ط°" in c or "ط§ط³طھط§ط°" in c or "ط§ظ„ط£ط³طھط§ط°" in c]
                if t_col:
                    my_mods = df_mod[df_mod[t_col[0]].astype(str).str.strip() == teacher_curr].copy()
                    if not my_mods.empty:
                        my_mods.index = range(1, len(my_mods) + 1)
                        st.dataframe(my_mods, use_container_width=True)
                    else:
                        st.info("ظ„ط§ طھظˆط¬ط¯ ط·ظ„ط¨ط§طھ طھط¹ط¯ظٹظ„ ظ…ظ‚ط¯ظ…ط© ظ…ظ† ط·ط±ظپظƒ.")

    with t_sub_tab5:
        if st.session_state.teacher_logged_in:
            teacher_curr = str(st.session_state.current_teacher).strip()
            st.subheader("ًں“œ ط§ط³طھط®ط±ط§ط¬ ط¥ظپط§ط¯ط© طھط£ط·ظٹط± ظ…ط°ظƒط±ط§طھ ط§ظ„ظ…ط§ط³طھط±")
            
            attest_pass_input = st.text_input("ط£ط¯ط®ظ„ ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط§ظ„ط®ط§طµط© ط¨ط¥ظپط§ط¯ط© ط§ظ„طھط£ط·ظٹط± (20262027):", type="password", key="inp_attest_pass_v55")
            
            if st.button("ًں”‘ طھظپط¹ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ط¥ظ„ظ‰ ط¥ظپط§ط¯ط© ط§ظ„طھط£ط·ظٹط±", key="btn_enter_attestation_v55"):
                if attest_pass_input == ATTESTATION_PASS:
                    st.session_state.attest_unlocked = True
                    st.toast("ًں”“ طھظ… طھظپط¹ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ظˆط§ط³طھط®ط±ط§ط¬ ط§ظ„ط¥ظپط§ط¯ط© ط¨ظ†ط¬ط§ط­!")
                    st.success("طھظ… طھظپط¹ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ط¨ظ†ط¬ط§ط­!")
                else:
                    st.error("â‌Œ ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط؛ظٹط± طµط­ظٹط­ط©!")

            if st.session_state.get("attest_unlocked", False):
                df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
                if not df_final_all.empty:
                    t_col_name = [c for c in df_final_all.columns if "ط£ط³طھط§ط°" in c or "ط§ط³طھط§ط°" in c]
                    if t_col_name:
                        df_teacher_memos = df_final_all[df_final_all[t_col_name[0]].astype(str).str.strip() == teacher_curr].copy()
                        if not df_teacher_memos.empty:
                            pdf_attest_bytes = generate_supervision_attestation_pdf(teacher_curr, df_teacher_memos)
                            st.download_button(
                                label=f"ًں“œ طھط­ظ…ظٹظ„ ط¥ظپط§ط¯ط© طھط£ط·ظٹط± ط§ظ„ظ…ط°ظƒط±ط§طھ (PDF)",
                                data=pdf_attest_bytes,
                                file_name=f"ط¥ظپط§ط¯ط©_طھط£ط·ظٹط±_{teacher_curr}.pdf",
                                mime="application/pdf",
                                key="btn_dl_attestation_v55"
                            )
                        else:
                            st.info("ظ„ط§ طھظˆط¬ط¯ ظ…ط°ظƒط±ط§طھ ظ…ط³ط¬ظ„ط© ط¨ط§ط³ظ…ظƒ ط­ط§ظ„ظٹط§ظ‹ ظ„ط¥طµط¯ط§ط± ط§ظ„ط¥ظپط§ط¯ط©.")

# ==========================================
# 2- ظپط¶ط§ط، ظ…ط³ط¤ظˆظ„ظٹ ط§ظ„طھط®طµطµط§طھ
# ==========================================
with tab_spec_admin:
    if 'spec_admin_logged_in' not in st.session_state:
        st.session_state.spec_admin_logged_in = False
        st.session_state.current_spec_admin = ""

    adm_sub_login, adm_tab1, adm_tab2, adm_tab3, adm_tab_stats, adm_tab_print = st.tabs([
        "ًں”گ ط­ط³ط§ط¨ظٹ",
        "ًں“ڑ ط§ظ„ط¹ظ†ط§ظˆظٹظ† ظˆط­ط§ظ„طھظ‡ط§", 
        "ًں‘¥ ط§ظ„ط·ظ„ط¨ط© ط§ظ„ظ…ط³ط¬ظ„ظˆظ†", 
        "ًں“© ط·ظ„ط¨ط§طھ ط§ظ„طھط¹ط¯ظٹظ„", 
        "ًں“ˆ ط¥ط­طµط§ط¦ظٹط§طھ ط§ظ„طھط®طµطµ",
        "ًں–¨ï¸ڈ ط·ط¨ط§ط¹ط© ط§ظ„طھظ‚ط±ظٹط± ط§ظ„ط¹ط§ظ…"
    ])

    with adm_sub_login:
        if not st.session_state.spec_admin_logged_in:
            st.subheader("ط¯ط®ظˆظ„ ظ…ط³ط¤ظˆظ„ ط§ظ„طھط®طµطµ")
            col_admin_spec, col_admin_pass = st.columns(2)
            with col_admin_spec: admin_selected_spec = st.selectbox("ط§ط®طھط± ط§ظ„طھط®طµطµ ظ„ظ„ظ…ط³ط¤ظˆظ„:", SPECIALTIES, key="sb_admin_spec_login_v55")
            with col_admin_pass: admin_pass_input = st.text_input("ظƒظ„ظ…ط© ظ…ط±ظˆط± ط§ظ„ظ…ط³ط¤ظˆظ„:", type="password", key="admin_p_in_v55")

            if st.button("طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ظƒظ…ط³ط¤ظˆظ„ طھط®طµطµ ًںڑ€", key="btn_login_spec_admin_v55"):
                df_admins = load_data_from_sheet(SHEET_ADMINS)
                if str(admin_pass_input) == MASTER_SUPER_PASS:
                    st.session_state.spec_admin_logged_in = True
                    st.session_state.current_spec_admin = admin_selected_spec
                    st.toast("âœ… طھظ… طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ظƒظ…ط³ط¤ظˆظ„ طھط®طµطµ!")
                    st.rerun()
                elif not df_admins.empty:
                    spec_col = [c for c in df_admins.columns if "طھط®طµطµ" in c][0]
                    pass_col = [c for c in df_admins.columns if "ظƒظ„ظ…ط©" in c or "ظ…ط±ظˆط±" in c][0]
                    match = df_admins[df_admins[spec_col] == admin_selected_spec]
                    if not match.empty and str(match[pass_col].values[0]) == str(admin_pass_input):
                        st.session_state.spec_admin_logged_in = True
                        st.session_state.current_spec_admin = admin_selected_spec
                        st.toast("âœ… طھظ… طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ظƒظ…ط³ط¤ظˆظ„ طھط®طµطµ!")
                        st.rerun()
                    else:
                        st.error("ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط؛ظٹط± طµط­ظٹط­ط©!")
        else:
            st.markdown(f"""
            <div class="status-msg-success">
                ظ…ط±ط­ط¨ط§ظ‹ ط¨ظƒ ط£ط³طھط§ط°ظ†ط§ ط§ظ„ظ…ط­طھط±ظ…طŒ ظ…ط³ط¤ظˆظ„ طھط®طµطµ: <b>{st.session_state.current_spec_admin}</b>
            </div>
            """, unsafe_allow_html=True)
            if st.button("ًں”´ طھط³ط¬ظٹظ„ ط§ظ„ط®ط±ظˆط¬ ظƒظ…ط³ط¤ظˆظ„ طھط®طµطµ", key="btn_logout_spec_admin_v55"):
                st.session_state.spec_admin_logged_in = False
                st.session_state.current_spec_admin = ""
                st.rerun()

    if st.session_state.spec_admin_logged_in:
        admin_selected_spec = st.session_state.current_spec_admin

        with adm_tab1:
            st.write("### ظ‚ط§ط¦ظ…ط© ط§ظ„ط¹ظ†ط§ظˆظٹظ† ظˆط¥ظ…ظƒط§ظ†ظٹط© ط§ظ„ط¨ط­ط«")
            df_titles = load_data_from_sheet(SHEET_TITLES)
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            
            tit_col_name = [c for c in df_final.columns if "ط¹ظ†ظˆط§ظ†" in c]
            registered_titles = df_final[tit_col_name[0]].dropna().astype(str).str.strip().tolist() if (not df_final.empty and tit_col_name) else []
            
            titles_status = []
            if not df_titles.empty:
                for i in range(0, len(df_titles.columns) - 1, 2):
                    t_col = df_titles.columns[i]
                    tch_col = df_titles.columns[i+1]
                    for _, r in df_titles.iterrows():
                        t_val = str(r[t_col]).strip()
                        tch_val = str(r[tch_col]).strip()
                        if t_val and t_val != 'nan':
                            status_str = "ًں”´ ظ…ظˆط¶ظˆط¹ ظ…ط³ط¬ظ„" if t_val in registered_titles else "ًںں¢ ظ…ظˆط¶ظˆط¹ ط؛ظٹط± ظ…ط³ط¬ظ„"
                            titles_status.append({"ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©": t_val, "ط§ظ„ط£ط³طھط§ط° ط§ظ„ظ…ط´ط±ظپ": tch_val, "ط§ظ„ط­ط§ظ„ط©": status_str})
            
            df_status_disp = pd.DataFrame(titles_status)
            if not df_status_disp.empty:
                df_status_disp.index = range(1, len(df_status_disp) + 1)
                st.dataframe(df_status_disp, use_container_width=True)

        with adm_tab2:
            st.write(f"### ًں‘¥ ظ‚ط§ط¦ظ…ط© ط§ظ„ط·ظ„ط¨ط© ط§ظ„ظ…ط³ط¬ظ„ظٹظ† ط¨طھط®طµطµ: {admin_selected_spec}")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            spec_col = [c for c in df_final.columns if "طھط®طµطµ" in c or "ط§ظ„طھط®طµطµ" in c]
            if not df_final.empty and spec_col:
                spec_registrations = df_final[df_final[spec_col[0]] == admin_selected_spec].copy()
                spec_registrations.index = range(1, len(spec_registrations) + 1)
                st.dataframe(spec_registrations, use_container_width=True)

        with adm_tab3:
            st.write("### ًں“© ط§ظ„ط¨طھ ظپظٹ ط·ظ„ط¨ط§طھ ط§ظ„طھط¹ط¯ظٹظ„ (ظ…ط³ط¤ظˆظ„ ط§ظ„طھط®طµطµ)")
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            spec_mod_col = [c for c in df_mod.columns if "طھط®طµطµ" in c or "ط§ظ„طھط®طµطµ" in c]
            if not df_mod.empty and spec_mod_col:
                spec_reqs = df_mod[df_mod[spec_mod_col[0]] == admin_selected_spec].copy()
                spec_reqs.index = range(1, len(spec_reqs) + 1)
                st.dataframe(spec_reqs, use_container_width=True)

                orig_col_name = [c for c in spec_reqs.columns if "ط£طµظ„ظٹ" in c or "ط§طµظ„ظٹ" in c or "ط§ظ„ط¹ظ†ظˆط§ظ†" in c][0]
                status_col_name = [c for c in spec_reqs.columns if "ط­ط§ظ„ط©" in c or "ط§ظ„ط­ط§ظ„ط©" in c][0]
                handler_col_name = [c for c in spec_reqs.columns if "ظ…ط¹ط§ظ„ط¬" in c or "ط§ظ„ط·ظ„ط¨" in c]
                handler_col = handler_col_name[0] if handler_col_name else None

                all_req_titles = spec_reqs[orig_col_name].tolist()
                req_orig_title = st.selectbox("ط§ط®طھط± ط·ظ„ط¨ ط§ظ„طھط¹ط¯ظٹظ„ ظ„ظ„ط¨طھ ظپظٹظ‡:", ["-- ط§ط®طھط± ط§ظ„ط·ظ„ط¨ --"] + all_req_titles, key="sb_mod_dec_v55")
                
                if req_orig_title != "-- ط§ط®طھط± ط§ظ„ط·ظ„ط¨ --":
                    selected_req_row = spec_reqs[spec_reqs[orig_col_name] == req_orig_title].iloc[0]
                    curr_status = str(selected_req_row.get(status_col_name, "")).strip()
                    curr_handler = str(selected_req_row.get(handler_col, "")).strip() if handler_col else ""

                    if "ظ…ظ‚ط¨ظˆظ„" in curr_status or "ظ…ط±ظپظˆط¶" in curr_status:
                        st.warning(f"âڑ ï¸ڈ طھظ… ط§طھط®ط§ط° ط§ظ„ظ‚ط±ط§ط± ط³ط§ط¨ظ‚ط§ظ‹ ط¨ظ€: `{curr_status}` ط¨ظˆط§ط³ط·ط©: `{curr_handler}`.")
                    else:
                        teacher_name_req = selected_req_row.get("ط§ظ„ط£ط³طھط§ط°", "")
                        new_title_req = selected_req_row.get("ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط¬ط¯ظٹط¯", "")

                        col_a, col_r = st.columns(2)
                        with col_a:
                            if st.button("ظ‚ط¨ظˆظ„ ط§ظ„طھط¹ط¯ظٹظ„ ظˆطھط­ط¯ظٹط« ط§ظ„ط¹ظ†ظˆط§ظ† âœ…", key="btn_accept_v55"):
                                if update_mod_request_status_in_sheet(req_orig_title, "طھط¹ط¯ظٹظ„ ظ…ظ‚ط¨ظˆظ„", f"ظ…ط³ط¤ظˆظ„ طھط®طµطµ ({admin_selected_spec})", teacher_name=teacher_name_req, new_title=new_title_req):
                                    st.success("طھظ… طھط³ط¬ظٹظ„ ط§ظ„ظ‚ط¨ظˆظ„ ظˆطھط­ط¯ظٹط« ط§ظ„ط¹ظ†ظˆط§ظ† ط³ط­ط§ط¨ظٹط§ظ‹!")
                                    st.toast("âœ… طھظ… ظ‚ط¨ظˆظ„ ط§ظ„طھط¹ط¯ظٹظ„ ظˆطھط­ط¯ظٹط« ط§ظ„ط¨ظٹط§ظ†ط§طھ ظپظٹ ط§ظ„ط¬ط¯ط§ظˆظ„ ط³ط­ط§ط¨ظٹط§ظ‹!")
                                    st.rerun()
                        with col_r:
                            if st.button("ط±ظپط¶ ط§ظ„طھط¹ط¯ظٹظ„ â‌Œ", key="btn_reject_v55"):
                                if update_mod_request_status_in_sheet(req_orig_title, "طھط¹ط¯ظٹظ„ ظ…ط±ظپظˆط¶", f"ظ…ط³ط¤ظˆظ„ طھط®طµطµ ({admin_selected_spec})"):
                                    st.warning("طھظ… طھط³ط¬ظٹظ„ ط§ظ„ط±ظپط¶ ط¨ظ†ط¬ط§ط­!")
                                    st.toast("â‌Œ طھظ… ط­ظپط¸ ظ‚ط±ط§ط± ط§ظ„ط±ظپط¶!")
                                    st.rerun()

        with adm_tab_stats:
            st.write(f"### ًں“ˆ ط¥ط­طµط§ط¦ظٹط§طھ ط§ظ„طھط®طµطµ: {admin_selected_spec}")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            spec_col = [c for c in df_final.columns if "طھط®طµطµ" in c or "ط§ظ„طھط®طµطµ" in c]
            t_col = [c for c in df_final.columns if "ط£ط³طھط§ط°" in c or "ط§ط³طھط§ط°" in c]
            
            if not df_final.empty and spec_col:
                df_spec = df_final[df_final[spec_col[0]] == admin_selected_spec]
                
                c_col_st1 = [c for c in df_spec.columns if "ط·ط§ظ„ط¨" in c and "1" in c]
                c_col_st2 = [c for c in df_spec.columns if "ط·ط§ظ„ط¨" in c and "2" in c]

                st1_cnt = len(df_spec[c_col_st1[0]].dropna().unique()) if c_col_st1 else 0
                st2_cnt = len([s for s in df_spec[c_col_st2[0]].dropna().unique() if str(s).strip() and str(s).strip().lower() not in ['---', 'nan', 'none', 'null', 'ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ']]) if c_col_st2 else 0
                
                c_m1, c_m2, c_m3 = st.columns(3)
                with c_m1: st.metric("ط¹ط¯ط¯ ط§ظ„ظ…ط°ظƒط±ط§طھ ط§ظ„ظ…ط³ط¬ظ„ط©", len(df_spec))
                with c_m2: st.metric("ط¹ط¯ط¯ ط§ظ„ط£ط³ط§طھط°ط© ط§ظ„ظ…ط´ط±ظپظٹظ†", df_spec[t_col[0]].nunique() if t_col else 0)
                with c_m3: st.metric("ط¹ط¯ط¯ ط§ظ„ط·ظ„ط¨ط© ط§ظ„ظ…ط³ط¬ظ„ظٹظ†", st1_cnt + st2_cnt)

        with adm_tab_print:
            st.write(f"### ًں–¨ï¸ڈ ط·ط¨ط§ط¹ط© ط§ظ„طھظ‚ط±ظٹط± ط§ظ„ط¹ط§ظ… ظ„طھط®طµطµ: {admin_selected_spec}")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if st.button("ًں“¥ ط¥ظ†ط´ط§ط، ظˆطھطµط¯ظٹط± ط§ظ„طھظ‚ط±ظٹط± ط§ظ„ط¹ط§ظ… (PDF)", key="btn_print_spec_pdf_v55"):
                pdf_b = generate_general_report_pdf(df_final, [admin_selected_spec], title_prefix=f"طھظ‚ط±ظٹط± طھط®طµطµ {admin_selected_spec}")
                st.download_button("ًں–¨ï¸ڈ طھط­ظ…ظٹظ„ ط§ظ„ظ…ظ„ظپ", data=pdf_b, file_name=f"طھظ‚ط±ظٹط±_{admin_selected_spec}.pdf", mime="application/pdf", key="dl_spec_pdf_v55")

# ==========================================
# 3- ظپط¶ط§ط، ظ…ط³ط¤ظˆظ„ظژظٹ ط§ظ„ط´ط¹ط¨طھظٹظ†
# ==========================================
with tab_dept_admin:
    if 'dept_admin_logged_in' not in st.session_state:
        st.session_state.dept_admin_logged_in = False

    d_sub_login, d_tab1, d_tab_mod, d_tab_edit_unreg, d_tab_unreg_students, d_tab2, d_tab3, d_tab4 = st.tabs([
        "ًں”گ ط­ط³ط§ط¨ظٹ",
        "ًں“ڑ ط§ظ„ظ…ظˆط§ط¶ظٹط¹ ط§ظ„ظ…ط³ط¬ظ„ط© ط¨ط§ظ„ظ‚ط³ظ…",
        "ًں“© ط§ظ„ط¨طھ ظپظٹ ط·ظ„ط¨ط§طھ ط§ظ„طھط¹ط¯ظٹظ„",
        "âœڈï¸ڈ طھط¹ط¯ظٹظ„ ط§ظ„ظ…ظˆط§ط¶ظٹط¹ ط؛ظٹط± ط§ظ„ظ…ط³ط¬ظ„ط©",
        "ًں‘¥ ط§ظ„ط·ظ„ط¨ط© ط؛ظٹط± ط§ظ„ظ…ط³ط¬ظ„ظٹظ†",
        "ًں–¨ï¸ڈ طھط­ظ…ظٹظ„ ط§ظ„ط§ط³طھظ…ط§ط±ط§طھ ظ…ط¹ ط§ظ„ظƒظˆط¯ط¨ط§ط±",
        "ًں“ˆ ط§ظ„طھظپط§طµظٹظ„ ظˆط§ظ„ط¥ط­طµط§ط¦ظٹط§طھ ط§ظ„ط¹ط§ظ…ط©",
        "ًں–¨ï¸ڈ ط·ط¨ط§ط¹ط© ط§ظ„طھظ‚ط±ظٹط± ط§ظ„ط¹ط§ظ…"
    ])

    with d_sub_login:
        if not st.session_state.dept_admin_logged_in:
            st.subheader("ط¯ط®ظˆظ„ ظ…ط³ط¤ظˆظ„ظژظٹ ط§ظ„ط´ط¹ط¨طھظٹظ†")
            dept_pass_input = st.text_input("ظƒظ„ظ…ط© ظ…ط±ظˆط± ظ…ط³ط¤ظˆظ„ ط§ظ„ط´ط¹ط¨ط©:", type="password", key="dept_p_in_v55")
            if st.button("طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ظƒظ…ط³ط¤ظˆظ„ ط´ط¹ط¨ط© ًںڑ€", key="btn_login_dept_admin_v55"):
                if dept_pass_input in ["1234", MASTER_SUPER_PASS]:
                    st.session_state.dept_admin_logged_in = True
                    st.toast("âœ… طھظ… طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ظƒظ…ط³ط¤ظˆظ„ ط´ط¹ط¨ط©!")
                    st.rerun()
                else:
                    st.error("ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط؛ظٹط± طµط­ظٹط­ط©!")
        else:
            st.markdown("""
            <div class="status-msg-success">
                ظ…ط±ط­ط¨ط§ظ‹ ط¨ظƒظ…ط§طŒ ظ…ط³ط¤ظˆظ„ظٹ ط§ظ„ط´ط¹ط¨طھظٹظ† - ط§ظ„ط¥ط¯ط§ط±ط© ط§ظ„ط¹ط§ظ…ط© ظ„ظ„ظ‚ط³ظ….
            </div>
            """, unsafe_allow_html=True)
            if st.button("ًں”´ طھط³ط¬ظٹظ„ ط§ظ„ط®ط±ظˆط¬ ظƒظ…ط³ط¤ظˆظ„ ط´ط¹ط¨ط©", key="btn_logout_dept_admin_v55"):
                st.session_state.dept_admin_logged_in = False
                st.rerun()

    if st.session_state.dept_admin_logged_in:
        with d_tab1:
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final.empty:
                df_final.index = range(1, len(df_final) + 1)
                st.dataframe(df_final, use_container_width=True)

        with d_tab_mod:
            st.write("### ًں“© ط§ظ„ط¨طھ ظپظٹ ط·ظ„ط¨ط§طھ ط§ظ„طھط¹ط¯ظٹظ„ (ظ…ط³ط¤ظˆظ„ ط§ظ„ط´ط¹ط¨ط©)")
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            if not df_mod.empty:
                df_mod.index = range(1, len(df_mod) + 1)
                st.dataframe(df_mod, use_container_width=True)

                orig_col_name = [c for c in df_mod.columns if "ط£طµظ„ظٹ" in c or "ط§طµظ„ظٹ" in c or "ط§ظ„ط¹ظ†ظˆط§ظ†" in c][0]
                status_col_name = [c for c in df_mod.columns if "ط­ط§ظ„ط©" in c or "ط§ظ„ط­ط§ظ„ط©" in c][0]

                req_orig_title_dept = st.selectbox("ط§ط®طھط± ط·ظ„ط¨ ط§ظ„طھط¹ط¯ظٹظ„ ظ„ظ„ط¨طھ ظپظٹظ‡ ظƒظ…ط³ط¤ظˆظ„ ط´ط¹ط¨ط©:", ["-- ط§ط®طھط± ط§ظ„ط·ظ„ط¨ --"] + df_mod[orig_col_name].tolist(), key="sb_mod_dec_dept_v55")
                if req_orig_title_dept != "-- ط§ط®طھط± ط§ظ„ط·ظ„ط¨ --":
                    selected_req_row = df_mod[df_mod[orig_col_name] == req_orig_title_dept].iloc[0]
                    teacher_name_req = selected_req_row.get("ط§ظ„ط£ط³طھط§ط°", "")
                    new_title_req = selected_req_row.get("ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط¬ط¯ظٹط¯", "")

                    col_da, col_dr = st.columns(2)
                    with col_da:
                        if st.button("ظ‚ط¨ظˆظ„ ط§ظ„طھط¹ط¯ظٹظ„ ظˆطھط­ط¯ظٹط« ط§ظ„ط¹ظ†ظˆط§ظ† (ظ…ط³ط¤ظˆظ„ ط§ظ„ط´ط¹ط¨ط©) âœ…", key="btn_accept_dept_v55"):
                            if update_mod_request_status_in_sheet(req_orig_title_dept, "طھط¹ط¯ظٹظ„ ظ…ظ‚ط¨ظˆظ„", "ظ…ط³ط¤ظˆظ„ ط§ظ„ط´ط¹ط¨ط©", teacher_name=teacher_name_req, new_title=new_title_req):
                                st.success("طھظ… طھط³ط¬ظٹظ„ ط§ظ„ظ‚ط¨ظˆظ„ ظˆطھط­ط¯ظٹط« ط§ظ„ط¹ظ†ظˆط§ظ† ط³ط­ط§ط¨ظٹط§ظ‹!")
                                st.toast("âœ… طھظ… ظ‚ط¨ظˆظ„ ط§ظ„طھط¹ط¯ظٹظ„ ظˆطھط­ط¯ظٹط« ط§ظ„ط¨ظٹط§ظ†ط§طھ ط³ط­ط§ط¨ظٹط§ظ‹!")
                                st.rerun()
                    with col_dr:
                        if st.button("ط±ظپط¶ ط§ظ„طھط¹ط¯ظٹظ„ (ظ…ط³ط¤ظˆظ„ ط§ظ„ط´ط¹ط¨ط©) â‌Œ", key="btn_reject_dept_v55"):
                            if update_mod_request_status_in_sheet(req_orig_title_dept, "طھط¹ط¯ظٹظ„ ظ…ط±ظپظˆط¶", "ظ…ط³ط¤ظˆظ„ ط§ظ„ط´ط¹ط¨ط©"):
                                st.warning("طھظ… طھط³ط¬ظٹظ„ ط§ظ„ط±ظپط¶ ط¨ظ†ط¬ط§ط­!")
                                st.toast("â‌Œ طھظ… ط­ظپط¸ ظ‚ط±ط§ط± ط§ظ„ط±ظپط¶!")
                                st.rerun()

        with d_tab_edit_unreg:
            st.write("### âœڈï¸ڈ طھط¹ط¯ظٹظ„ ط§ظ„ظ…ظˆط§ط¶ظٹط¹ ظˆط§ظ„ظ…ط´ط±ظپظٹظ† ط؛ظٹط± ط§ظ„ظ…ط³ط¬ظ„ظٹظ†")
            df_titles = load_data_from_sheet(SHEET_TITLES)
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            
            tit_col_name = [c for c in df_final.columns if "ط¹ظ†ظˆط§ظ†" in c]
            registered_titles = df_final[tit_col_name[0]].dropna().astype(str).str.strip().tolist() if (not df_final.empty and tit_col_name) else []

            unregistered_titles_list = []
            if not df_titles.empty:
                for i in range(0, len(df_titles.columns) - 1, 2):
                    t_col = df_titles.columns[i]
                    tch_col = df_titles.columns[i+1]
                    for _, r in df_titles.iterrows():
                        t_val = str(r[t_col]).strip()
                        tch_val = str(r[tch_col]).strip()
                        if t_val and t_val != 'nan' and t_val not in registered_titles:
                            unregistered_titles_list.append({"ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط­ط§ظ„ظٹ": t_val, "ط§ظ„ط£ط³طھط§ط° ط§ظ„ظ…ط´ط±ظپ ط§ظ„ط­ط§ظ„ظٹ": tch_val})

            df_unreg_disp = pd.DataFrame(unregistered_titles_list)
            if not df_unreg_disp.empty:
                df_unreg_disp.index = range(1, len(df_unreg_disp) + 1)
                st.dataframe(df_unreg_disp, use_container_width=True)

                sel_title_to_edit = st.selectbox("ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط±ط§ط¯ طھط¹ط¯ظٹظ„ ط¨ظٹط§ظ†ط§طھظ‡:", ["-- ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† --"] + df_unreg_disp["ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط­ط§ظ„ظٹ"].tolist(), key="sb_edit_unreg_title_v55")
                if sel_title_to_edit != "-- ط§ط®طھط± ط§ظ„ط¹ظ†ظˆط§ظ† --":
                    row_unreg = df_unreg_disp[df_unreg_disp["ط§ظ„ط¹ظ†ظˆط§ظ† ط§ظ„ط­ط§ظ„ظٹ"] == sel_title_to_edit].iloc[0]
                    
                    df_teachers = load_data_from_sheet(SHEET_TEACHERS)
                    t_name_col = [c for c in df_teachers.columns if "ط§ظ„ط§ط³ظ…" in c or "ط§ظ„ظ„ظ‚ط¨" in c][0] if not df_teachers.empty else "ط§ط³ظ… ط§ظ„ط£ط³طھط§ط°"
                    teachers_list = df_teachers[t_name_col].dropna().unique().tolist() if not df_teachers.empty else []

                    new_title_unreg = st.text_input("طھط¹ط¯ظٹظ„ ط§ظ„ط¹ظ†ظˆط§ظ†:", value=sel_title_to_edit, key="inp_new_unreg_t_v55")
                    new_teacher_unreg = st.selectbox("طھط¹ط¯ظٹظ„ ط§ظ„ظ…ط´ط±ظپ:", teachers_list, index=teachers_list.index(row_unreg["ط§ظ„ط£ط³طھط§ط° ط§ظ„ظ…ط´ط±ظپ ط§ظ„ط­ط§ظ„ظٹ"]) if row_unreg["ط§ظ„ط£ط³طھط§ط° ط§ظ„ظ…ط´ط±ظپ ط§ظ„ط­ط§ظ„ظٹ"] in teachers_list else 0, key="sb_new_unreg_tch_v55")

                    if st.button("ًں’¾ ط­ظپط¸ ط§ظ„طھط¹ط¯ظٹظ„ ظپظٹ ظ‚ط§ط¹ط¯ط© ط§ظ„ط¨ظٹط§ظ†ط§طھ", key="btn_save_unreg_title_v55"):
                        if update_title_in_sheets_after_approval(new_teacher_unreg, sel_title_to_edit, new_title_unreg):
                            st.success("âœ… طھظ… ط­ظپط¸ ط§ظ„طھط¹ط¯ظٹظ„ ط¨ظ†ط¬ط§ط­ ظپظٹ ظ‚ط§ط¹ط¯ط© ط§ظ„ط¨ظٹط§ظ†ط§طھ ظˆطھط­ط¯ظٹط« ط§ط³ظ… ط§ظ„ط£ط³طھط§ط° ظˆط§ظ„ط¹ظ†ظˆط§ظ†!")
                            st.toast("âœ… طھظ… طھط­ط¯ظٹط« ط§ظ„ط¹ظ†ظˆط§ظ† ظˆط§ظ„ط£ط³طھط§ط° ط³ط­ط§ط¨ظٹط§ظ‹!")
                            st.rerun()

        with d_tab_unreg_students:
            st.write("### ًں‘¥ ظ‚ط§ط¦ظ…ط© ط§ظ„ط·ظ„ط¨ط© ط؛ظٹط± ط§ظ„ظ…ط³ط¬ظ„ظٹظ† ط¨ط§ظ„ظ‚ط³ظ…")
            df_students = load_data_from_sheet(SHEET_STUDENTS)
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)

            c_col_st1 = [c for c in df_final.columns if "ط·ط§ظ„ط¨" in c and "1" in c]
            c_col_st2 = [c for c in df_final.columns if "ط·ط§ظ„ط¨" in c and "2" in c]
            reg_st1 = df_final[c_col_st1[0]].dropna().tolist() if c_col_st1 else []
            reg_st2 = df_final[c_col_st2[0]].dropna().tolist() if c_col_st2 else []
            all_reg_students = set([str(s).strip() for s in reg_st1 + reg_st2 if str(s).strip()])

            unregistered_students = []
            spec_col_map = {
                "ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©": ("طھط®طµطµ ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ظ„ط³ط§ظ†ظٹط§طھ ط¹ط§ظ…ط©"),
                "ط£ط¯ط¨ ط¹ط±ط¨ظٹ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±": ("طھط®طµطµ ط£ط¯ط¨ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ط£ط¯ط¨ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±"),
                "ظ†ظ‚ط¯ ط­ط¯ظٹط« ظ…ط¹ط§طµط±": ("طھط®طµطµ ظ†ظ‚ط¯ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ظ†ظ‚ط¯ ط­ط¯ظٹط« ظˆظ…ط¹ط§طµط±"),
                "ط£ط¯ط¨ ط´ط¹ط¨ظٹ": ("طھط®طµطµ ط£ط¯ط¨ ط´ط¹ط¨ظٹ", "ط±ظ‚ظ… طھط³ط¬ظٹظ„ ط£ط¯ط¨ ط´ط¹ط¨ظٹ")
            }

            if not df_students.empty:
                for spec_k, (n_col_t, r_col_t) in spec_col_map.items():
                    n_col = [c for c in df_students.columns if n_col_t.replace(" ", "") in c.replace(" ", "") or n_col_t.replace(" ", "_") in c.replace(" ", "_")]
                    r_col = [c for c in df_students.columns if r_col_t.replace(" ", "") in c.replace(" ", "") or r_col_t.replace(" ", "_") in c.replace(" ", "_")]
                    
                    if n_col and r_col:
                        for _, r in df_students.iterrows():
                            s_name = str(r[n_col[0]]).strip()
                            s_reg = str(r[r_col[0]]).strip()
                            if s_name and s_name != 'nan' and s_name not in all_reg_students:
                                unregistered_students.append({"ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨": s_name, "ط±ظ‚ظ… ط§ظ„طھط³ط¬ظٹظ„": s_reg, "ط§ظ„طھط®طµطµ": spec_k})

            df_unreg_st = pd.DataFrame(unregistered_students)
            if not df_unreg_st.empty:
                col_s_ord, col_s_filt = st.columns(2)
                with col_s_ord:
                    sort_order = st.radio("طھط±طھظٹط¨ ط§ظ„ظ‚ط§ط¦ظ…ط© ط­ط³ط¨ ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨:", ["ظ…ظ† A ط¥ظ„ظ‰ Z (طھطµط§ط¹ط¯ظٹ)", "ظ…ظ† Z ط¥ظ„ظ‰ A (طھظ†ط§ط²ظ„ظٹ)"], horizontal=True, key="rd_sort_unreg_v55")
                with col_s_filt:
                    filter_specs = st.multiselect("ظپط±ط² ط­ط³ط¨ ط§ظ„طھط®طµطµ:", options=SPECIALTIES, default=SPECIALTIES, key="ms_filter_unreg_v55")
                
                if filter_specs:
                    df_unreg_st = df_unreg_st[df_unreg_st["ط§ظ„طھط®طµطµ"].isin(filter_specs)]

                ascending_bool = True if "A ط¥ظ„ظ‰ Z" in sort_order else False
                df_unreg_st = df_unreg_st.sort_values(by="ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨", ascending=ascending_bool)
                df_unreg_st.index = range(1, len(df_unreg_st) + 1)
                st.dataframe(df_unreg_st, use_container_width=True)

                col_exp_pdf, col_exp_excel = st.columns(2)
                with col_exp_pdf:
                    if st.button("ًں“¥ طھطµط¯ظٹط± ظ‚ط§ط¦ظ…ط© ط؛ظٹط± ط§ظ„ظ…ط³ط¬ظ„ظٹظ† (PDF)", key="btn_exp_unreg_pdf_v55"):
                        pdf_unreg_bytes = generate_general_report_pdf(df_unreg_st, filter_specs, title_prefix="ظ‚ط§ط¦ظ…ط© ط§ظ„ط·ظ„ط¨ط© ط؛ظٹط± ط§ظ„ظ…ط³ط¬ظ„ظٹظ†")
                        st.download_button("ًں–¨ï¸ڈ طھط­ظ…ظٹظ„ PDF", data=pdf_unreg_bytes, file_name="ط§ظ„ط·ظ„ط¨ط©_ط؛ظٹط±_ط§ظ„ظ…ط³ط¬ظ„ظٹظ†.pdf", mime="application/pdf", key="dl_unreg_pdf_v55")

                with col_exp_excel:
                    buffer_excel = BytesIO()
                    with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                        df_unreg_st.to_excel(writer, index=False, sheet_name="ط؛ظٹط± ط§ظ„ظ…ط³ط¬ظ„ظٹظ†")
                    buffer_excel.seek(0)
                    st.download_button("ًں“ٹ طھطµط¯ظٹط± ظ‚ط§ط¦ظ…ط© ط؛ظٹط± ط§ظ„ظ…ط³ط¬ظ„ظٹظ† (Excel)", data=buffer_excel, file_name="ط§ظ„ط·ظ„ط¨ط©_ط؛ظٹط±_ط§ظ„ظ…ط³ط¬ظ„ظٹظ†.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_unreg_excel_v55")

        with d_tab2:
            st.write("### ًں–¨ï¸ڈ ط§ط³طھط®ط±ط§ط¬ ظˆطھط­ظ…ظٹظ„ ط§ط³طھظ…ط§ط±ط§طھ ط§ظ„ظ…ط°ظƒط±ط§طھ (ظپط±ط¯ظٹط§ظ‹ ظˆط¯ظڈظپط¹ط© ظˆط§ط­ط¯ط©)")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final.empty:
                t_col_name = [c for c in df_final.columns if "ط£ط³طھط§ط°" in c or "ط§ط³طھط§ط°" in c][0]
                
                df_final['ط£ط³طھط§ط°_ظ†ط¸ظٹظپ'] = df_final[t_col_name].astype(str).str.strip()
                df_final['ط±ظ‚ظ…_ظ…ط°ظƒط±ط©_ط§ظ„ط£ط³طھط§ط°'] = df_final.groupby('ط£ط³طھط§ط°_ظ†ط¸ظٹظپ').cumcount() + 1
                df_final['ط§ط³ظ…_ط§ظ„ظ…ظ„ظپ'] = df_final['ط£ط³طھط§ط°_ظ†ط¸ظٹظپ'] + df_final['ط±ظ‚ظ…_ظ…ط°ظƒط±ط©_ط§ظ„ط£ط³طھط§ط°'].astype(str)

                col_single, col_bulk = st.columns(2)
                
                with col_single:
                    st.markdown("#### ًں“„ طھط­ظ…ظٹظ„ ط§ط³طھظ…ط§ط±ط© ظˆط§ط­ط¯ط©")
                    file_options = df_final['ط§ط³ظ…_ط§ظ„ظ…ظ„ظپ'].tolist()
                    selected_file_label = st.selectbox("ط§ط®طھط± ط§ظ„ط§ط³طھظ…ط§ط±ط© ط§ظ„ظ…ط³ظ…ظ‰ ط¨ط§ط³ظ… ط§ظ„ط£ط³طھط§ط° ظˆط±ظ‚ظ…ظ‡ط§:", ["-- ط§ط®طھط± ط§ظ„ط§ط³طھظ…ط§ط±ط© --"] + file_options, key="sb_dept_single_file_v55")
                    
                    if selected_file_label != "-- ط§ط®طھط± ط§ظ„ط§ط³طھظ…ط§ط±ط© --":
                        form_row = df_final[df_final['ط§ط³ظ…_ط§ظ„ظ…ظ„ظپ'] == selected_file_label].iloc[0]
                        
                        c_col_st1 = [c for c in form_row.index if "ط·ط§ظ„ط¨" in c and "1" in c]
                        c_col_r1 = [c for c in form_row.index if "طھط³ط¬ظٹظ„" in c and "1" in c]
                        c_col_st2 = [c for c in form_row.index if "ط·ط§ظ„ط¨" in c and "2" in c]
                        c_col_r2 = [c for c in form_row.index if "طھط³ط¬ظٹظ„" in c and "2" in c]

                        st1_v = form_row.get(c_col_st1[0], '') if c_col_st1 else form_row.get('ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 1', '')
                        r1_v = form_row.get(c_col_r1[0], '') if c_col_r1 else form_row.get('ط±ظ‚ظ… طھط³ط¬ظٹظ„ 1', '')
                        st2_v = form_row.get(c_col_st2[0], '') if c_col_st2 else form_row.get('ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 2', '')
                        r2_v = form_row.get(c_col_r2[0], '') if c_col_r2 else form_row.get('ط±ظ‚ظ… طھط³ط¬ظٹظ„ 2', '')

                        t_name_val = form_row.get(t_col_name, "")
                        spec_val = form_row.get("طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨", "")
                        title_val = form_row.get("ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©", "")
                        form_code_val = form_row.get("ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©", generate_form_code())

                        st2_qr_txt = f"\nط§ظ„ط·ط§ظ„ط¨ 2: {st2_v} ({r2_v})" if st2_v else "\nط§ظ„ط·ط§ظ„ط¨ 2: ظ„ط§ ظٹظˆط¬ط¯"
                        qr_code_val = f"ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©: {form_code_val}\nط§ظ„ظ…ط´ط±ظپ: {t_name_val}\nط§ظ„طھط®طµطµ: {spec_val}\nط§ظ„ط¹ظ†ظˆط§ظ†: {title_val}\nط§ظ„ط·ط§ظ„ط¨ 1: {st1_v} ({r1_v}){st2_qr_txt}\nطھط§ط±ظٹط® ط§ظ„ط§ط¹طھظ…ط§ط¯: {form_row.get('طھط§ط±ظٹط® ط§ظ„طھط³ط¬ظٹظ„', datetime.now().strftime('%Y-%m-%d %H:%M'))}"

                        dept_pdf_bytes = generate_pdf_document(
                            form_code_val,
                            t_name_val, spec_val,
                            st1_v, r1_v, st2_v, r2_v, title_val,
                            qr_code_str=qr_code_val
                        )

                        st.download_button(
                            label=f"ًں–¨ï¸ڈ طھط­ظ…ظٹظ„ ط§ط³طھظ…ط§ط±ط© ({selected_file_label}.pdf)",
                            data=dept_pdf_bytes,
                            file_name=f"{selected_file_label}.pdf",
                            mime="application/pdf",
                            key="btn_dept_dl_single_v55"
                        )

                with col_bulk:
                    st.markdown("#### ًں“¦ طھط­ظ…ظٹظ„ ط§ظ„ط§ط³طھظ…ط§ط±ط§طھ ط¯ظپط¹ط© ظˆط§ط­ط¯ط© (ZIP)")
                    bulk_choice = st.radio("ط®ظٹط§ط±ط§طھ ط§ظ„طھط¬ظ…ظٹط¹ ظ„ظ„طھط­ظ…ظٹظ„ ط§ظ„ط¬ظ…ط§ط¹ظٹ:", ["ط¬ظ…ظٹط¹ ط§ظ„ط§ط³طھظ…ط§ط±ط§طھ ط¨ط§ظ„ظ‚ط³ظ…", "ط­ط³ط¨ طھط®طµطµ ظ…ط¹ظٹظ†"], horizontal=True, key="rd_bulk_type_v55")
                    
                    target_bulk_df = df_final.copy()
                    if bulk_choice == "ط­ط³ط¨ طھط®طµطµ ظ…ط¹ظٹظ†":
                        selected_bulk_spec = st.selectbox("ط§ط®طھط± ط§ظ„طھط®طµطµ ظ„ظ„طھظ†ط²ظٹظ„ ط§ظ„ط¬ظ…ط§ط¹ظٹ:", SPECIALTIES, key="sb_bulk_spec_v55")
                        target_bulk_df = target_bulk_df[target_bulk_df["طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨"] == selected_bulk_spec]

                    if st.button("ًں“¦ ط¥ظ†طھط§ط¬ ظ…ظ„ظپ ط§ظ„ط§ط³طھظ…ط§ط±ط§طھ ط§ظ„ط¬ظ…ط§ط¹ظٹ (ZIP)", key="btn_gen_bulk_zip_v55"):
                        if not target_bulk_df.empty:
                            zip_buffer = BytesIO()
                            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                                for _, form_row in target_bulk_df.iterrows():
                                    c_col_st1 = [c for c in form_row.index if "ط·ط§ظ„ط¨" in c and "1" in c]
                                    c_col_r1 = [c for c in form_row.index if "طھط³ط¬ظٹظ„" in c and "1" in c]
                                    c_col_st2 = [c for c in form_row.index if "ط·ط§ظ„ط¨" in c and "2" in c]
                                    c_col_r2 = [c for c in form_row.index if "طھط³ط¬ظٹظ„" in c and "2" in c]

                                    st1_v = form_row.get(c_col_st1[0], '') if c_col_st1 else form_row.get('ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 1', '')
                                    r1_v = form_row.get(c_col_r1[0], '') if c_col_r1 else form_row.get('ط±ظ‚ظ… طھط³ط¬ظٹظ„ 1', '')
                                    st2_v = form_row.get(c_col_st2[0], '') if c_col_st2 else form_row.get('ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨ 2', '')
                                    r2_v = form_row.get(c_col_r2[0], '') if c_col_r2 else form_row.get('ط±ظ‚ظ… طھط³ط¬ظٹظ„ 2', '')

                                    t_name_val = form_row.get(t_col_name, "")
                                    spec_val = form_row.get("طھط®طµطµ ط§ظ„ط·ط§ظ„ط¨", "")
                                    title_val = form_row.get("ط¹ظ†ظˆط§ظ† ط§ظ„ظ…ط°ظƒط±ط©", "")
                                    file_label = form_row.get("ط§ط³ظ…_ط§ظ„ظ…ظ„ظپ", f"ط§ط³طھظ…ط§ط±ط©_{t_name_val}")
                                    form_code_val = form_row.get("ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©", generate_form_code())

                                    st2_qr_txt = f"\nط§ظ„ط·ط§ظ„ط¨ 2: {st2_v} ({r2_v})" if st2_v else "\nط§ظ„ط·ط§ظ„ط¨ 2: ظ„ط§ ظٹظˆط¬ط¯"
                                    qr_code_val = f"ط±ظ…ط² ط§ظ„ط§ط³طھظ…ط§ط±ط©: {form_code_val}\nط§ظ„ظ…ط´ط±ظپ: {t_name_val}\nط§ظ„طھط®طµطµ: {spec_val}\nط§ظ„ط¹ظ†ظˆط§ظ†: {title_val}\nط§ظ„ط·ط§ظ„ط¨ 1: {st1_v} ({r1_v}){st2_qr_txt}\nطھط§ط±ظٹط® ط§ظ„ط§ط¹طھظ…ط§ط¯: {form_row.get('طھط§ط±ظٹط® ط§ظ„طھط³ط¬ظٹظ„', datetime.now().strftime('%Y-%m-%d %H:%M'))}"

                                    pdf_data = generate_pdf_document(
                                        form_code_val,
                                        t_name_val, spec_val,
                                        st1_v, r1_v, st2_v, r2_v, title_val,
                                        qr_code_str=qr_code_val
                                    )
                                    zip_file.writestr(f"{file_label}.pdf", pdf_data)

                            zip_buffer.seek(0)
                            st.toast("ًں“¦ طھظ… طھط¬ظ…ظٹط¹ ظˆط§ط³طھط®ط±ط§ط¬ ط¬ظ…ظٹط¹ ط§ظ„ط§ط³طھظ…ط§ط±ط§طھ ط¨ظ†ط¬ط§ط­!")
                            st.download_button(
                                label="ًں“¥ ط§ط¶ط؛ط· ظ‡ظ†ط§ ظ„طھط­ظ…ظٹظ„ ط£ط±ط´ظٹظپ ط§ظ„ط§ط³طھظ…ط§ط±ط§طھ (ZIP)",
                                data=zip_buffer,
                                file_name="ط¬ظ…ظٹط¹_ط§ظ„ط§ط³طھظ…ط§ط±ط§طھ_ط§ظ„ظ…ط¹طھظ…ط¯ط©.zip",
                                mime="application/zip",
                                key="btn_dl_zip_final_v55"
                            )
                        else:
                            st.warning("ظ„ط§ طھظˆط¬ط¯ ط§ط³طھظ…ط§ط±ط§طھ ظ…ط·ط§ط¨ظ‚ط© ظ„ظ„ط®ظٹط§ط± ط§ظ„ظ…ط­ط¯ط¯.")

        with d_tab3:
            st.write("### ًں“ˆ ط§ظ„ط¥ط­طµط§ط¦ظٹط§طھ ط§ظ„طھظپط§ط¹ظ„ظٹط© ط§ظ„ط´ط§ظ…ظ„ط© ظ„ظ„ظ‚ط³ظ…")
            selected_stats_specs = st.multiselect("ط­ط¯ط¯ ط§ظ„طھط®طµطµط§طھ ظ„ط¹ط±ط¶ ط¥ط­طµط§ط¦ظٹط§طھظ‡ط§:", options=SPECIALTIES, default=SPECIALTIES, key="ms_dept_stats_v55")
            
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            spec_col = [c for c in df_final.columns if "طھط®طµطµ" in c or "ط§ظ„طھط®طµطµ" in c]
            t_col = [c for c in df_final.columns if "ط£ط³طھط§ط°" in c or "ط§ط³طھط§ط°" in c]

            if not df_final.empty and spec_col:
                df_filtered_stats = df_final[df_final[spec_col[0]].isin(selected_stats_specs)]
                
                c_col_st1 = [c for c in df_filtered_stats.columns if "ط·ط§ظ„ط¨" in c and "1" in c]
                c_col_st2 = [c for c in df_filtered_stats.columns if "ط·ط§ظ„ط¨" in c and "2" in c]

                st1_cnt = len(df_filtered_stats[c_col_st1[0]].dropna().unique()) if c_col_st1 else 0
                st2_cnt = len([s for s in df_filtered_stats[c_col_st2[0]].dropna().unique() if str(s).strip() and str(s).strip().lower() not in ['---', 'nan', 'none', 'null', 'ظ„ط§ ظٹظˆط¬ط¯ / ط®ظٹط§ط± ظپط±ط¯ظٹ']]) if c_col_st2 else 0

                c_m1, c_m2, c_m3 = st.columns(3)
                with c_m1: st.metric("ط¹ط¯ط¯ ط§ظ„ظ…ط°ظƒط±ط§طھ ط§ظ„ظ…ط³ط¬ظ„ط©", len(df_filtered_stats))
                with c_m2: st.metric("ط¹ط¯ط¯ ط§ظ„ط£ط³ط§طھط°ط© ط§ظ„ظ…ط´ط±ظپظٹظ†", df_filtered_stats[t_col[0]].nunique() if t_col else 0)
                with c_m3: st.metric("ط¹ط¯ط¯ ط§ظ„ط·ظ„ط¨ط© ط§ظ„ظ…ط³ط¬ظ„ظٹظ†", st1_cnt + st2_cnt)

        with d_tab4:
            selected_specs_report = st.multiselect("ط­ط¯ط¯ ط§ظ„طھط®طµطµط§طھ ط§ظ„ظ…ط·ظ„ظˆط¨ ط·ط¨ط§ط¹طھظ‡ط§:", options=SPECIALTIES, default=SPECIALTIES, key="ms_dept_v55")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if st.button("ًں“¥ طھطµط¯ظٹط± ط§ظ„طھظ‚ط±ظٹط± ط§ظ„ط¹ط§ظ… (PDF)", key="btn_print_dept_pdf_v55"):
                pdf_b = generate_general_report_pdf(df_final, selected_specs_report)
                st.download_button("ًں–¨ï¸ڈ طھط­ظ…ظٹظ„ ط§ظ„ظ…ظ„ظپ", data=pdf_b, file_name="ط§ظ„طھظ‚ط±ظٹط±_ط§ظ„ط¹ط§ظ….pdf", mime="application/pdf", key="dl_dept_pdf_v55")
