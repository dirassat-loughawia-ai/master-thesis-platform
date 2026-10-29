import streamlit as st
import streamlit.components.v1 as components
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
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.utils import ImageReader

import arabic_reshaper
from bidi.algorithm import get_display
import qrcode

# --- 1. إعدادات الصفحة والتوسيط والـ RTL ---
st.set_page_config(
    page_title="منصة إدارة مذكرات الماستر - جامعة الوادي",
    page_icon="🎓",
    layout="wide"
)

GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/USERNAME/REPOSITORY/main/" 

SPREADSHEET_ID = "1GvS4BE2WL18peY97GAfjRJz9LdZTCZYWlV7P-QsJpOQ"
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbzxPsO3Ud7p_2eZ0Bi_t8_r3INo09PsYufpItPFpoMoFHqbCkvfa-Rh9lTzcvAlZ3GsZw/exec"

SHEET_TEACHERS = "قائمة الأساتذة"
SHEET_ADMINS = "كلمات مرور المسؤولين"
SHEET_STUDENTS = "قوائم الطلبة"
SHEET_TITLES = "العناوين المسجلة"
SHEET_MOD_REQUESTS = "طلبات التعديل"
SHEET_FINAL_REGISTRATIONS = "التسجيلات النهائية"
SHEET_ATTEST_NUMBERS = "رقم الإفادة"

SPECIALTIES = ["لسانيات عامة", "أدب عربي حديث ومعاصر", "نقد حديث معاصر", "أدب شعبي"]
DAYS_OF_WEEK = ["السبت", "الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس"]

MASTER_SUPER_PASS = "0000"
ATTESTATION_PASS = "20262027"
SYS_ADMIN_PASS = "19822026"
REGISTRATION_UNLOCK_PASS = "REG2026"
PV_UNLOCK_PASS = "PV2027"

SPEC_SUFFIX_MAP = {
    "لسانيات عامة": "_ling",
    "أدب عربي حديث ومعاصر": "_hadith",
    "نقد حديث معاصر": "_nakd",
    "أدب شعبي": "_chabi"
}

# --- 2. كود عداد الزوار ---
AMAZING_COUNTER_HTML = """
<div style="text-align: center; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; direction: rtl;">
    <div style="font-size: 1.15rem; font-weight: bold; color: #1e3a8a; margin-bottom: 8px;">
        أستاذنا المبجل، أنت الزائر رقم:
    </div>
    <div style="pointer-events: none; cursor: default; display: inline-block;">
        <img border="0" src="http://cc.amazingcounters.com/counter.php?i=3202262&c=9607099" alt="AmazingCounters.com" style="pointer-events: none; cursor: default;">
    </div>
    <div style="font-size: 1.15rem; font-weight: bold; color: #1e3a8a; margin-top: 4px;">
        لهذه المنصة - التعديلات السحابية لا تتم في الموقع
    </div>
</div>
"""

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
        df.columns = [str(col).strip() for col in df.columns]
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

def get_students_by_specialty(df_students, specialty):
    students_list = []
    suffix = SPEC_SUFFIX_MAP.get(specialty, "")
    if df_students.empty or not suffix:
        return students_list

    matr_col = [c for c in df_students.columns if c.endswith(f"matr{suffix}") or f"matr{suffix}" in c]
    nom_ar_col = [c for c in df_students.columns if c.endswith(f"nom{suffix}") or f"nom{suffix}" in c]
    prenom_ar_col = [c for c in df_students.columns if c.endswith(f"prenom{suffix}") or f"prenom{suffix}" in c]
    nom_fr_col = [c for c in df_students.columns if c.endswith(f"nom_fr{suffix}") or f"nom_fr{suffix}" in c]
    prenom_fr_col = [c for c in df_students.columns if c.endswith(f"prenom_fr{suffix}") or f"prenom_fr{suffix}" in c]
    date_n_col = [c for c in df_students.columns if c.endswith(f"date_n{suffix}") or f"date_n{suffix}" in c]
    lieu_n_col = [c for c in df_students.columns if c.endswith(f"lieu_n{suffix}") or f"lieu_n{suffix}" in c]

    c_matr = matr_col[0] if matr_col else None
    c_nom_ar = nom_ar_col[0] if nom_ar_col else None
    c_prenom_ar = prenom_ar_col[0] if prenom_ar_col else None
    c_nom_fr = nom_fr_col[0] if nom_fr_col else None
    c_prenom_fr = prenom_fr_col[0] if prenom_fr_col else None
    c_date_n = date_n_col[0] if date_n_col else None
    c_lieu_n = lieu_n_col[0] if lieu_n_col else None

    if c_nom_ar and c_prenom_ar:
        for _, row in df_students.iterrows():
            nom_ar = str(row.get(c_nom_ar, '')).strip()
            prenom_ar = str(row.get(c_prenom_ar, '')).strip()
            matr = str(row.get(c_matr, '')).strip() if c_matr else ""
            nom_fr = str(row.get(c_nom_fr, '')).strip() if c_nom_fr else ""
            prenom_fr = str(row.get(c_prenom_fr, '')).strip() if c_prenom_fr else ""
            date_n = str(row.get(c_date_n, '')).strip() if c_date_n else ""
            lieu_n = str(row.get(c_lieu_n, '')).strip() if c_lieu_n else ""

            if nom_ar and nom_ar.lower() != 'nan':
                name_ar = f"{nom_ar} {prenom_ar}".strip()
                name_fr = f"{nom_fr} {prenom_fr}".strip()
                label_display = f"{name_ar} | {name_fr} ({matr})" if name_fr else f"{name_ar} ({matr})"
                
                students_list.append({
                    "display": label_display,
                    "name_ar": name_ar,
                    "name_fr": name_fr,
                    "matr": matr,
                    "date_n": date_n,
                    "lieu_n": lieu_n
                })
    return students_list

def send_payload_to_script(payload):
    try:
        response = requests.post(WEB_APP_URL, json=payload, timeout=20)
        st.cache_data.clear()
        if response.status_code == 200:
            try:
                res_j = response.json()
                return res_j.get("status") == "success"
            except Exception:
                return True
        return False
    except Exception as e:
        st.error(f"خطأ في الاتصال السحابي: {e}")
        return False

def generate_random_code():
    letters = ''.join(random.choices(string.ascii_uppercase, k=4))
    digits = ''.join(random.choices(string.digits, k=4))
    return f"{letters}-{digits}"

def extract_title_from_row(row_series):
    if len(row_series) >= 8:
        val_idx7 = str(row_series.iloc[7]).strip()
        if val_idx7 and val_idx7.lower() != 'nan':
            return val_idx7
            
    for col_name, val in row_series.items():
        col_str = str(col_name).strip()
        val_str = str(val).strip()
        if ("عنوان" in col_str or "العنوان" in col_str) and val_str and val_str.lower() != 'nan':
            return val_str

    return "عنوان المذكرة"

def extract_teacher_from_row(row_series):
    for col_name, val in row_series.items():
        col_str = str(col_name).strip()
        val_str = str(val).strip()
        if ("أستاذ" in col_str or "استاذ" in col_str or "المشرف" in col_str) and val_str and val_str.lower() != 'nan':
            return val_str
    if len(row_series) >= 2:
        return str(row_series.iloc[1]).strip()
    return "اسم الأستاذ"

def get_teacher_titles_status(teacher_name, specialty):
    df_titles = load_data_from_sheet(SHEET_TITLES)
    all_titles_info = []
    approved_only = []
    unapproved_only = []
    
    if df_titles.empty:
        return all_titles_info, approved_only, unapproved_only

    for i in range(0, len(df_titles.columns) - 2, 3):
        t_col = df_titles.columns[i]
        tch_col = df_titles.columns[i+1]
        dec_col = df_titles.columns[i+2]
        
        col_lower = str(t_col).lower()
        spec_match = False
        if "لسانيات" in specialty and "لسانيات" in col_lower: spec_match = True
        elif "أدب" in specialty and "أدب" in col_lower: spec_match = True
        elif "نقد" in specialty and "نقد" in col_lower: spec_match = True
        elif "شعبي" in specialty and "شعبي" in col_lower: spec_match = True
        elif len(df_titles.columns) <= 6: spec_match = True

        if spec_match:
            for _, r in df_titles.iterrows():
                t_val = str(r[t_col]).strip()
                tch_val = str(r[tch_col]).strip()
                dec_val = str(r[dec_col]).strip()
                
                if tch_val == str(teacher_name).strip() and t_val and t_val.lower() != 'nan':
                    dec_display = dec_val if dec_val else "قيد الدراسة"
                    
                    if dec_val.lower() == "مقبول":
                        status_tag = "🟢 مقبول (متاح للتسجيل النهائي)"
                        approved_only.append(t_val)
                    else:
                        status_tag = f"🟡/🔴 {dec_display} (يتطلب تقديم طلب تعديل)"
                        unapproved_only.append(t_val)
                        
                    all_titles_info.append({
                        "عنوان المذكرة": t_val,
                        "قرار الخبرة": status_tag
                    })
                    
    return all_titles_info, list(set(approved_only)), list(set(unapproved_only))

def get_next_attestation_number(teacher_name):
    df_att = load_data_from_sheet(SHEET_ATTEST_NUMBERS)
    if not df_att.empty:
        t_col = [c for c in df_att.columns if "أستاذ" in c or "استاذ" in c]
        if t_col:
            matched = df_att[df_att[t_col[0]].astype(str).str.strip() == str(teacher_name).strip()]
            if not matched.empty and "رقم الإفادة" in matched.columns:
                return str(matched["رقم الإفادة"].values[0])

    att_code = generate_random_code()
    row_data = {"اسم الأستاذ": teacher_name, "رقم الإفادة": att_code, "تاريخ الإصدار": datetime.now().strftime("%Y-%m-%d %H:%M")}
    payload = {"action": "append", "sheet_name": SHEET_ATTEST_NUMBERS, "row_data": list(row_data.values())}
    send_payload_to_script(payload)
    return att_code

def save_data_to_sheet(row_data_dict, worksheet_name):
    if worksheet_name == SHEET_FINAL_REGISTRATIONS:
        ordered_keys = ["رمز الاستمارة", "اسم الأستاذ", "تخصص الطالب", "اسم الطالب 1", "رقم تسجيل 1", "اسم الطالب 2", "رقم تسجيل 2", "عنوان المذكرة", "تاريخ التسجيل", "كود التحقق"]
        row_values = [str(row_data_dict.get(k, "")).strip() for k in ordered_keys]
    else:
        row_values = [str(v).strip() for v in row_data_dict.values()]

    payload = {"action": "append", "sheet_name": worksheet_name, "row_data": row_values}
    return send_payload_to_script(payload)

def delete_registration_from_sheet(key_identifier):
    payload = {"action": "delete_row", "sheet_name": SHEET_FINAL_REGISTRATIONS, "key_val": str(key_identifier).strip()}
    return send_payload_to_script(payload)

def update_registration_in_sheet(key_identifier, row_data_dict):
    ordered_keys = ["رمز الاستمارة", "اسم الأستاذ", "تخصص الطالب", "اسم الطالب 1", "رقم تسجيل 1", "اسم الطالب 2", "رقم تسجيل 2", "عنوان المذكرة", "تاريخ التسجيل", "كود التحقق"]
    row_values = [str(row_data_dict.get(k, "")).strip() for k in ordered_keys]
    payload = {"action": "update_row", "sheet_name": SHEET_FINAL_REGISTRATIONS, "key_val": str(key_identifier).strip(), "row_data": row_values}
    return send_payload_to_script(payload)

def update_title_in_sheets_after_approval(teacher_name, orig_title, new_title):
    payload = {
        "action": "update_title_everywhere",
        "teacher": str(teacher_name).strip(),
        "orig_title": str(orig_title).strip(),
        "new_title": str(new_title).strip()
    }
    return send_payload_to_script(payload)

def update_mod_request_status_in_sheet(orig_title, status, handler, teacher_name="", new_title=""):
    payload = {
        "action": "update_status",
        "sheet_name": SHEET_MOD_REQUESTS,
        "orig_title": str(orig_title).strip(),
        "status": str(status).strip(),
        "handler": str(handler).strip()
    }
    success = send_payload_to_script(payload)
    if success and "مقبول" in status and teacher_name and new_title:
        update_title_in_sheets_after_approval(teacher_name, orig_title, new_title)
    return success

# --- 3. إعداد الخطوط والصور ---
def setup_arabic_font():
    local_fonts = ["trado.ttf", "Traditional Arabic.ttf", "Traditional-Arabic.ttf", "Amiri-Regular.ttf", "arial.ttf"]
    for font_p in local_fonts:
        if os.path.exists(font_p):
            try:
                pdfmetrics.registerFont(TTFont('TraditionalArabic', font_p))
                pdfmetrics.registerFont(TTFont('TraditionalArabic-Bold', font_p))
                return 'TraditionalArabic', 'TraditionalArabic-Bold'
            except Exception: pass

    try:
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Regular.ttf"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            with open("trado.ttf", "wb") as f: f.write(r.content)
            pdfmetrics.registerFont(TTFont('TraditionalArabic', "trado.ttf"))
            pdfmetrics.registerFont(TTFont('TraditionalArabic-Bold', "trado.ttf"))
            return 'TraditionalArabic', 'TraditionalArabic-Bold'
    except Exception: pass

    return 'Helvetica', 'Helvetica-Bold'

ARABIC_FONT, ARABIC_FONT_BOLD = setup_arabic_font()

def reshape_arabic(text):
    if text is None or pd.isna(text): return ""
    txt_str = str(text).strip()
    if txt_str == "" or txt_str.lower() in ["nan", "none", "null"]: return ""
    return get_display(arabic_reshaper.reshape(txt_str))

@st.cache_data(ttl=3600)
def get_image_bytes(image_filename):
    if os.path.exists(image_filename):
        try:
            with open(image_filename, "rb") as f: return f.read()
        except Exception: pass
    try:
        url = GITHUB_RAW_BASE_URL + image_filename
        res = requests.get(url, timeout=5)
        if res.status_code == 200: return res.content
    except Exception: pass
    return None

def make_reportlab_image(image_filename, width, height):
    b_data = get_image_bytes(image_filename)
    if b_data:
        try: return RLImage(BytesIO(b_data), width=width, height=height)
        except Exception: pass
    return None

def draw_header_icons(can, page_width, page_height):
    b1 = get_image_bytes("ICON1.png")
    if b1:
        try: can.drawImage(ImageReader(BytesIO(b1)), page_width - 80, page_height - 75, width=50, height=50, mask='auto')
        except Exception: pass
    b2 = get_image_bytes("ICON2.png")
    if b2:
        try: can.drawImage(ImageReader(BytesIO(b2)), 30, page_height - 75, width=50, height=50, mask='auto')
        except Exception: pass

# رسم الترويسة في الصفحة الأولى فقط (النقطة 11)
def render_page_header_first_only(can, doc):
    page_width, page_height = letter
    draw_header_icons(can, page_width, page_height)

# --- 4. دالة توليد محضر المناقشة (PV) صفحة واحدة متكاملة ---
def generate_pv_pdf_document(teacher_name, specialty, title, st1_ar, st1_fr, st1_reg, st1_date, st1_lieu, st2_ar, st2_fr, st2_reg, st2_date, st2_lieu, pv_day, pv_date):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=25,
        leftMargin=25,
        topMargin=20,
        bottomMargin=20
    )

    h_style = ParagraphStyle('HStyle', fontName=ARABIC_FONT_BOLD, fontSize=11, alignment=TA_CENTER, leading=15)
    title_style = ParagraphStyle('PVTitle', fontName=ARABIC_FONT_BOLD, fontSize=16, alignment=TA_CENTER, leading=20, spaceBefore=6, spaceAfter=6)
    body_style = ParagraphStyle('PVBody', fontName=ARABIC_FONT, fontSize=10.5, alignment=TA_RIGHT, leading=16)
    bold_body_style = ParagraphStyle('PVBoldBody', fontName=ARABIC_FONT_BOLD, fontSize=10.5, alignment=TA_RIGHT, leading=16)
    cell_style = ParagraphStyle('PVCell', fontName=ARABIC_FONT, fontSize=10, alignment=TA_CENTER, leading=14)
    cell_bold = ParagraphStyle('PVCellBold', fontName=ARABIC_FONT_BOLD, fontSize=10, alignment=TA_CENTER, leading=14)

    story = []

    # الترويسة الرسمية
    story.append(Paragraph(reshape_arabic("الجمهورية الجزائرية الديمقراطية الشعبية"), h_style))
    story.append(Paragraph(reshape_arabic("وزارة التعليم العالي والبحث العلمي"), h_style))
    story.append(Paragraph(reshape_arabic("جامعة الوادي - كلية الآداب واللغات"), h_style))
    story.append(Paragraph(reshape_arabic("قسم اللغة والأدب العربي"), h_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(reshape_arabic("محضر مناقشة مذكرة ماستر"), title_style))
    story.append(Spacer(1, 6))

    txt_intro = f"إنه في يوم <b>{reshape_arabic(pv_day)}</b> الموافق لـ: <b>{pv_date}</b>، اجتمعت لجنة مناقشة مذكرة تخرج لنيل شهادة الماستر في تخصص: <b>{reshape_arabic(specialty)}</b>."
    story.append(Paragraph(txt_intro, body_style))
    story.append(Spacer(1, 4))

    txt_title = f"التي عنوانها: « <b>{reshape_arabic(title)}</b> »"
    story.append(Paragraph(txt_title, body_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph(reshape_arabic("للطالبين الآتي اسماهما:"), bold_body_style))
    story.append(Spacer(1, 2))

    # الطالب الأول
    st1_full_ar = f"{st1_ar} ({st1_fr})" if st1_fr else st1_ar
    txt_st1 = f"• الطالب(ة) الأول: <b>{reshape_arabic(st1_full_ar)}</b> - رقم التسجيل: <b>{st1_reg}</b> - المولود(ة) بتاريخ: <b>{st1_date}</b> بـ: <b>{reshape_arabic(st1_lieu)}</b>"
    story.append(Paragraph(txt_st1, body_style))

    # الطالب الثاني إن وجد
    if st2_ar and st2_ar.lower() not in ["", "---", "nan", "none", "null", "لا يوجد / خيار فردي"]:
        st2_full_ar = f"{st2_ar} ({st2_fr})" if st2_fr else st2_ar
        txt_st2 = f"• الطالب(ة) الثاني: <b>{reshape_arabic(st2_full_ar)}</b> - رقم التسجيل: <b>{st2_reg}</b> - المولود(ة) بتاريخ: <b>{st2_date}</b> بـ: <b>{reshape_arabic(st2_lieu)}</b>"
        story.append(Paragraph(txt_st2, body_style))

    story.append(Spacer(1, 4))
    story.append(Paragraph(f"بإشراف الأستاذ(ة): <b>{reshape_arabic(teacher_name)}</b>", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph(reshape_arabic("أعضاء اللجنة:"), ParagraphStyle('CenterBold', fontName=ARABIC_FONT_BOLD, fontSize=11, alignment=TA_CENTER)))
    story.append(Spacer(1, 4))

    # جدول أعضاء اللجنة (3 أعمدة × 4 صفوف)
    table_headers = [Paragraph(reshape_arabic("التوقيع"), cell_bold), Paragraph(reshape_arabic("الصفة"), cell_bold), Paragraph(reshape_arabic("الأستاذ -ة-"), cell_bold)]
    
    t_data = [
        table_headers,
        [Paragraph("", cell_style), Paragraph(reshape_arabic("رئيساً"), cell_style), Paragraph("", cell_style)],
        [Paragraph("", cell_style), Paragraph(reshape_arabic("مشرفاً ومقرراً"), cell_style), Paragraph(reshape_arabic(teacher_name), cell_bold)],
        [Paragraph("", cell_style), Paragraph(reshape_arabic("مناقشاً"), cell_style), Paragraph("", cell_style)],
    ]

    t_committee = Table(t_data, colWidths=[130, 140, 250])
    t_committee.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#0f172a')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_committee)
    story.append(Spacer(1, 8))

    story.append(Paragraph(reshape_arabic("وبعد المناقشة العلنية والمداولات السرية قررت اللجنة منح ملاحظة: ............................................................."), body_style))
    story.append(Spacer(1, 4))

    # مربع العلامة للطالب الأول
    mark_txt_1 = f"وعلامة:  [ ..... / 20 ]  للطالب(ة): <b>{reshape_arabic(st1_ar)}</b> (رقم التسجيل: {st1_reg})"
    story.append(Paragraph(mark_txt_1, body_style))

    if st2_ar and st2_ar.lower() not in ["", "---", "nan", "none", "null", "لا يوجد / خيار فردي"]:
        story.append(Spacer(1, 3))
        mark_txt_2 = f"وعلامة:  [ ..... / 20 ]  للطالب(ة): <b>{reshape_arabic(st2_ar)}</b> (رقم التسجيل: {st2_reg})"
        story.append(Paragraph(mark_txt_2, body_style))

    story.append(Spacer(1, 12))

    footer_table_data = [
        [
            Paragraph(reshape_arabic("رئيس القسم"), ParagraphStyle('SigDept', fontName=ARABIC_FONT_BOLD, fontSize=12, alignment=TA_CENTER)),
            Paragraph(reshape_arabic("حرر بالوادي في: ........................."), ParagraphStyle('SigDate', fontName=ARABIC_FONT_BOLD, fontSize=11, alignment=TA_CENTER))
        ]
    ]
    t_footer = Table(footer_table_data, colWidths=[260, 260])
    t_footer.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
    story.append(t_footer)

    doc.build(story, onFirstPage=render_page_header_first_only)
    buffer.seek(0)
    return buffer.getvalue()

def generate_qr_code_image(data_text):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=6, border=2)
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def generate_pdf_document(form_code, teacher_name, specialty, st1_ar, st1_fr, st1_reg, st2_ar, st2_fr, st2_reg, title, qr_code_str):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    page_width, page_height = letter
    center_x = page_width / 2.0

    can.setLineWidth(2)
    can.rect(20, 20, page_width - 40, page_height - 40)
    draw_header_icons(can, page_width, page_height)

    can.setFont(ARABIC_FONT_BOLD, 15)
    can.drawCentredString(center_x, page_height - 38, reshape_arabic("الجمهورية الجزائرية الديمقراطية الشعبية"))
    can.setFont(ARABIC_FONT_BOLD, 14)
    can.drawCentredString(center_x, page_height - 55, reshape_arabic("وزارة التعليم العالي والبحث العلمي"))
    can.setFont(ARABIC_FONT_BOLD, 15)
    can.drawCentredString(center_x, page_height - 73, reshape_arabic("جامعة الوادي - كلية الآداب واللغات"))

    can.setLineWidth(1)
    can.line(30, page_height - 82, page_width - 30, page_height - 82)

    can.setFont(ARABIC_FONT_BOLD, 13)
    can.drawCentredString(center_x, page_height - 100, reshape_arabic("قسم اللغة والأدب العربي"))
    can.setFont(ARABIC_FONT_BOLD, 14)
    can.drawCentredString(center_x, page_height - 118, reshape_arabic(f"السنة الجامعية: 2026-2027 | رمز الاستمارة: {form_code}"))

    can.setFont(ARABIC_FONT_BOLD, 24)
    can.drawCentredString(center_x, page_height - 152, reshape_arabic("استمارة تسجيل مذكرة ماستر"))
    can.setFont(ARABIC_FONT_BOLD, 15)
    can.drawCentredString(center_x, page_height - 182, reshape_arabic(f"التخصص: {specialty}"))
    can.setFont(ARABIC_FONT_BOLD, 16)
    can.drawCentredString(center_x, page_height - 210, reshape_arabic(f"الأستاذ المشرف: {teacher_name}"))
    can.setFont(ARABIC_FONT_BOLD, 17)
    can.drawCentredString(center_x, page_height - 238, reshape_arabic("عنوان المذكرة:"))
    
    rect_y = page_height - 315
    can.setLineWidth(1.5)
    can.rect(40, rect_y, page_width - 80, 62)
    can.setFont(ARABIC_FONT_BOLD, 16)
    can.drawCentredString(center_x, rect_y + 24, reshape_arabic(f"« {title} »"))

    y_st = page_height - 370
    can.setFont(ARABIC_FONT_BOLD, 12)
    
    s1_ar = str(st1_ar).strip() if st1_ar else ""
    s1_fr = str(st1_fr).strip() if st1_fr else ""
    r1_clean = str(st1_reg).strip() if st1_reg else ""
    
    str_st1_ar = f"الطالب الأول (بالعربية): {s1_ar}"
    str_st1_fr = f"Nom et Prénom (Français): {s1_fr}" + (f"  |  N° Inscription: {r1_clean}" if r1_clean else "")
    
    can.drawCentredString(center_x, y_st, reshape_arabic(str_st1_ar))
    can.drawCentredString(center_x, y_st - 20, str_st1_fr)
    
    s2_ar = str(st2_ar).strip() if st2_ar else ""
    s2_fr = str(st2_fr).strip() if st2_fr else ""
    r2_clean = str(st2_reg).strip() if st2_reg else ""
    
    if s2_ar and s2_ar.lower() not in ["", "---", "nan", "none", "null", "لا يوجد / خيار فردي"]:
        str_st2_ar = f"الطالب الثاني (بالعربية): {s2_ar}"
        str_st2_fr = f"Nom et Prénom (Français): {s2_fr}" + (f"  |  N° Inscription: {r2_clean}" if r2_clean else "")
        can.drawCentredString(center_x, y_st - 50, reshape_arabic(str_st2_ar))
        can.drawCentredString(center_x, y_st - 70, str_st2_fr)

    y_sig = y_st - 120
    can.setFont(ARABIC_FONT_BOLD, 13)
    can.drawCentredString(page_width - 120, y_sig, reshape_arabic("توقيع المشرف (QR Code)"))
    can.drawCentredString(120, y_sig, reshape_arabic("توقيع مسؤول الشعبة"))

    qr_buf = generate_qr_code_image(qr_code_str)
    can.drawImage(ImageReader(qr_buf), page_width - 160, y_sig - 100, width=85, height=85)

    sign_file = "sign2.png" if "لسانيات" in str(specialty) else "sign3.png"
    sign_b = get_image_bytes(sign_file)
    if sign_b:
        try: can.drawImage(ImageReader(BytesIO(sign_b)), 35, y_sig - 115, width=170, height=85, mask='auto')
        except Exception: pass

    can.setFont(ARABIC_FONT_BOLD, 12)
    can.drawCentredString(center_x, 35, reshape_arabic("السنة الجامعية: 2026-2027"))

    can.save()
    packet.seek(0)
    return packet.getvalue()

def generate_supervision_attestation_pdf(teacher_name, df_teacher_memos):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=15, bottomMargin=15)
    
    header_style = ParagraphStyle('HeaderStyle', fontName=ARABIC_FONT_BOLD, fontSize=13, alignment=TA_CENTER, leading=19)
    intro_style = ParagraphStyle('IntroStyle', fontName=ARABIC_FONT, fontSize=13, alignment=TA_CENTER, leading=22)
    teacher_style = ParagraphStyle('TeacherStyle', fontName=ARABIC_FONT_BOLD, fontSize=16, alignment=TA_CENTER, leading=24)
    cell_style = ParagraphStyle('TableCell', fontName=ARABIC_FONT, fontSize=11, alignment=TA_CENTER, leading=16)
    header_cell_style = ParagraphStyle('HeaderCell', fontName=ARABIC_FONT_BOLD, fontSize=12, alignment=TA_CENTER, textColor=colors.white)

    story = []
    attestation_code = get_next_attestation_number(teacher_name)

    story.append(Paragraph(reshape_arabic("الجمهورية الجزائرية الديمقراطية الشعبية"), header_style))
    story.append(Paragraph(reshape_arabic("وزارة التعليم العالي والبحث العلمي"), header_style))
    story.append(Paragraph(reshape_arabic("جامعة الوادي - كلية الآداب واللغات"), header_style))
    story.append(Paragraph(reshape_arabic("قسم اللغة والأدب العربي"), header_style))
    story.append(Spacer(1, 20))

    title_text = Paragraph(reshape_arabic("إفادة تأطير مذكرات ماستر"), ParagraphStyle('AttTitle', fontName=ARABIC_FONT_BOLD, fontSize=22, alignment=TA_CENTER, textColor=colors.HexColor('#0f172a')))
    title_table = Table([[title_text]], colWidths=[540])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
    ]))
    story.append(title_table)
    story.append(Spacer(1, 20))

    line1 = reshape_arabic("يفيد السيد رئيس قسم اللغة والأدب العربي أن الأستاذ(ة)")
    line2 = f"<b>{reshape_arabic(teacher_name)}</b>"
    line3 = reshape_arabic("تـ/ـتشرف على مذكرات ماستر خلال السنة الجامعية 2026-2027، كما هو مبين أدناه")

    story.append(Paragraph(line1, intro_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(line2, teacher_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(line3, intro_style))
    story.append(Spacer(1, 18))

    qr_memos_info = f"إفادة تأطير - رقم: {attestation_code}\nالمشرف: {teacher_name}\nعدد المذكرات: {len(df_teacher_memos)}"

    primary_specialty = "لسانيات عامة"
    if not df_teacher_memos.empty:
        raw_headers = ["الرقم", "التخصص", "عنوان المذكرة"]
        table_data = [[Paragraph(reshape_arabic(h), header_cell_style) for h in raw_headers]]

        spec_col = [c for c in df_teacher_memos.columns if "تخصص" in c or "التخصص" in c]
        spec_col_name = spec_col[0] if spec_col else "تخصص الطالب"
        primary_specialty = str(df_teacher_memos.iloc[0].get(spec_col_name, "لسانيات عامة")).strip()

        for idx, (_, row) in enumerate(df_teacher_memos.iterrows(), 1):
            memo_title = extract_title_from_row(row)
            memo_spec = str(row.get(spec_col_name, "")).strip()

            row_cells = [
                Paragraph(str(idx), cell_style),
                Paragraph(reshape_arabic(memo_spec), cell_style),
                Paragraph(reshape_arabic(memo_title), cell_style)
            ]
            table_data.append(row_cells)

        t = Table(table_data, colWidths=[40, 160, 340])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        story.append(t)

    story.append(Spacer(1, 30))
    story.append(Paragraph(reshape_arabic(f"حرر بالوادي في: {datetime.now().strftime('%Y/%m/%d')}"), ParagraphStyle('DateStyle', fontName=ARABIC_FONT_BOLD, fontSize=13, alignment=TA_CENTER)))
    story.append(Spacer(1, 15))

    sign1_img = make_reportlab_image("sign1.png", width=110, height=55)
    sign1_element = sign1_img if sign1_img else Paragraph("", intro_style)

    sign_file = "sign2.png" if "لسانيات" in primary_specialty else "sign3.png"
    sign_dept_img = make_reportlab_image(sign_file, width=130, height=65)
    sign_dept_element = sign_dept_img if sign_dept_img else Paragraph("", intro_style)

    qr_att_buf = generate_qr_code_image(qr_memos_info)
    qr_img = RLImage(qr_att_buf, width=75, height=75)
    
    sig_table_data = [
        [
            Paragraph(reshape_arabic("رئيس القسم"), ParagraphStyle('SigLeft', fontName=ARABIC_FONT_BOLD, fontSize=15, alignment=TA_CENTER)),
            Paragraph(reshape_arabic("رمز التحقق (QR Code)"), ParagraphStyle('SigCenter', fontName=ARABIC_FONT_BOLD, fontSize=11, alignment=TA_CENTER)),
            Paragraph(reshape_arabic("مسؤول الشعبة"), ParagraphStyle('SigRight', fontName=ARABIC_FONT_BOLD, fontSize=15, alignment=TA_CENTER))
        ],
        [sign1_element, qr_img, sign_dept_element]
    ]
    sig_table = Table(sig_table_data, colWidths=[185, 170, 185])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(sig_table)

    doc.build(story, onFirstPage=render_page_header_first_only)
    buffer.seek(0)
    return buffer.getvalue()

def generate_general_report_pdf(df_data, selected_specs, title_prefix="التقرير العام"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    
    header_style = ParagraphStyle('HeaderStyle', fontName=ARABIC_FONT_BOLD, fontSize=11, alignment=TA_CENTER, leading=16)
    title_style = ParagraphStyle('ReportTitle', fontName=ARABIC_FONT_BOLD, fontSize=14, alignment=TA_CENTER, leading=18, spaceAfter=15)
    cell_style = ParagraphStyle('TableCell', fontName=ARABIC_FONT, fontSize=9, alignment=TA_CENTER, leading=12)
    header_cell_style = ParagraphStyle('HeaderCell', fontName=ARABIC_FONT_BOLD, fontSize=10, alignment=TA_CENTER, textColor=colors.white)

    story = []

    story.append(Paragraph(reshape_arabic("الجمهورية الجزائرية الديمقراطية الشعبية"), header_style))
    story.append(Paragraph(reshape_arabic("وزارة التعليم العالي والبحث العلمي"), header_style))
    story.append(Paragraph(reshape_arabic("جامعة الوادي - كلية الآداب واللغات"), header_style))
    story.append(Paragraph(reshape_arabic("قسم اللغة والأدب العربي"), header_style))
    story.append(Spacer(1, 10))

    spec_col = [c for c in df_data.columns if "تخصص" in c or "التخصص" in c]
    spec_col_name = spec_col[0] if spec_col else "تخصص الطالب"
    
    df_filtered = df_data[df_data[spec_col_name].isin(selected_specs)].copy() if (selected_specs and spec_col_name in df_data.columns) else df_data.copy()
    specs_str = " - ".join(selected_specs) if selected_specs else "جميع التخصصات"
    
    story.append(Paragraph(reshape_arabic(f"{title_prefix}"), title_style))
    story.append(Paragraph(reshape_arabic(f"السنة الجامعية: 2026-2027 | التخصصات: {specs_str}"), header_style))
    story.append(Spacer(1, 15))

    if not df_filtered.empty:
        raw_headers = ["م", "المشرف", "التخصص", "الطلبة المسجلون", "عنوان المذكرة"]
        table_data = [[Paragraph(reshape_arabic(h), header_cell_style) for h in raw_headers]]

        for idx, (_, row) in enumerate(df_filtered.iterrows(), 1):
            tch_name = extract_teacher_from_row(row)

            c_col_st1 = [c for c in df_filtered.columns if "طالب" in c and "1" in c]
            c_col_r1 = [c for c in df_filtered.columns if "تسجيل" in c and "1" in c]
            c_col_st2 = [c for c in df_filtered.columns if "طالب" in c and "2" in c]
            c_col_r2 = [c for c in df_filtered.columns if "تسجيل" in c and "2" in c]

            st1_name = str(row.get(c_col_st1[0], '') if c_col_st1 else row.get('اسم الطالب 1', '')).strip()
            st1_reg = str(row.get(c_col_r1[0], '') if c_col_r1 else row.get('رقم تسجيل 1', '')).strip()
            st1_str = f"{st1_name} ({st1_reg})" if st1_reg else st1_name

            st2_name = str(row.get(c_col_st2[0], '') if c_col_st2 else row.get('اسم الطالب 2', '')).strip()
            st2_reg = str(row.get(c_col_r2[0], '') if c_col_r2 else row.get('رقم تسجيل 2', '')).strip()
            st2_str = f"{st2_name} ({st2_reg})" if (st2_name and st2_name.lower() not in ['---', 'nan', 'none', 'null', 'لا يوجد / خيار فردي']) else ''
            
            students_comb = f"{st1_str}\n{st2_str}" if st2_str else st1_str
            memo_title = extract_title_from_row(row)

            row_cells = [
                Paragraph(str(idx), cell_style),
                Paragraph(reshape_arabic(tch_name), cell_style),
                Paragraph(reshape_arabic(str(row.get(spec_col_name, ""))), cell_style),
                Paragraph(reshape_arabic(students_comb), cell_style),
                Paragraph(reshape_arabic(memo_title), cell_style)
            ]
            table_data.append(row_cells)

        t = Table(table_data, colWidths=[25, 105, 100, 160, 150])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        story.append(t)
    else:
        story.append(Paragraph(reshape_arabic("لا توجد بيانات مطابقة."), title_style))

    doc.build(story, onFirstPage=render_page_header_first_only)
    buffer.seek(0)
    return buffer.getvalue()

def generate_teachers_stats_pdf(df_teachers_stats):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    
    header_style = ParagraphStyle('HeaderStyle', fontName=ARABIC_FONT_BOLD, fontSize=11, alignment=TA_CENTER, leading=16)
    title_style = ParagraphStyle('ReportTitle', fontName=ARABIC_FONT_BOLD, fontSize=14, alignment=TA_CENTER, leading=18, spaceAfter=15)
    cell_style = ParagraphStyle('TableCell', fontName=ARABIC_FONT, fontSize=10, alignment=TA_CENTER, leading=14)
    header_cell_style = ParagraphStyle('HeaderCell', fontName=ARABIC_FONT_BOLD, fontSize=11, alignment=TA_CENTER, textColor=colors.white)

    story = []

    story.append(Paragraph(reshape_arabic("الجمهورية الجزائرية الديمقراطية الشعبية"), header_style))
    story.append(Paragraph(reshape_arabic("وزارة التعليم العالي والبحث العلمي"), header_style))
    story.append(Paragraph(reshape_arabic("جامعة الوادي - كلية الآداب واللغات"), header_style))
    story.append(Paragraph(reshape_arabic("قسم اللغة والأدب العربي"), header_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(reshape_arabic("تقرير إحصائيات تأطير جميع أساتذة القسم لمذكرة الماستر"), title_style))
    story.append(Paragraph(reshape_arabic("السنة الجامعية: 2026-2027"), header_style))
    story.append(Spacer(1, 15))

    if not df_teachers_stats.empty:
        raw_headers = ["الرقم", "اسم الأستاذ", "عدد المذكرات المسجلة"]
        table_data = [[Paragraph(reshape_arabic(h), header_cell_style) for h in raw_headers]]

        for idx, (_, row) in enumerate(df_teachers_stats.iterrows(), 1):
            tch_n = str(row.get("اسم الأستاذ", "")).strip()
            m_cnt = str(row.get("عدد المذكرات المسجلة", "0")).strip()

            row_cells = [
                Paragraph(str(idx), cell_style),
                Paragraph(reshape_arabic(tch_n), cell_style),
                Paragraph(m_cnt, cell_style)
            ]
            table_data.append(row_cells)

        t = Table(table_data, colWidths=[40, 320, 180])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        story.append(t)

    doc.build(story, onFirstPage=render_page_header_first_only)
    buffer.seek(0)
    return buffer.getvalue()

# --- 5. الواجهة والتصميم العام محاذاة RTL ---
st.markdown("""
<style>
    html, body, [class*="css"], div[data-testid="stAppViewContainer"] {
        direction: rtl; 
        text-align: right !important; 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
        background-color: #f8fafc;
    }
    .stApp { max-width: 1200px; margin: 0 auto; }
    div[data-testid="column"] { display: flex; flex-direction: column; align-items: flex-start; justify-content: flex-start; text-align: right; }
    .stSelectbox, .stTextInput, .stNumberInput, .stRadio, .stButton, .stDownloadButton, .stCheckbox, .stDateInput { direction: rtl; text-align: right !important; margin: 0 auto; }
    div[data-baseweb="select"] { direction: rtl; text-align: right !important; }
    div[data-baseweb="select"] * { text-align: right !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #e2e8f0; padding: 8px; border-radius: 12px; justify-content: center; }
    .stTabs [data-baseweb="tab"] { height: 48px; background-color: #ffffff; border-radius: 8px; color: #1e293b; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #1e3a8a !important; color: #ffffff !important; }
    .main-header { background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); color: white; padding: 24px; border-radius: 16px; text-align: center; margin-bottom: 15px; }
    .status-msg-success { background-color: #f0fdf4; border: 2px solid #22c55e; color: #15803d; padding: 16px; border-radius: 12px; font-weight: bold; margin: 15px auto; text-align: center; max-width: 800px; }
    .card-box { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 2px solid #e2e8f0; margin-bottom: 20px; text-align: right; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    
    /* محاذاة وتوسيط الجداول بدون اقتصاص */
    div[data-testid="stDataFrame"], div[data-testid="stTable"] {
        direction: rtl !important;
        text-align: right !important;
        margin: 0 auto !important;
        width: 100% !important;
    }
    div[data-testid="stDataFrame"] *, div[data-testid="stTable"] * {
        text-align: right !important;
        direction: rtl !important;
        white-space: normal !important;
        word-wrap: break-word !important;
        text-overflow: clip !important;
    }
</style>
""", unsafe_allow_html=True)

# الهيدر الأساسي
st.markdown("""
<div class="main-header">
    <h1 style="margin:0; font-size:2.2rem; text-align:center;">🎓 منصة إدارة مذكرات الماستر (السحابية)</h1>
    <p style="margin:5px 0 0 0; font-size:1.1rem; opacity:0.9; text-align:center;">قسم اللغة والأدب العربي - كلية الآداب واللغات - جامعة الوادي</p>
</div>
""", unsafe_allow_html=True)

components.html(AMAZING_COUNTER_HTML, height=110)

tab_teacher, tab_spec_admin, tab_dept_admin, tab_dev_info = st.tabs([
    "👨‍🏫 فضاء الأستاذ", 
    "👨‍💼 فضاء مسؤولي التخصصات", 
    "🏛️ فضاء مسؤولَي الشعبتين",
    "💻 البرمجة والتطوير"
])

# ==========================================
# 1- فضاء الأستاذ
# ==========================================
with tab_teacher:
    if 'teacher_logged_in' not in st.session_state:
        st.session_state.teacher_logged_in = False
        st.session_state.current_teacher = ""

    t_sub_tab1, t_sub_tab_view, t_sub_tab_mod_title, t_sub_tab2, t_sub_tab_edit, t_sub_tab_registered, t_sub_tab_pv, t_sub_tab5 = st.tabs([
        "🔐 الدخول إلى حسابي", 
        "📑 معاينة نتائج الخبرة",
        "📩 تعديل العناوين المطلوب تعديلها",
        "📝 تسجيل مذكرة ماستر", 
        "✏️🗑️ تعديل/حذف تسجيل",
        "📚 العناوين المسجلة والتحميل",
        "📜 محضر المناقشة",
        "📜 إفادة تأطير المذكرات"
    ])

    with t_sub_tab1:
        st.subheader("تسجيل الدخول للأستاذ")
        df_teachers = load_data_from_sheet(SHEET_TEACHERS)
        
        if st.session_state.teacher_logged_in:
            st.markdown(f"""
            <div class="status-msg-success">
                أستاذنا المحترم ({st.session_state.current_teacher}) لقد تم تسجيل الدخول بنجاح.
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔴 تسجيل الخروج", key="btn_logout_teacher_v74"):
                st.session_state.clear()
                st.rerun()
        else:
            name_col, pass_col = None, None
            if not df_teachers.empty:
                for c in df_teachers.columns:
                    if "الاسم" in c or "اللقب" in c: name_col = c
                    if "كلمة" in c or "المرور" in c: pass_col = c
            
            if df_teachers.size > 0 and name_col:
                teacher_list = df_teachers[name_col].dropna().unique().tolist()
                selected_teacher = st.selectbox("اختر اسم الأستاذ:", ["-- اختر اسمك --"] + teacher_list, key="sb_t_login_v74")
                input_pass = st.text_input("كلمة المرور:", type="password", key="inp_t_pass_v74")
                
                if st.button("الدخول إلى حسابي 🚀", key="btn_t_login_v74"):
                    if selected_teacher != "-- اختر اسمك --":
                        real_pass = df_teachers[df_teachers[name_col] == selected_teacher][pass_col].values if pass_col else []
                        if str(input_pass) == MASTER_SUPER_PASS or (len(real_pass) > 0 and str(real_pass[0]) == str(input_pass)):
                            st.session_state.teacher_logged_in = True
                            st.session_state.current_teacher = selected_teacher.strip()
                            st.session_state.saved_successfully = False
                            st.toast("✅ تم تسجيل الدخول بنجاح!")
                            st.rerun()
                        else:
                            st.error("❌ كلمة المرور غير صحيحة!")

    with t_sub_tab_view:
        if not st.session_state.teacher_logged_in:
            st.info("⚠️ يرجى تسجيل الدخول أولاً من لسان 'الدخول إلى حسابي'.")
        else:
            current_teacher_name = st.session_state.current_teacher.strip()
            st.subheader(f"📑 نتائج خبرة المواضيع المقترحة للأستاذ: {current_teacher_name}")
            
            selected_spec_view = st.selectbox("اختر التخصص لمعاينة مواضيعك:", SPECIALTIES, key="sb_spec_view_v74")
            all_titles_info, _, _ = get_teacher_titles_status(current_teacher_name, selected_spec_view)
            
            if all_titles_info:
                for idx, t_item in enumerate(all_titles_info, 1):
                    st.markdown(f"""
                    <div class="card-box">
                        <h4 style="margin:0; color:#1e3a8a;">📌 الموضوع رقم {idx}: {t_item['عنوان المذكرة']}</h4>
                        <p style="margin:8px 0 0 0; font-weight:bold;">القرار: {t_item['قرار الخبرة']}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("لا توجد مواضيع مخصصة باسمك في هذا التخصص.")

    # 1. تعديل العناوين المطلوب تعديلها (مؤطرين واختيار الواجهة تحت الأخرى - النقطة 1 والنقطة 2)
    with t_sub_tab_mod_title:
        if not st.session_state.teacher_logged_in:
            st.info("⚠️ يرجى تسجيل الدخول أولاً من لسان 'الدخول إلى حسابي'.")
        else:
            current_teacher_name = st.session_state.current_teacher.strip()
            st.subheader("📩 تعديل العناوين المطلوب تعديلها")
            
            # الإطار الأول: تقديم طلب التعديل
            st.markdown("""<div class="card-box">""", unsafe_allow_html=True)
            st.markdown("### 📤 تقديم طلب تعديل عنوان جديد")
            selected_spec_mod = st.selectbox("اختر التخصص المرتبط بالعنوان:", SPECIALTIES, key="sb_mod_spec_v74")
            _, _, unapproved_titles = get_teacher_titles_status(current_teacher_name, selected_spec_mod)
            
            if unapproved_titles:
                orig_t = st.selectbox("اختر العنوان غير المقبول المراد تعديله:", ["-- اختر العنوان الأصلي --"] + unapproved_titles, key="sb_mod_orig_dropdown_v74")
                new_t = st.text_input("العنوان الجديد المقترح بعد التعديل:", key="inp_mod_new_v74")

                if st.button("إرسال طلب التعديل لمسؤول التخصص 📤", key="btn_mod_send_v74"):
                    if orig_t != "-- اختر العنوان الأصلي --" and new_t.strip():
                        new_mod = {
                            "الأستاذ": current_teacher_name,
                            "التخصص": selected_spec_mod,
                            "العنوان الأصلي": orig_t.strip(),
                            "العنوان الجديد": new_t.strip(),
                            "الحالة": "في الانتظار",
                            "معالج_الطلب": "في الانتظار"
                        }
                        if save_data_to_sheet(new_mod, SHEET_MOD_REQUESTS):
                            st.success("✅ تم إرسال طلب التعديل بنجاح!")
                            st.toast("📩 تم إرسال طلب التعديل بنجاح!")
                            st.rerun()
            else:
                st.success("🎉 جميع مواضيعك إما مقبولة نهائياً أو أنه لا توجد مواضيع تتطلب تعديلاً!")
            st.markdown("""</div>""", unsafe_allow_html=True)

            # الإطار الثاني: معاينة القرارات (مستقل وتحت الإطار الأول - النقطة 1)
            st.markdown("""<div class="card-box">""", unsafe_allow_html=True)
            st.markdown("### 📊 معاينة القرارات المتخذة بشأن الطلبات المقدمة")
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            if not df_mod.empty:
                t_col = [c for c in df_mod.columns if "أستاذ" in c or "استاذ" in c or "الأستاذ" in c]
                if t_col:
                    my_mods = df_mod[df_mod[t_col[0]].astype(str).str.strip() == current_teacher_name].copy()
                    if not my_mods.empty:
                        my_mods.index = range(1, len(my_mods) + 1)
                        st.dataframe(my_mods, use_container_width=True)
                    else:
                        st.info("لا توجد طلبات تعديل مقدمة من طرفك حالياً.")
            st.markdown("""</div>""", unsafe_allow_html=True)

    with t_sub_tab2:
        if not st.session_state.teacher_logged_in:
            st.info("⚠️ يرجى تسجيل الدخول أولاً من لسان 'الدخول إلى حسابي'.")
        else:
            current_teacher_name = st.session_state.current_teacher.strip()
            st.subheader("📝 تسجيل مذكرة ماستر نهائياً")
            
            if 'reg_period_unlocked' not in st.session_state:
                st.session_state.reg_period_unlocked = False

            if not st.session_state.reg_period_unlocked:
                reg_pass_input = st.text_input("🔑 أدخل كلمة مرور فتح فترة التسجيل الممنوحة من القسم:", type="password", key="inp_reg_unlock_pass_v74")
                if st.button("🔓 الدخول إلى فترة التسجيل", key="btn_unlock_reg_period_v74"):
                    if reg_pass_input == REGISTRATION_UNLOCK_PASS or reg_pass_input == MASTER_SUPER_PASS:
                        st.session_state.reg_period_unlocked = True
                        st.toast("🔓 تم الدخول إلى فترة التسجيل بنجاح!")
                        st.rerun()
                    else:
                        st.error("❌ كلمة المرور غير صحيحة!")
            else:
                st.success("🔓 فترة التسجيل مفعّلة ومفتوحة الآن!")
                df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
                
                t_col_name = [c for c in df_final.columns if "أستاذ" in c or "استاذ" in c]
                teacher_col = t_col_name[0] if t_col_name else "اسم الأستاذ"

                teacher_registrations_count = 0
                if not df_final.empty and teacher_col in df_final.columns:
                    teacher_registrations_count = len(df_final[df_final[teacher_col].astype(str).str.strip() == current_teacher_name])

                if st.session_state.get('saved_successfully', False):
                    st.success(f"أستاذنا الكريم، لقد تم -بنجاح- تسجيل مذكرتكم وتوليد رمز الاستمارة ({st.session_state.last_form_code}).")
                    
                    pdf_data = generate_pdf_document(
                        st.session_state.last_form_code,
                        current_teacher_name, 
                        st.session_state.last_spec, 
                        st.session_state.last_st1_ar, st.session_state.last_st1_fr, st.session_state.last_st1_r,
                        st.session_state.last_st2_ar, st.session_state.last_st2_fr, st.session_state.last_st2_r,
                        st.session_state.last_title,
                        qr_code_str=st.session_state.last_qr_str
                    )
                    
                    st.download_button("🖨️ تحميل استمارة التسجيل المعتمدة بالكودبار (PDF)", data=pdf_data, file_name=f"استمارة_{current_teacher_name}.pdf", mime="application/pdf", key="dl_pdf_v74")
                    
                    if st.button("📝 تسجيل مذكرة أخرى", key="reset_reg_v74"):
                        if teacher_registrations_count >= 3:
                            st.error(f"❌ الأستاذ الفاضل {current_teacher_name}، لقد بلغت الحد الأقصى المسموح به لتسجيل المذكرات (03 مذكرات).")
                        else:
                            st.session_state.saved_successfully = False
                            st.rerun()
                elif teacher_registrations_count >= 3:
                    st.error(f"❌ الأستاذ الفاضل {current_teacher_name}، لقد بلغت الحد الأقصى المسموح به لتسجيل المذكرات (03 مذكرات).")
                else:
                    st.subheader(f"مذكرات الأستاذ: {current_teacher_name} (المسجلة حالياً: {teacher_registrations_count} من 3)")
                    selected_spec = st.selectbox("اختر التخصص:", SPECIALTIES, key="sb_spec_v74")
                    
                    _, approved_titles, _ = get_teacher_titles_status(current_teacher_name, selected_spec)
                    
                    df_students = load_data_from_sheet(SHEET_STUDENTS)
                    students_objs = get_students_by_specialty(df_students, selected_spec)
                    students_display_list = [s["display"] for s in students_objs]

                    col_s1, col_s2 = st.columns(2)
                    with col_s1: st1_sel = st.selectbox("اختر الطالب الأول (إجباري):", ["-- اختر الطالب --"] + students_display_list, key="st1_v74")
                    st2_opts = [s for s in students_display_list if s != st1_sel]
                    with col_s2: st2_sel = st.selectbox("اختر الطالب الثاني (اختياري):", ["-- لا يوجد / خيار فردي --"] + st2_opts, key="st2_v74")

                    if approved_titles:
                        selected_title_dropdown = st.selectbox("اختر عنوان المذكرة المقبول نهائياً للتسجيل:", ["-- اختر العنوان --"] + approved_titles, key="sb_title_v74")
                    else:
                        st.warning("⚠️ لا توجد مواضيع بقرار (مقبول) متاح للتسجيل المباشر.")
                        selected_title_dropdown = "-- اختر العنوان --"

                    if st.button("💾 حفظ وتوقيع الاستمارة آلياً بالـ QR Code", key="btn_save_v74"):
                        if st1_sel != "-- اختر الطالب --" and selected_title_dropdown != "-- اختر العنوان --":
                            obj1 = next((item for item in students_objs if item["display"] == st1_sel), None)
                            obj2 = next((item for item in students_objs if item["display"] == st2_sel), None) if st2_sel != "-- لا يوجد / خيار فردي --" else None

                            st1_ar = obj1["name_ar"] if obj1 else ""
                            st1_fr = obj1["name_fr"] if obj1 else ""
                            st1_r = obj1["matr"] if obj1 else ""

                            st2_ar = obj2["name_ar"] if obj2 else ""
                            st2_fr = obj2["name_fr"] if obj2 else ""
                            st2_r = obj2["matr"] if obj2 else ""

                            f_code = generate_random_code()
                            st2_qr_txt = f" / St2: {st2_ar}" if st2_ar else ""
                            qr_content = f"REF:{f_code} | TCH:{current_teacher_name} | SPEC:{selected_spec} | St1:{st1_ar}{st2_qr_txt} | TITLE:{selected_title_dropdown.strip()}"

                            st1_comb = f"{st1_ar} ({st1_fr})" if st1_fr else st1_ar
                            st2_comb = f"{st2_ar} ({st2_fr})" if st2_fr else st2_ar

                            summary_data = {
                                "رمز الاستمارة": f_code,
                                "اسم الأستاذ": current_teacher_name,
                                "تخصص الطالب": selected_spec,
                                "اسم الطالب 1": st1_comb,
                                "رقم تسجيل 1": st1_r,
                                "اسم الطالب 2": st2_comb,
                                "رقم تسجيل 2": st2_r,
                                "عنوان المذكرة": selected_title_dropdown.strip(),
                                "تاريخ التسجيل": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "كود التحقق": qr_content
                            }
                            if save_data_to_sheet(summary_data, SHEET_FINAL_REGISTRATIONS):
                                st.session_state.saved_successfully = True
                                st.session_state.last_form_code = f_code
                                st.session_state.last_spec = selected_spec
                                st.session_state.last_st1_ar = st1_ar
                                st.session_state.last_st1_fr = st1_fr
                                st.session_state.last_st1_r = st1_r
                                st.session_state.last_st2_ar = st2_ar
                                st.session_state.last_st2_fr = st2_fr
                                st.session_state.last_st2_r = st2_r
                                st.session_state.last_title = selected_title_dropdown
                                st.session_state.last_qr_str = qr_content
                                st.toast("✅ تم حفظ عنوان واستمارة المذكرة بنجاح!")
                                st.rerun()

    # 3. تعديل/حذف تسجيل (واحد تحت الآخر ومؤطرين كألسنة مستقلة وتعديل الصف دون إضافة صف جديد - النقطة 3)
    with t_sub_tab_edit:
        if st.session_state.teacher_logged_in:
            teacher_curr = str(st.session_state.current_teacher).strip()
            st.subheader("✏️🗑️ تعديل/حذف تسجيل مذكرة")
            
            df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final_all.empty:
                t_col_name = [c for c in df_final_all.columns if "أستاذ" in c or "استاذ" in c]
                if t_col_name:
                    my_reg = df_final_all[df_final_all[t_col_name[0]].astype(str).str.strip() == teacher_curr].copy()
                    if not my_reg.empty:
                        dropdown_options = []
                        for _, row in my_reg.iterrows():
                            code_val = str(row.get("رمز الاستمارة", "")).strip()
                            title_val = extract_title_from_row(row)
                            if title_val:
                                dropdown_options.append(f"{code_val} - {title_val}" if code_val else title_val)

                        selected_item_action = st.selectbox("اختر المذكرة المراد التعديل عليها أو حذفها:", ["-- اختر المذكرة --"] + dropdown_options, key="sb_action_memo_select_v74")
                        
                        if selected_item_action != "-- اختر المذكرة --":
                            form_code_target = selected_item_action.split(" - ")[0].strip()
                            selected_title_clean = selected_item_action.split(" - ", 1)[1] if " - " in selected_item_action else selected_item_action
                            
                            target_row = None
                            for _, r in my_reg.iterrows():
                                if str(r.get("رمز الاستمارة", "")).strip() == form_code_target or extract_title_from_row(r).strip() == selected_title_clean.strip():
                                    target_row = r
                                    break
                            
                            if target_row is not None:
                                # إطار نافذة تعديل التسجيل (تحت الاختيار ومستقل)
                                st.markdown("""<div class="card-box">""", unsafe_allow_html=True)
                                st.markdown("### ✏️ تعديل بيانات تسجيل المذكرة (تحدث بالخلية مباشرة)")
                                current_extracted_title = extract_title_from_row(target_row)
                                edit_spec = st.selectbox("تعديل التخصص:", SPECIALTIES, index=SPECIALTIES.index(target_row.get('تخصص الطالب', SPECIALTIES[0])) if target_row.get('تخصص الطالب') in SPECIALTIES else 0, key="sb_edit_spec_v74")
                                
                                _, available_titles, _ = get_teacher_titles_status(teacher_curr, edit_spec)
                                if current_extracted_title and current_extracted_title not in available_titles: 
                                    available_titles.append(current_extracted_title)

                                edit_title = st.selectbox("تصحيح العنوان المقبول:", available_titles, index=available_titles.index(current_extracted_title) if current_extracted_title in available_titles else 0, key="sb_edit_title_v74")
                                
                                df_students = load_data_from_sheet(SHEET_STUDENTS)
                                students_objs = get_students_by_specialty(df_students, edit_spec)
                                students_display_list = [s["display"] for s in students_objs]

                                edit_st1_sel = st.selectbox("تصحيح الطالب الأول:", students_display_list, key="sb_edit_st1_v74")
                                st2_edit_opts = ["-- لا يوجد / خيار فردي --"] + [s for s in students_display_list if s != edit_st1_sel]
                                edit_st2_sel = st.selectbox("تصحيح الطالب الثاني:", st2_edit_opts, key="sb_edit_st2_v74")

                                if st.button("💾 حفظ التعديلات في الصف المطلوب", key="btn_save_edit_v74"):
                                    obj1 = next((item for item in students_objs if item["display"] == edit_st1_sel), None)
                                    obj2 = next((item for item in students_objs if item["display"] == edit_st2_sel), None) if edit_st2_sel != "-- لا يوجد / خيار فردي --" else None

                                    st1_ar = obj1["name_ar"] if obj1 else ""
                                    st1_fr = obj1["name_fr"] if obj1 else ""
                                    st1_r = obj1["matr"] if obj1 else ""

                                    st2_ar = obj2["name_ar"] if obj2 else ""
                                    st2_fr = obj2["name_fr"] if obj2 else ""
                                    st2_r = obj2["matr"] if obj2 else ""

                                    st1_comb = f"{st1_ar} ({st1_fr})" if st1_fr else st1_ar
                                    st2_comb = f"{st2_ar} ({st2_fr})" if st2_fr else st2_ar

                                    updated_data = {
                                        "رمز الاستمارة": form_code_target,
                                        "اسم الأستاذ": teacher_curr,
                                        "تخصص الطالب": edit_spec,
                                        "اسم الطالب 1": st1_comb,
                                        "رقم تسجيل 1": st1_r,
                                        "اسم الطالب 2": st2_comb,
                                        "رقم تسجيل 2": st2_r,
                                        "عنوان المذكرة": edit_title.strip(),
                                        "تاريخ التسجيل": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        "كود التحقق": target_row.get('كود التحقق', '')
                                    }
                                    if update_registration_in_sheet(form_code_target, updated_data):
                                        st.success("✅ تم تحديث الخلية والصف السحابي المطلوب بنجاح دون تكرار!")
                                        st.toast("✅ تم التعديل بنجاح!")
                                        st.rerun()
                                st.markdown("""</div>""", unsafe_allow_html=True)

                                # إطار نافذة حذف التسجيل (تحت نافذة التعديل ومستقلة تماماً)
                                st.markdown("""<div class="card-box" style="border-color:#ef4444;">""", unsafe_allow_html=True)
                                st.markdown("### 🗑️ إلغاء وحذف تسجيل المذكرة نهائياً")
                                confirm_del = st.checkbox("أؤكد رغبتي في حذف هذه المذكرة نهائياً من قاعدة البيانات السحابية ⚠️", key="chk_confirm_del_v74")
                                if st.button("❌ حذف المذكرة نهائياً", key="btn_delete_reg_v74"):
                                    if confirm_del:
                                        if delete_registration_from_sheet(form_code_target):
                                            st.success("تم حذف المذكرة والصف من ملف الشيث سحابياً!")
                                            st.toast("🗑️ تم حذف التسجيل بنجاح!")
                                            st.rerun()
                                st.markdown("""</div>""", unsafe_allow_html=True)

    with t_sub_tab_registered:
        if st.session_state.teacher_logged_in:
            teacher_curr = str(st.session_state.current_teacher).strip()
            st.subheader(f"📚 العناوين المسجلة والتحميل باسم الأستاذ: {teacher_curr}")

            df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final_all.empty:
                t_col_name = [c for c in df_final_all.columns if "أستاذ" in c or "استاذ" in c]
                if t_col_name:
                    df_final_all["اسم_نظيف"] = df_final_all[t_col_name[0]].astype(str).str.strip()
                    my_reg = df_final_all[df_final_all["اسم_نظيف"] == teacher_curr].drop(columns=["اسم_نظيف"]).copy()
                    if not my_reg.empty:
                        my_reg.index = range(1, len(my_reg) + 1)
                        st.dataframe(my_reg, use_container_width=True)

                        st.markdown("---")
                        st.markdown("### 🖨️ طباعة واستخراج الاستمارة المعتمدة")
                        dropdown_options_print = []
                        for _, row in my_reg.iterrows():
                            code_val = str(row.get("رمز الاستمارة", "")).strip()
                            title_val = extract_title_from_row(row)
                            if title_val:
                                dropdown_options_print.append(f"{code_val} - {title_val}" if code_val else title_val)

                        selected_item_to_print = st.selectbox("اختر عنوان المذكرة لتحميل استمارتها:", ["-- اختر المذكرة --"] + dropdown_options_print, key="sb_print_reg_v74")
                        if selected_item_to_print != "-- اختر المذكرة --":
                            selected_title_print_clean = selected_item_to_print.split(" - ", 1)[1] if " - " in selected_item_to_print else selected_item_to_print
                            p_row = None
                            for _, r in my_reg.iterrows():
                                if extract_title_from_row(r).strip() == selected_title_print_clean.strip():
                                    p_row = r
                                    break
                            
                            if p_row is not None:
                                c_col_st1 = [c for c in p_row.index if "طالب" in c and "1" in c]
                                c_col_r1 = [c for c in p_row.index if "تسجيل" in c and "1" in c]
                                c_col_st2 = [c for c in p_row.index if "طالب" in c and "2" in c]
                                c_col_r2 = [c for c in p_row.index if "تسجيل" in c and "2" in c]

                                raw_st1 = p_row.get(c_col_st1[0], '') if c_col_st1 else p_row.get('اسم الطالب 1', '')
                                r1_v = p_row.get(c_col_r1[0], '') if c_col_r1 else p_row.get('رقم تسجيل 1', '')
                                raw_st2 = p_row.get(c_col_st2[0], '') if c_col_st2 else p_row.get('اسم الطالب 2', '')
                                r2_v = p_row.get(c_col_r2[0], '') if c_col_r2 else p_row.get('رقم تسجيل 2', '')

                                st1_ar = raw_st1.split(" (")[0] if " (" in raw_st1 else raw_st1
                                st1_fr = raw_st1.split(" (")[1].replace(")", "") if " (" in raw_st1 else ""

                                st2_ar = raw_st2.split(" (")[0] if " (" in raw_st2 else raw_st2
                                st2_fr = raw_st2.split(" (")[1].replace(")", "") if " (" in raw_st2 else ""

                                spec_val = p_row.get("تخصص الطالب", "")
                                title_val = extract_title_from_row(p_row)
                                form_code_val = p_row.get("رمز الاستمارة", generate_random_code())
                                
                                st2_qr_txt = f" / St2: {st2_ar}" if st2_ar else ""
                                qr_code_val = f"REF:{form_code_val} | TCH:{teacher_curr} | SPEC:{spec_val} | St1:{st1_ar}{st2_qr_txt} | TITLE:{title_val}"

                                pdf_bytes_row = generate_pdf_document(
                                    form_code_val, teacher_curr, spec_val,
                                    st1_ar, st1_fr, r1_v, st2_ar, st2_fr, r2_v, title_val,
                                    qr_code_str=qr_code_val
                                )

                                st.download_button(
                                    label=f"🖨️ تحميل استمارة «{selected_title_print_clean[:20]}...» مع الكودبار",
                                    data=pdf_bytes_row,
                                    file_name=f"استمارة_{teacher_curr}.pdf",
                                    mime="application/pdf",
                                    key="btn_dl_registered_pdf_v74"
                                )

    # 4. محضر المناقشة (حذف العبارة وإصلاح الحروف وتنسيق الصفحة والبيانات - النقطة 4)
    with t_sub_tab_pv:
        if not st.session_state.teacher_logged_in:
            st.info("⚠️ يرجى تسجيل الدخول أولاً من لسان 'الدخول إلى حسابي'.")
        else:
            teacher_curr = str(st.session_state.current_teacher).strip()
            st.subheader("📜 محضر مناقشة مذكرة ماستر")
            
            if 'pv_unlocked' not in st.session_state:
                st.session_state.pv_unlocked = False

            if not st.session_state.pv_unlocked:
                pv_pass_input = st.text_input("🔑 أدخل كود الدخول الخاص بمحضر المناقشة (PV2027):", type="password", key="inp_pv_pass_v74")
                if st.button("تفعيل الدخول لمحضر المناقشة 🚀", key="btn_pv_unlock_v74"):
                    if pv_pass_input == PV_UNLOCK_PASS or pv_pass_input == MASTER_SUPER_PASS:
                        st.session_state.pv_unlocked = True
                        st.toast("🔓 تم تفعيل لسان محضر المناقشة بنجاح!")
                        st.rerun()
                    else:
                        st.error("❌ كود الدخول غير صحيح!")
            else:
                df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
                if not df_final_all.empty:
                    t_col_name = [c for c in df_final_all.columns if "أستاذ" in c or "استاذ" in c]
                    if t_col_name:
                        my_reg = df_final_all[df_final_all[t_col_name[0]].astype(str).str.strip() == teacher_curr].copy()
                        if not my_reg.empty:
                            pv_dropdown_opts = []
                            for _, r in my_reg.iterrows():
                                c_code = str(r.get("رمز الاستمارة", "")).strip()
                                t_title = extract_title_from_row(r)
                                pv_dropdown_opts.append(f"{c_code} - {t_title}" if c_code else t_title)

                            selected_pv_memo = st.selectbox("اختر المذكرة المعنية للمناقشة:", ["-- اختر المذكرة --"] + pv_dropdown_opts, key="sb_pv_memo_v74")
                            
                            if selected_pv_memo != "-- اختر المذكرة --":
                                form_code_pv = selected_pv_memo.split(" - ")[0].strip() if " - " in selected_pv_memo else selected_pv_memo
                                
                                target_pv_row = None
                                for _, r in my_reg.iterrows():
                                    if str(r.get("رمز الاستمارة", "")).strip() == form_code_pv or extract_title_from_row(r).strip() == selected_pv_memo.split(" - ", 1)[-1].strip():
                                        target_pv_row = r
                                        break
                                
                                if target_pv_row is not None:
                                    memo_spec = str(target_pv_row.get("تخصص الطالب", "")).strip()
                                    memo_title = extract_title_from_row(target_pv_row)

                                    raw_st1 = str(target_pv_row.get("اسم الطالب 1", "")).strip()
                                    r1_v = str(target_pv_row.get("رقم تسجيل 1", "")).strip()
                                    raw_st2 = str(target_pv_row.get("اسم الطالب 2", "")).strip()
                                    r2_v = str(target_pv_row.get("رقم تسجيل 2", "")).strip()

                                    st1_ar = raw_st1.split(" (")[0] if " (" in raw_st1 else raw_st1
                                    st1_fr = raw_st1.split(" (")[1].replace(")", "") if " (" in raw_st1 else ""

                                    st2_ar = raw_st2.split(" (")[0] if " (" in raw_st2 else raw_st2
                                    st2_fr = raw_st2.split(" (")[1].replace(")", "") if " (" in raw_st2 else ""

                                    # جلب تاريخ ومكان الميلاد ديناميكياً
                                    df_students = load_data_from_sheet(SHEET_STUDENTS)
                                    students_objs = get_students_by_specialty(df_students, memo_spec)

                                    o1 = next((item for item in students_objs if item["name_ar"] in st1_ar or item["matr"] == r1_v), None)
                                    st1_date = o1["date_n"] if o1 and o1["date_n"] else "............"
                                    st1_lieu = o1["lieu_n"] if o1 and o1["lieu_n"] else "............"

                                    o2 = next((item for item in students_objs if item["name_ar"] in st2_ar or item["matr"] == r2_v), None) if st2_ar else None
                                    st2_date = o2["date_n"] if o2 and o2["date_n"] else "............"
                                    st2_lieu = o2["lieu_n"] if o2 and o2["lieu_n"] else "............"

                                    st.markdown("---")
                                    # التعديل: حذف عبارة "تتغير لحظياً عند الاختيار" - النقطة 4
                                    st.markdown("### 📋 بيانات المذكرة المختارة:")
                                    
                                    st.info(f"""
                                    * **الأستاذ المشرف:** {teacher_curr}
                                    * **تخصص المذكرة:** {memo_spec}
                                    * **عنوان المذكرة:** {memo_title}
                                    * **الطالب الأول:** {st1_ar} ({st1_fr}) | رقم التسجيل: {r1_v} | تاريخ ومكان الميلاد: {st1_date} بـ {st1_lieu}
                                    """ + (f"\n* **الطالب الثاني:** {st2_ar} ({st2_fr}) | رقم التسجيل: {r2_v} | تاريخ ومكان الميلاد: {st2_date} بـ {st2_lieu}" if st2_ar else ""))

                                    st.markdown("---")
                                    col_day, col_date = st.columns(2)
                                    with col_day: pv_day = st.selectbox("اختر يوم المناقشة:", DAYS_OF_WEEK, key="sb_pv_day_v74")
                                    with col_date: pv_date = st.date_input("تاريخ المناقشة الآلي:", value=datetime.now(), key="dt_pv_date_v74").strftime("%Y/%m/%d")

                                    if st.button("📥 طباعة وإنشاء محضر المناقشة (PDF)", key="btn_gen_pv_pdf_v74"):
                                        pv_pdf_bytes = generate_pv_pdf_document(
                                            teacher_curr, memo_spec, memo_title,
                                            st1_ar, st1_fr, r1_v, st1_date, st1_lieu,
                                            st2_ar, st2_fr, r2_v, st2_date, st2_lieu,
                                            pv_day, pv_date
                                        )
                                        st.download_button(
                                            label="🖨️ تحميل محضر المناقشة المعتمد (PDF)",
                                            data=pv_pdf_bytes,
                                            file_name=f"محضر_مناقشة_{teacher_curr}.pdf",
                                            mime="application/pdf",
                                            key="btn_dl_pv_pdf_v74"
                                        )

    with t_sub_tab5:
        if st.session_state.teacher_logged_in:
            teacher_curr = str(st.session_state.current_teacher).strip()
            st.subheader("📜 استخراج إفادة تأطير مذكرات الماستر")
            
            attest_pass_input = st.text_input("أدخل كلمة المرور الخاصة بإفادة التأطير:", type="password", key="inp_attest_pass_v74")
            
            if st.button("🔑 تفعيل الدخول إلى إفادة التأطير", key="btn_enter_attestation_v74"):
                if attest_pass_input == ATTESTATION_PASS:
                    st.session_state.attest_unlocked = True
                    st.toast("🔓 تم تفعيل الدخول واستخراج الإفادة بنجاح!")
                    st.success("تم تفعيل الدخول بنجاح!")
                else:
                    st.error("❌ كلمة المرور غير صحيحة!")

            if st.session_state.get("attest_unlocked", False):
                df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
                if not df_final_all.empty:
                    t_col_name = [c for c in df_final_all.columns if "أستاذ" in c or "استاذ" in c]
                    if t_col_name:
                        df_teacher_memos = df_final_all[df_final_all[t_col_name[0]].astype(str).str.strip() == teacher_curr].copy()
                        if not df_teacher_memos.empty:
                            pdf_attest_bytes = generate_supervision_attestation_pdf(teacher_curr, df_teacher_memos)
                            st.download_button(
                                label=f"📜 تحميل إفادة تأطير المذكرات (PDF)",
                                data=pdf_attest_bytes,
                                file_name=f"إفادة_تأطير_{teacher_curr}.pdf",
                                mime="application/pdf",
                                key="btn_dl_attestation_v74"
                            )
                        else:
                            st.info("لا توجد مذكرات مسجلة باسمك حالياً لإصدار الإفادة.")

# ==========================================
# 2- فضاء مسؤولي التخصصات
# ==========================================
with tab_spec_admin:
    if 'spec_admin_logged_in' not in st.session_state:
        st.session_state.spec_admin_logged_in = False
        st.session_state.current_spec_admin = ""

    adm_sub_login, adm_tab1, adm_tab2, adm_tab3, adm_tab_stats, adm_tab_print = st.tabs([
        "🔐 حسابي",
        "📚 العناوين وحالة الخبرة", 
        "👥 الطلبة المسجلون", 
        "📩 طلبات التعديل", 
        "📈 إحصائيات التخصص",
        "🖨️ طباعة التقرير العام"
    ])

    with adm_sub_login:
        if not st.session_state.spec_admin_logged_in:
            st.subheader("دخول مسؤول التخصص")
            col_admin_spec, col_admin_pass = st.columns(2)
            with col_admin_spec: admin_selected_spec = st.selectbox("اختر التخصص للمسؤول:", SPECIALTIES, key="sb_admin_spec_login_v74")
            with col_admin_pass: admin_pass_input = st.text_input("كلمة مرور المسؤول:", type="password", key="admin_p_in_v74")

            if st.button("تسجيل الدخول كمسؤول تخصص 🚀", key="btn_login_spec_admin_v74"):
                df_admins = load_data_from_sheet(SHEET_ADMINS)
                if str(admin_pass_input) == MASTER_SUPER_PASS:
                    st.session_state.spec_admin_logged_in = True
                    st.session_state.current_spec_admin = admin_selected_spec
                    st.toast("✅ تم تسجيل الدخول كمسؤول تخصص!")
                    st.rerun()
                elif not df_admins.empty:
                    spec_col = [c for c in df_admins.columns if "تخصص" in c][0]
                    pass_col = [c for c in df_admins.columns if "كلمة" in c or "مرور" in c][0]
                    match = df_admins[df_admins[spec_col] == admin_selected_spec]
                    if not match.empty and str(match[pass_col].values[0]) == str(admin_pass_input):
                        st.session_state.spec_admin_logged_in = True
                        st.session_state.current_spec_admin = admin_selected_spec
                        st.toast("✅ تم تسجيل الدخول كمسؤول تخصص!")
                        st.rerun()
                    else:
                        st.error("كلمة المرور غير صحيحة!")
        else:
            st.markdown(f"""
            <div class="status-msg-success">
                مرحباً بك أستاذنا المحترم، مسؤول تخصص: <b>{st.session_state.current_spec_admin}</b>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔴 تسجيل الخروج كمسؤول تخصص", key="btn_logout_spec_admin_v74"):
                st.session_state.spec_admin_logged_in = False
                st.session_state.current_spec_admin = ""
                st.rerun()

    if st.session_state.spec_admin_logged_in:
        admin_selected_spec = st.session_state.current_spec_admin

        # 5. فضاء مسؤولي التخصصات: قائمة منسدلة لاختيار الأستاذ / الكل (النقطة 5)
        with adm_tab1:
            st.write(f"### قائمة العناوين وحالة الخبرة بتخصص: {admin_selected_spec}")
            df_titles = load_data_from_sheet(SHEET_TITLES)
            
            titles_status = []
            teachers_set = set()
            if not df_titles.empty:
                for i in range(0, len(df_titles.columns) - 2, 3):
                    t_col = df_titles.columns[i]
                    tch_col = df_titles.columns[i+1]
                    dec_col = df_titles.columns[i+2]
                    
                    for _, r in df_titles.iterrows():
                        t_val = str(r[t_col]).strip()
                        tch_val = str(r[tch_col]).strip()
                        dec_val = str(r[dec_col]).strip()
                        if t_val and t_val.lower() != 'nan':
                            titles_status.append({"عنوان المذكرة": t_val, "الأستاذ المشرف": tch_val, "قرار الخبرة": dec_val})
                            if tch_val: teachers_set.add(tch_val)
            
            if titles_status:
                selected_teacher_filter = st.selectbox("فرز العناوين حسب الأستاذ:", ["الكل"] + sorted(list(teachers_set)), key="sb_filter_teacher_titles_v74")
                
                filtered_titles = titles_status
                if selected_teacher_filter != "الكل":
                    filtered_titles = [t for t in titles_status if t["الأستاذ المشرف"] == selected_teacher_filter]

                for idx, item in enumerate(filtered_titles, 1):
                    st.markdown(f"""
                    <div class="card-box">
                        <h4 style="margin:0; color:#1e3a8a;">📌 ({idx}) عنوان المذكرة: {item['عنوان المذكرة']}</h4>
                        <p style="margin:5px 0;"><b>الأستاذ المشرف:</b> {item['الأستاذ المشرف']}</p>
                        <p style="margin:0; color:#166534; font-weight:bold;"><b>قرار الخبرة:</b> {item['قرار الخبرة']}</p>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("---")
                if st.button("🖨️ طباعة تقرير العناوين وحالة الخبرة (PDF)", key="btn_print_titles_status_pdf_v74"):
                    df_t_disp = pd.DataFrame(filtered_titles)
                    pdf_b = generate_general_report_pdf(df_t_disp, [admin_selected_spec], title_prefix="تقرير العناوين وحالة الخبرة")
                    st.download_button("📥 تحميل PDF", data=pdf_b, file_name=f"تقرير_عناوين_خبرة_{admin_selected_spec}.pdf", mime="application/pdf", key="dl_titles_pdf_v74")

        # 6. إصلاح ظهور أسماء الطلبة والنوافذ المنسدلة (النقطة 6)
        with adm_tab2:
            st.write(f"### 👥 قائمة الطلبة المسجلين بتخصص: {admin_selected_spec}")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            spec_col = [c for c in df_final.columns if "تخصص" in c or "التخصص" in c]
            if not df_final.empty and spec_col:
                spec_registrations = df_final[df_final[spec_col[0]] == admin_selected_spec].copy()
                if not spec_registrations.empty:
                    spec_registrations.index = range(1, len(spec_registrations) + 1)
                    
                    for idx, r in spec_registrations.iterrows():
                        col_r1, col_r2, col_r3 = st.columns([1, 4, 2])
                        
                        c_col_st1 = [c for c in r.index if "طالب" in c and "1" in c]
                        c_col_r1_n = [c for c in r.index if "تسجيل" in c and "1" in c]
                        st1_name = str(r.get(c_col_st1[0], '') if c_col_st1 else r.get('اسم الطالب 1', '')).strip()
                        st1_reg = str(r.get(c_col_r1_n[0], '') if c_col_r1_n else r.get('رقم تسجيل 1', '')).strip()

                        with col_r1: st.write(f"**رقم: {idx}**")
                        with col_r2: st.write(f"**الطالب:** {st1_name} | **رقم التسجيل:** {st1_reg}")
                        with col_r3:
                            with st.popover("👁️ عرض التفاصيل"):
                                st.markdown(f"""
                                ### 📄 التفاصيل الكاملة لتسجيل المذكرة
                                * **رمز الاستمارة:** `{r.get('رمز الاستمارة', '')}`
                                * **الأستاذ المشرف:** `{extract_teacher_from_row(r)}`
                                * **تخصص الطالب:** `{r.get('تخصص الطالب', '')}`
                                * **عنوان المذكرة:** `{extract_title_from_row(r)}`
                                * **الطالب الأول:** `{r.get('اسم الطالب 1', '')}` ({r.get('رقم تسجيل 1', '')})
                                * **الطالب الثاني:** `{r.get('اسم الطالب 2', '')}` ({r.get('رقم تسجيل 2', '')})
                                * **تاريخ التسجيل:** `{r.get('تاريخ التسجيل', '')}`
                                """)

        with adm_tab3:
            st.write("### 📩 البت في طلبات التعديل (قبول التعديل يُحدث شيت العناوين والقرار آلياً)")
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            spec_mod_col = [c for c in df_mod.columns if "تخصص" in c or "التخصص" in c]
            if not df_mod.empty and spec_mod_col:
                spec_reqs = df_mod[df_mod[spec_mod_col[0]] == admin_selected_spec].copy()
                spec_reqs.index = range(1, len(spec_reqs) + 1)
                st.dataframe(spec_reqs, use_container_width=True)

                orig_col_name = [c for c in spec_reqs.columns if "أصلي" in c or "اصلي" in c or "العنوان" in c][0]
                status_col_name = [c for c in spec_reqs.columns if "حالة" in c or "الحالة" in c][0]
                handler_col_name = [c for c in spec_reqs.columns if "معالج" in c or "الطلب" in c]
                handler_col = handler_col_name[0] if handler_col_name else None

                all_req_titles = [str(x).strip() for x in spec_reqs[orig_col_name].dropna().tolist() if str(x).strip()]
                req_orig_title = st.selectbox("اختر طلب التعديل للبت فيه:", ["-- اختر الطلب --"] + all_req_titles, key="sb_mod_dec_v74")
                
                if req_orig_title != "-- اختر الطلب --":
                    selected_req_row = spec_reqs[spec_reqs[orig_col_name].astype(str).str.strip() == req_orig_title].iloc[0]
                    curr_status = str(selected_req_row.get(status_col_name, "")).strip()
                    curr_handler = str(selected_req_row.get(handler_col, "")).strip() if handler_col else ""

                    if "مقبول" in curr_status or "مرفوض" in curr_status:
                        st.warning(f"⚠️ تم اتخاذ القرار سابقاً بـ: `{curr_status}` بواسطة: `{curr_handler}`.")
                    else:
                        teacher_name_req = selected_req_row.get("الأستاذ", "")
                        new_title_req = selected_req_row.get("العنوان الجديد", "")

                        col_a, col_r = st.columns(2)
                        with col_a:
                            if st.button("قبول التعديل وتعديل القرار لـ 'مقبول' ✅", key="btn_accept_v74"):
                                if update_mod_request_status_in_sheet(req_orig_title, "تعديل مقبول", f"مسؤول تخصص ({admin_selected_spec})", teacher_name=teacher_name_req, new_title=new_title_req):
                                    st.success("تم تفعيل القرار وتحديث ورقة 'العناوين المسجلة' سحابياً ليصبح الموضوع مقبولاً ومتاحاً للتسجيل!")
                                    st.toast("✅ تم التحديث بنجاح!")
                                    st.rerun()
                        with col_r:
                            if st.button("رفض التعديل ❌", key="btn_reject_v74"):
                                if update_mod_request_status_in_sheet(req_orig_title, "تعديل مرفوض", f"مسؤول تخصص ({admin_selected_spec})"):
                                    st.warning("تم تسجيل الرفض بنجاح!")
                                    st.toast("❌ تم حفظ قرار الرفض!")
                                    st.rerun()

        with adm_tab_stats:
            st.write(f"### 📈 إحصائيات التخصص: {admin_selected_spec}")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            spec_col = [c for c in df_final.columns if "تخصص" in c or "التخصص" in c]
            t_col = [c for c in df_final.columns if "أستاذ" in c or "استاذ" in c]
            
            if not df_final.empty and spec_col:
                df_spec = df_final[df_final[spec_col[0]] == admin_selected_spec]
                
                c_col_st1 = [c for c in df_spec.columns if "طالب" in c and "1" in c]
                c_col_st2 = [c for c in df_spec.columns if "طالب" in c and "2" in c]

                st1_cnt = len(df_spec[c_col_st1[0]].dropna().unique()) if c_col_st1 else 0
                st2_cnt = len([s for s in df_spec[c_col_st2[0]].dropna().unique() if str(s).strip() and str(s).strip().lower() not in ['---', 'nan', 'none', 'null', 'لا يوجد / خيار فردي']]) if c_col_st2 else 0
                
                c_m1, c_m2, c_m3 = st.columns(3)
                with c_m1: st.metric("عدد المذكرات المسجلة", len(df_spec))
                with c_m2: st.metric("عدد الأساتذة المشرفين", df_spec[t_col[0]].nunique() if t_col else 0)
                with c_m3: st.metric("عدد الطلبة المسجلين", st1_cnt + st2_cnt)

        # 7. إصلاح التقارير العامة لضمان عدم وجود حقول فارغة مثل اسم الأستاذ (النقطة 7 والنقطة 12)
        with adm_tab_print:
            st.write(f"### 🖨️ طباعة التقرير العام لتخصص: {admin_selected_spec}")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if st.button("📥 إنشاء وتصدير التقرير العام (PDF)", key="btn_print_spec_pdf_v74"):
                pdf_b = generate_general_report_pdf(df_final, [admin_selected_spec], title_prefix=f"تقرير تخصص {admin_selected_spec}")
                st.download_button("🖨️ تحميل الملف", data=pdf_b, file_name=f"تقرير_{admin_selected_spec}.pdf", mime="application/pdf", key="dl_spec_pdf_v74")

# ==========================================
# 3- فضاء مسؤولَي الشعبتين
# ==========================================
with tab_dept_admin:
    if 'dept_admin_logged_in' not in st.session_state:
        st.session_state.dept_admin_logged_in = False

    d_sub_login, d_tab1, d_tab_mod, d_tab_unreg_titles, d_tab_unreg_students, d_tab2, d_tab3, d_tab4 = st.tabs([
        "🔐 حسابي",
        "📚 المواضيع المسجلة بالقسم",
        "📩 البت في طلبات التعديل",
        "📚 العناوين غير المسجلة",
        "👥 الطلبة غير المسجلين",
        "🖨️ تحميل الاستمارات مع الكودبار",
        "📈 التفاصيل والإحصائيات العامة",
        "🖨️ طباعة التقرير العام"
    ])

    with d_sub_login:
        if not st.session_state.dept_admin_logged_in:
            st.subheader("دخول مسؤولَي الشعبتين")
            dept_pass_input = st.text_input("كلمة مرور مسؤول الشعبة:", type="password", key="dept_p_in_v74")
            if st.button("تسجيل الدخول كمسؤول شعبة 🚀", key="btn_login_dept_admin_v74"):
                if dept_pass_input in ["1234", MASTER_SUPER_PASS]:
                    st.session_state.dept_admin_logged_in = True
                    st.toast("✅ تم تسجيل الدخول كمسؤول شعبة!")
                    st.rerun()
                else:
                    st.error("كلمة المرور غير صحيحة!")
        else:
            st.markdown("""
            <div class="status-msg-success">
                مرحباً بكما، مسؤولي الشعبتين - الإدارة العامة للقسم.
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔴 تسجيل الخروج كمسؤول شعبة", key="btn_logout_dept_admin_v74"):
                st.session_state.dept_admin_logged_in = False
                st.rerun()

    if st.session_state.dept_admin_logged_in:
        # 10. المواضيع المسجلة بالقسم: إلغاء رقم التسجيل من الجدول (النقطة 10)
        with d_tab1:
            st.write("### 📚 المواضيع المسجلة بالقسم (بدون رقم التسجيل)")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final.empty:
                cols_to_drop = [c for c in df_final.columns if "رقم" in c and "تسجيل" in c]
                df_final_display = df_final.drop(columns=cols_to_drop) if cols_to_drop else df_final
                df_final_display.index = range(1, len(df_final_display) + 1)
                st.dataframe(df_final_display, use_container_width=True)

        with d_tab_mod:
            st.write("### 📩 البت في طلبات التعديل (مسؤول الشعبة)")
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            if not df_mod.empty:
                df_mod.index = range(1, len(df_mod) + 1)
                st.dataframe(df_mod, use_container_width=True)

                orig_col_name = [c for c in df_mod.columns if "أصلي" in c or "اصلي" in c or "العنوان" in c][0]
                status_col_name = [c for c in df_mod.columns if "حالة" in c or "الحالة" in c][0]

                req_orig_title_dept = st.selectbox("اختر طلب التعديل للبت فيه كمسؤول شعبة:", ["-- اختر الطلب --"] + df_mod[orig_col_name].dropna().tolist(), key="sb_mod_dec_dept_v74")
                if req_orig_title_dept != "-- اختر الطلب --":
                    selected_req_row = df_mod[df_mod[orig_col_name].astype(str).str.strip() == req_orig_title_dept.strip()].iloc[0]
                    teacher_name_req = selected_req_row.get("الأستاذ", "")
                    new_title_req = selected_req_row.get("العنوان الجديد", "")

                    col_da, col_dr = st.columns(2)
                    with col_da:
                        if st.button("قبول التعديل وتحويل القرار لـ 'مقبول' (مسؤول الشعبة) ✅", key="btn_accept_dept_v74"):
                            if update_mod_request_status_in_sheet(req_orig_title_dept, "تعديل مقبول", "مسؤول الشعبة", teacher_name=teacher_name_req, new_title=new_title_req):
                                st.success("تم تسجيل القبول وتحديث القرار في شيت العناوين ليكون جاهزاً للتسجيل!")
                                st.toast("✅ تم التحديث سحابياً!")
                                st.rerun()
                    with col_dr:
                        if st.button("رفض التعديل (مسؤول الشعبة) ❌", key="btn_reject_dept_v74"):
                            if update_mod_request_status_in_sheet(req_orig_title_dept, "تعديل مرفوض", "مسؤول الشعبة"):
                                st.warning("تم تسجيل الرفض بنجاح!")
                                st.toast("❌ تم حفظ قرار الرفض!")
                                st.rerun()

        with d_tab_unreg_titles:
            st.write("### 📚 قائمة العناوين غير المسجلة")
            df_titles = load_data_from_sheet(SHEET_TITLES)
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            
            registered_titles = [extract_title_from_row(r) for _, r in df_final.iterrows()] if not df_final.empty else []

            unregistered_titles_list = []
            if not df_titles.empty:
                for i in range(0, len(df_titles.columns) - 2, 3):
                    t_col = df_titles.columns[i]
                    tch_col = df_titles.columns[i+1]
                    
                    col_lower = str(t_col).lower()
                    spec_detected = "عام"
                    if "لسانيات" in col_lower: spec_detected = "لسانيات عامة"
                    elif "أدب" in col_lower: spec_detected = "أدب عربي حديث ومعاصر"
                    elif "نقد" in col_lower: spec_detected = "نقد حديث معاصر"
                    elif "شعبي" in col_lower: spec_detected = "أدب شعبي"

                    for _, r in df_titles.iterrows():
                        t_val = str(r[t_col]).strip()
                        tch_val = str(r[tch_col]).strip()
                        if t_val and t_val.lower() != 'nan' and t_val not in registered_titles:
                            unregistered_titles_list.append({
                                "التخصص": spec_detected,
                                "العنوان": t_val, 
                                "الأستاذ المشرف": tch_val
                            })

            df_unreg_disp = pd.DataFrame(unregistered_titles_list)
            if not df_unreg_disp.empty:
                selected_spec_filter = st.selectbox("فرز العناوين غير المسجلة حسب التخصص:", ["الكل"] + SPECIALTIES, key="sb_unreg_titles_spec_v74")
                if selected_spec_filter != "الكل":
                    df_unreg_disp = df_unreg_disp[df_unreg_disp["التخصص"] == selected_spec_filter]

                df_unreg_disp.index = range(1, len(df_unreg_disp) + 1)
                st.dataframe(df_unreg_disp, use_container_width=True)

                if st.button("🖨️ طباعة تقرير العناوين غير المسجلة (PDF)", key="btn_print_unregistered_titles_pdf_v74"):
                    pdf_unreg_bytes = generate_general_report_pdf(df_unreg_disp, [selected_spec_filter], title_prefix="قائمة العناوين غير المسجلة بالقسم")
                    st.download_button("📥 تحميل PDF", data=pdf_unreg_bytes, file_name="العناوين_غير_المسجلة.pdf", mime="application/pdf", key="dl_unreg_titles_pdf_v74")
            else:
                st.info("لا توجد عناوين غير مسجلة حالياً.")

        with d_tab_unreg_students:
            st.write("### 👥 قائمة الطلبة غير المسجلين بالقسم")
            df_students = load_data_from_sheet(SHEET_STUDENTS)
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)

            c_col_st1 = [c for c in df_final.columns if "طالب" in c and "1" in c]
            c_col_st2 = [c for c in df_final.columns if "طالب" in c and "2" in c]
            reg_st1 = df_final[c_col_st1[0]].dropna().tolist() if c_col_st1 else []
            reg_st2 = df_final[c_col_st2[0]].dropna().tolist() if c_col_st2 else []
            all_reg_students = set([str(s).split(" (")[0].strip() for s in reg_st1 + reg_st2 if str(s).strip()])

            unregistered_students = []
            if not df_students.empty:
                for spec_k in SPECIALTIES:
                    st_objs = get_students_by_specialty(df_students, spec_k)
                    for st_o in st_objs:
                        if st_o["name_ar"] not in all_reg_students:
                            unregistered_students.append({
                                "الاسم واللقب": st_o["name_ar"],
                                "التخصص": spec_k
                            })

            df_unreg_st = pd.DataFrame(unregistered_students)
            if not df_unreg_st.empty:
                filter_specs = st.multiselect("فرز حسب التخصص:", options=SPECIALTIES, default=SPECIALTIES, key="ms_filter_unreg_v74")
                if filter_specs:
                    df_unreg_st = df_unreg_st[df_unreg_st["التخصص"].isin(filter_specs)]

                df_unreg_st = df_unreg_st.sort_values(by="الاسم واللقب", ascending=True)
                df_unreg_st.index = range(1, len(df_unreg_st) + 1)
                st.dataframe(df_unreg_st, use_container_width=True)

                if st.button("📥 تصدير قائمة الطلبة غير المسجلين (PDF بدون تكرار الترويسة)", key="btn_exp_unreg_pdf_v74"):
                    pdf_unreg_bytes = generate_general_report_pdf(df_unreg_st, filter_specs, title_prefix="قائمة الطلبة غير المسجلين بالقسم")
                    st.download_button("🖨️ تحميل PDF", data=pdf_unreg_bytes, file_name="الطلبة_غير_المسجلين.pdf", mime="application/pdf", key="dl_unreg_pdf_v74")

        with d_tab2:
            st.write("### 🖨️ استخراج وتحميل استمارات المذكرات (فردياً ودُفعة واحدة)")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final.empty:
                t_col_name = [c for c in df_final.columns if "أستاذ" in c or "استاذ" in c][0]
                
                df_final['أستاذ_نظيف'] = df_final[t_col_name].astype(str).str.strip()
                df_final['رقم_مذكرة_الأستاذ'] = df_final.groupby('أستاذ_نظيف').cumcount() + 1
                df_final['اسم_الملف'] = df_final['أستاذ_نظيف'] + df_final['رقم_مذكرة_الأستاذ'].astype(str)

                col_single, col_bulk = st.columns(2)
                
                with col_single:
                    st.markdown("#### 📄 تحميل استمارة واحدة")
                    file_options = df_final['اسم_الملف'].dropna().tolist()
                    selected_file_label = st.selectbox("اختر الاستمارة المسمى باسم الأستاذ ورقمها:", ["-- اختر الاستمارة --"] + file_options, key="sb_dept_single_file_v74")
                    
                    if selected_file_label != "-- اختر الاستمارة --":
                        form_row = df_final[df_final['اسم_الملف'] == selected_file_label].iloc[0]
                        
                        c_col_st1 = [c for c in form_row.index if "طالب" in c and "1" in c]
                        c_col_r1 = [c for c in form_row.index if "تسجيل" in c and "1" in c]
                        c_col_st2 = [c for c in form_row.index if "طالب" in c and "2" in c]
                        c_col_r2 = [c for c in form_row.index if "تسجيل" in c and "2" in c]

                        raw_st1 = form_row.get(c_col_st1[0], '') if c_col_st1 else form_row.get('اسم الطالب 1', '')
                        r1_v = form_row.get(c_col_r1[0], '') if c_col_r1 else form_row.get('رقم تسجيل 1', '')
                        raw_st2 = form_row.get(c_col_st2[0], '') if c_col_st2 else form_row.get('اسم الطالب 2', '')
                        r2_v = form_row.get(c_col_r2[0], '') if c_col_r2 else form_row.get('رقم تسجيل 2', '')

                        st1_ar = raw_st1.split(" (")[0] if " (" in raw_st1 else raw_st1
                        st1_fr = raw_st1.split(" (")[1].replace(")", "") if " (" in raw_st1 else ""

                        st2_ar = raw_st2.split(" (")[0] if " (" in raw_st2 else raw_st2
                        st2_fr = raw_st2.split(" (")[1].replace(")", "") if " (" in raw_st2 else ""

                        t_name_val = extract_teacher_from_row(form_row)
                        spec_val = form_row.get("تخصص الطالب", "")
                        title_val = extract_title_from_row(form_row)
                        form_code_val = form_row.get("رمز الاستمارة", generate_random_code())

                        st2_qr_txt = f" / St2: {st2_ar}" if st2_ar else ""
                        qr_code_val = f"REF:{form_code_val} | TCH:{t_name_val} | SPEC:{spec_val} | St1:{st1_ar}{st2_qr_txt} | TITLE:{title_val}"

                        dept_pdf_bytes = generate_pdf_document(
                            form_code_val,
                            t_name_val, spec_val,
                            st1_ar, st1_fr, r1_v,
                            st2_ar, st2_fr, r2_v,
                            title_val,
                            qr_code_str=qr_code_val
                        )

                        st.download_button(
                            label=f"🖨️ تحميل استمارة ({selected_file_label}.pdf)",
                            data=dept_pdf_bytes,
                            file_name=f"{selected_file_label}.pdf",
                            mime="application/pdf",
                            key="btn_dept_dl_single_v74"
                        )

                with col_bulk:
                    st.markdown("#### 📦 تحميل الاستمارات دفعة واحدة (ZIP)")
                    bulk_choice = st.radio("خيارات التجميع للتحميل الجماعي:", ["جميع الاستمارات بالقسم", "حسب تخصص معين"], horizontal=True, key="rd_bulk_type_v74")
                    
                    target_bulk_df = df_final.copy()
                    if bulk_choice == "حسب تخصص معين":
                        selected_bulk_spec = st.selectbox("اختر التخصص للتنزيل الجماعي:", SPECIALTIES, key="sb_bulk_spec_v74")
                        target_bulk_df = target_bulk_df[target_bulk_df["تخصص الطالب"] == selected_bulk_spec]

                    if st.button("📦 إنتاج ملف الاستمارات الجماعي (ZIP)", key="btn_gen_bulk_zip_v74"):
                        if not target_bulk_df.empty:
                            zip_buffer = BytesIO()
                            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                                for _, form_row in target_bulk_df.iterrows():
                                    c_col_st1 = [c for c in form_row.index if "طالب" in c and "1" in c]
                                    c_col_r1 = [c for c in form_row.index if "تسجيل" in c and "1" in c]
                                    c_col_st2 = [c for c in form_row.index if "طالب" in c and "2" in c]
                                    c_col_r2 = [c for c in form_row.index if "تسجيل" in c and "2" in c]

                                    raw_st1 = form_row.get(c_col_st1[0], '') if c_col_st1 else form_row.get('اسم الطالب 1', '')
                                    r1_v = form_row.get(c_col_r1[0], '') if c_col_r1 else form_row.get('رقم تسجيل 1', '')
                                    raw_st2 = form_row.get(c_col_st2[0], '') if c_col_st2 else form_row.get('اسم الطالب 2', '')
                                    r2_v = form_row.get(c_col_r2[0], '') if c_col_r2 else form_row.get('رقم تسجيل 2', '')

                                    st1_ar = raw_st1.split(" (")[0] if " (" in raw_st1 else raw_st1
                                    st1_fr = raw_st1.split(" (")[1].replace(")", "") if " (" in raw_st1 else ""

                                    st2_ar = raw_st2.split(" (")[0] if " (" in raw_st2 else raw_st2
                                    st2_fr = raw_st2.split(" (")[1].replace(")", "") if " (" in raw_st2 else ""

                                    t_name_val = extract_teacher_from_row(form_row)
                                    spec_val = form_row.get("تخصص الطالب", "")
                                    title_val = extract_title_from_row(form_row)
                                    file_label = form_row.get("اسم_الملف", f"استمارة_{t_name_val}")
                                    form_code_val = form_row.get("رمز الاستمارة", generate_random_code())

                                    st2_qr_txt = f" / St2: {st2_ar}" if st2_ar else ""
                                    qr_code_val = f"REF:{form_code_val} | TCH:{t_name_val} | SPEC:{spec_val} | St1:{st1_ar}{st2_qr_txt} | TITLE:{title_val}"

                                    pdf_data = generate_pdf_document(
                                        form_code_val,
                                        t_name_val, spec_val,
                                        st1_ar, st1_fr, r1_v,
                                        st2_ar, st2_fr, r2_v,
                                        title_val,
                                        qr_code_str=qr_code_val
                                    )
                                    zip_file.writestr(f"{file_label}.pdf", pdf_data)

                            zip_buffer.seek(0)
                            st.toast("📦 تم تجميع واستخراج جميع الاستمارات بنجاح!")
                            st.download_button(
                                label="📥 اضغط هنا لتحميل أرشيف الاستمارات (ZIP)",
                                data=zip_buffer,
                                file_name="جميع_الاستمارات_المعتمدة.zip",
                                mime="application/zip",
                                key="btn_dl_zip_final_v74"
                            )
                        else:
                            st.warning("لا توجد استمارات مطابقة للخيار المحدد.")

        with d_tab3:
            st.write("### 📈 التفاصيل والإحصائيات العامة بالقسم")
            
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            df_teachers = load_data_from_sheet(SHEET_TEACHERS)
            
            spec_col = [c for c in df_final.columns if "تخصص" in c or "التخصص" in c]
            t_col = [c for c in df_final.columns if "أستاذ" in c or "استاذ" in c]

            if not df_final.empty:
                c_col_st1 = [c for c in df_final.columns if "طالب" in c and "1" in c]
                c_col_st2 = [c for c in df_final.columns if "طالب" in c and "2" in c]

                st1_cnt = len(df_final[c_col_st1[0]].dropna().unique()) if c_col_st1 else 0
                st2_cnt = len([s for s in df_final[c_col_st2[0]].dropna().unique() if str(s).strip() and str(s).strip().lower() not in ['---', 'nan', 'none', 'null', 'لا يوجد / خيار فردي']]) if c_col_st2 else 0

                c_m1, c_m2, c_m3 = st.columns(3)
                with c_m1: st.metric("إجمالي المذكرات المسجلة", len(df_final))
                with c_m2: st.metric("إجمالي الأساتذة المشرفين", df_final[t_col[0]].nunique() if t_col else 0)
                with c_m3: st.metric("إجمالي الطلبة المسجلين", st1_cnt + st2_cnt)

            st.markdown("---")
            st.write("#### 📋 جدول جميع أساتذة القسم مع عدد المذكرات المسجلة لكل أستاذ:")
            
            t_name_col = [c for c in df_teachers.columns if "الاسم" in c or "اللقب" in c][0] if not df_teachers.empty else "اسم الأستاذ"
            teachers_all_list = df_teachers[t_name_col].dropna().unique().tolist() if not df_teachers.empty else []

            teacher_memos_count = []
            for tch in teachers_all_list:
                cnt = 0
                if not df_final.empty and t_col:
                    cnt = len(df_final[df_final[t_col[0]].astype(str).str.strip() == str(tch).strip()])
                teacher_memos_count.append({"اسم الأستاذ": tch, "عدد المذكرات المسجلة": cnt})

            df_tch_stats = pd.DataFrame(teacher_memos_count)
            if not df_tch_stats.empty:
                df_tch_stats.index = range(1, len(df_tch_stats) + 1)
                st.dataframe(df_tch_stats, use_container_width=True)

                pdf_tch_stats_bytes = generate_teachers_stats_pdf(df_tch_stats)
                st.download_button(
                    label="🖨️ طباعة تقرير إحصائيات الأساتذة الشامل مع الترويسة (PDF)",
                    data=pdf_tch_stats_bytes,
                    file_name="تقرير_إحصائيات_أساتذة_القسم.pdf",
                    mime="application/pdf",
                    key="btn_dl_tch_stats_pdf_v74"
                )

        with d_tab4:
            selected_specs_report = st.multiselect("حدد التخصصات المطلوب طباعتها:", options=SPECIALTIES, default=SPECIALTIES, key="ms_dept_v74")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if st.button("📥 تصدير التقرير العام (PDF)", key="btn_print_dept_pdf_v74"):
                pdf_b = generate_general_report_pdf(df_final, selected_specs_report)
                st.download_button("🖨️ تحميل الملف", data=pdf_b, file_name="التقرير_العام.pdf", mime="application/pdf", key="dl_dept_pdf_v74")

# ==========================================
# 4- لسان البرمجة والتطوير
# ==========================================
with tab_dev_info:
    st.subheader("💻 البرمجة والتطوير")
    
    st.markdown("""
    <div class="dev-box" style="background-color: #ffffff; padding: 25px; border-radius: 16px; border: 2px solid #1e3a8a; text-align: center;">
        <h3 style="color:#1e3a8a; margin-top:0; font-size: 1.4rem;">حول المنصة السحابية:</h3>
        <p style="font-size: 1.15rem; line-height: 2.2; margin: 0; color: #1e293b;">
            هذه المنصة مصممة لأساتذة قسم اللغة والأدب العربي<br>
            لإدارة مذكرات التخرج بدءاً بااختيار العناوين وإيداع الاستمارات<br>
            وانتهاءً بمناقشة المذكرة وإصدار محضر المناقشة.<br><br>
            <b>تطوير:</b> أ.د/ عبد الكريم خليل – قسم اللغة والأدب العربي<br>
            كلية الآداب واللغات – جامعة الوادي<br>
            <b>لغات البرمجة المستعملة:</b> Python – Java – PHP<br>
            <b>السنة الجامعية:</b> 2026/2027
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 🔐 حيز إدارة النظام")
    
    sys_pass_input = st.text_input("أدخل كلمة المرور لدخول إدارة النظام:", type="password", key="inp_sys_pass_v74")
    
    if st.button("الدخول إلى إدارة النظام 🚀", key="btn_login_sys_admin_v74"):
        if sys_pass_input == SYS_ADMIN_PASS:
            st.toast("✅ تم التحقق من كلمة المرور بنجاح! جاري تحديث الصفحة...")
            st.success("تم الدخول بنجاح! جاري التحديث...")
            st.rerun()
        else:
            st.markdown("""
            <div style="background-color: #fef2f2; border: 2px solid #ef4444; color: #b91c1c; padding: 12px; border-radius: 8px; font-weight: bold; margin: 10px auto; max-width: 400px; text-align: center;">
                🔴 ليس لديك صلاحية الدخول لإدارة النظام
            </div>
            """, unsafe_allow_html=True)
