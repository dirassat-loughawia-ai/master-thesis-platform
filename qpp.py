import streamlit as st
import pandas as pd
import os
import requests
import urllib.parse
import base64
from datetime import datetime
from io import BytesIO
from streamlit_gsheets import GSheetsConnection

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from PIL import Image

import arabic_reshaper
from bidi.algorithm import get_display

# --- 1. إعدادات الصفحة الأساسية ---
st.set_page_config(
    page_title="منصة إدارة مذكرات الماستر - جامعة الوادي",
    page_icon="🎓",
    layout="wide"
)

SPREADSHEET_ID = "1GvS4BE2WL18peY97GAfjRJz9LdZTCZYWlV7P-QsJpOQ"
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxnzaSNAz4LQ7jhf6-qtdZsWS_1srSZyt3xasvJiHxdYOeTbp99rS-BO_4jiam7Q1eDQA/exec"

SHEET_TEACHERS = "قائمة الأساتذة"
SHEET_ADMINS = "كلمات مرور المسؤولين"
SHEET_STUDENTS = "قوائم الطلبة"
SHEET_TITLES = "العناوين المسجلة"
SHEET_MOD_REQUESTS = "طلبات التعديل"
SHEET_FINAL_REGISTRATIONS = "التسجيلات النهائية"

SPECIALTIES = ["لسانيات عامة", "أدب عربي حديث ومعاصر", "نقد حديث معاصر", "أدب شعبي"]
MASTER_SUPER_PASS = "0000"

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
        response = requests.post(WEB_APP_URL, json=payload, timeout=15)
        st.cache_data.clear()
        if response.status_code == 200:
            return response.json() if response.headers.get('content-type', '').startswith('application/json') else {"status": "success", "message": response.text}
        return None
    except Exception as e:
        st.error(f"خطأ في الاتصال السحابي: {e}")
        return None

def save_data_to_sheet(row_data_dict, worksheet_name):
    if worksheet_name == SHEET_FINAL_REGISTRATIONS:
        ordered_keys = ["رقم الاستمارة", "اسم الأستاذ", "تخصص الطالب", "اسم الطالب 1", "رقم تسجيل 1", "اسم الطالب 2", "رقم تسجيل 2", "عنوان المذكرة", "تاريخ التسجيل", "رابط الاستمارة"]
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

def upload_form_file_to_sheet(form_num, teacher_name, pdf_bytes):
    """رفع الملف إلى Google Drive وحفظ الرابط الحقيقي في الشيت"""
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    payload = {
        "action": "upload_pdf_get_link",
        "sheet_name": SHEET_FINAL_REGISTRATIONS,
        "form_num": str(form_num).strip(),
        "file_name": f"استمارة_{form_num}_{teacher_name}.pdf",
        "pdf_data": base64_pdf
    }
    return send_payload_to_script(payload)

def delete_registration_from_sheet(form_num):
    payload = {
        "action": "delete_row",
        "sheet_name": SHEET_FINAL_REGISTRATIONS,
        "key_val": str(form_num).strip()
    }
    res = send_payload_to_script(payload)
    return res is not None

def update_registration_in_sheet(form_num, row_data_dict):
    ordered_keys = ["رقم الاستمارة", "اسم الأستاذ", "تخصص الطالب", "اسم الطالب 1", "رقم تسجيل 1", "اسم الطالب 2", "رقم تسجيل 2", "عنوان المذكرة", "تاريخ التسجيل", "رابط الاستمارة"]
    row_values = [str(row_data_dict.get(k, "")).strip() for k in ordered_keys]
    payload = {
        "action": "update_row",
        "sheet_name": SHEET_FINAL_REGISTRATIONS,
        "key_val": str(form_num).strip(),
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
    if success and status == "تعديل مقبول" and teacher_name and new_title:
        update_title_in_sheets_after_approval(teacher_name, orig_title, new_title)
    return success

# --- 4. إعداد الخط العربي والأيقونات ---
def setup_arabic_font():
    local_fonts = ["Amiri-Regular.ttf", "amiri.ttf", "Simplified Arabic.ttf", "arial.ttf"]
    for font_p in local_fonts:
        if os.path.exists(font_p):
            try:
                pdfmetrics.registerFont(TTFont('ArabicFont', font_p))
                pdfmetrics.registerFont(TTFont('ArabicFont-Bold', font_p))
                return 'ArabicFont', 'ArabicFont-Bold'
            except Exception:
                pass

    try:
        url = "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            with open("Amiri-Regular.ttf", "wb") as f:
                f.write(r.content)
            pdfmetrics.registerFont(TTFont('ArabicFont', "Amiri-Regular.ttf"))
            pdfmetrics.registerFont(TTFont('ArabicFont-Bold', "Amiri-Regular.ttf"))
            return 'ArabicFont', 'ArabicFont-Bold'
    except Exception:
        pass

    return 'Helvetica', 'Helvetica-Bold'

ARABIC_FONT, ARABIC_FONT_BOLD = setup_arabic_font()

def reshape_arabic(text):
    if text is None or pd.isna(text):
        return ""
    txt_str = str(text).strip()
    if txt_str == "" or txt_str.lower() in ["nan", "none"]:
        return ""
    reshaped_text = arabic_reshaper.reshape(txt_str)
    return get_display(reshaped_text)

def draw_icon_if_exists(can, icon_name, x, y, width=50, height=50):
    if os.path.exists(icon_name):
        try:
            can.drawImage(icon_name, x, y, width=width, height=height, mask='auto')
        except Exception:
            pass

# --- 5. توليد PDF مع معالجة دقيقة لأسماء الطلبة وأرقام التسجيل ---
def generate_pdf_document(form_num, teacher_name, specialty, st1_name, st1_reg, st2_name, st2_reg, title, signature_file=None):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    page_width, page_height = letter
    center_x = page_width / 2.0

    can.setLineWidth(2)
    can.rect(20, 20, page_width - 40, page_height - 40)

    draw_icon_if_exists(can, "icon1.png", page_width - 80, page_height - 75, 50, 50)
    draw_icon_if_exists(can, "icon2.png", 30, page_height - 75, 50, 50)

    can.setFont(ARABIC_FONT_BOLD, 12)
    can.drawCentredString(center_x, page_height - 40, reshape_arabic("الجمهورية الجزائرية الديمقراطية الشعبية"))
    can.drawCentredString(center_x, page_height - 55, reshape_arabic("وزارة التعليم العالي والبحث العلمي"))
    can.drawCentredString(center_x, page_height - 70, reshape_arabic("جامعة الوادي - كلية الآداب واللغات"))

    can.setFont(ARABIC_FONT_BOLD, 10)
    can.drawCentredString(center_x, page_height - 85, reshape_arabic("قسم اللغة والأدب العربي"))
    
    can.setFont(ARABIC_FONT_BOLD, 13)
    can.drawCentredString(center_x, page_height - 102, reshape_arabic("السنة الجامعية: 2026-2027"))

    can.setLineWidth(1)
    can.line(30, page_height - 112, page_width - 30, page_height - 112)

    can.setFont(ARABIC_FONT_BOLD, 22)
    can.drawCentredString(center_x, page_height - 145, reshape_arabic("استمارة تسجيل مذكرة ماستر"))
    
    can.setFont(ARABIC_FONT_BOLD, 14)
    can.drawCentredString(center_x, page_height - 175, reshape_arabic(f"رقم الاستمارة: {form_num}"))
    can.setFont(ARABIC_FONT_BOLD, 13)
    can.drawCentredString(center_x, page_height - 198, reshape_arabic(f"التخصص: {specialty}"))

    can.setFont(ARABIC_FONT_BOLD, 14)
    can.drawCentredString(center_x, page_height - 235, reshape_arabic(f"الأستاذ المشرف: {teacher_name}"))
    can.drawCentredString(center_x, page_height - 265, reshape_arabic("عنوان المذكرة:"))
    
    rect_y = page_height - 345
    can.setLineWidth(1.5)
    can.rect(40, rect_y, page_width - 80, 65)
    
    can.setFont(ARABIC_FONT_BOLD, 13)
    can.drawCentredString(center_x, rect_y + 26, reshape_arabic(f"« {title} »"))

    # طباعة أسماء وأرقام تسجيل الطلبة بوضوح صريح
    y_st = page_height - 390
    can.setFont(ARABIC_FONT_BOLD, 12)
    
    str_st1 = f"الطالب الأول: {st1_name}" + (f" (رقم التسجيل: {st1_reg})" if st1_reg else "")
    can.drawRightString(page_width - 50, y_st, reshape_arabic(str_st1))
    
    if st2_name and str(st2_name).strip() not in ["", "---", "nan", "لا يوجد / خيار فردي"]:
        str_st2 = f"الطالب الثاني: {st2_name}" + (f" (رقم التسجيل: {st2_reg})" if st2_reg else "")
        can.drawRightString(page_width - 50, y_st - 30, reshape_arabic(str_st2))

    y_sig = y_st - 85
    can.drawRightString(page_width - 60, y_sig, reshape_arabic("إمضاء المشرف:"))
    can.drawString(60, y_sig, reshape_arabic("مسؤول الشعبة:"))

    if signature_file is not None:
        try:
            sig_img = Image.open(signature_file)
            sig_bytes = BytesIO()
            sig_img.save(sig_bytes, format='PNG')
            sig_bytes.seek(0)
            can.drawImage(sig_bytes, page_width - 160, y_sig - 45, width=100, height=45, mask='auto')
        except Exception:
            pass

    can.setFont(ARABIC_FONT_BOLD, 12)
    can.drawCentredString(center_x, 35, reshape_arabic("السنة الجامعية: 2026-2027"))

    can.save()
    packet.seek(0)
    return packet.getvalue()

# --- 6. الواجهة ---
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

st.markdown("""
<div class="main-header">
    <h1 style="margin:0; font-size:2.2rem;">🎓 منصة إدارة مذكرات الماستر (السحابية)</h1>
    <p style="margin:5px 0 0 0; font-size:1.1rem; opacity:0.9;">قسم اللغة والأدب العربي - كلية الآداب واللغات - جامعة الوادي</p>
</div>
""", unsafe_allow_html=True)

tab_teacher, tab_spec_admin, tab_dept_admin = st.tabs([
    "👨‍🏫 فضاء الأستاذ", 
    "👨‍💼 فضاء مسؤولي التخصصات", 
    "🏛️ فضاء مسؤولَي الشعبتين"
])

# ==========================================
# 1- فضاء الأستاذ
# ==========================================
with tab_teacher:
    if 'teacher_logged_in' not in st.session_state:
        st.session_state.teacher_logged_in = False
        st.session_state.current_teacher = ""

    t_sub_tab1, t_sub_tab2, t_sub_tab_registered = st.tabs([
        "🔐 الدخول إلى حسابي", 
        "📝 تسجيل مذكرة ماستر", 
        "📚 العناوين المسجلة والأرشفة"
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
            if st.button("🔴 تسجيل الخروج", key="btn_logout_teacher_v38"):
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
                selected_teacher = st.selectbox("اختر اسم الأستاذ:", ["-- اختر اسمك --"] + teacher_list, key="sb_t_login_v38")
                input_pass = st.text_input("كلمة المرور:", type="password", key="inp_t_pass_v38")
                
                if st.button("الدخول إلى حسابي 🚀", key="btn_t_login_v38"):
                    if selected_teacher != "-- اختر اسمك --":
                        real_pass = df_teachers[df_teachers[name_col] == selected_teacher][pass_col].values if pass_col else []
                        if str(input_pass) == MASTER_SUPER_PASS or (len(real_pass) > 0 and str(real_pass[0]) == str(input_pass)):
                            st.session_state.teacher_logged_in = True
                            st.session_state.current_teacher = selected_teacher.strip()
                            st.session_state.saved_successfully = False
                            st.rerun()
                        else:
                            st.error("❌ كلمة المرور غير صحيحة!")

    with t_sub_tab2:
        if not st.session_state.teacher_logged_in:
            st.info("⚠️ يرجى تسجيل الدخول أولاً من لسان 'الدخول إلى حسابي'.")
        else:
            current_teacher_name = st.session_state.current_teacher.strip()
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            
            t_col_name = [c for c in df_final.columns if "أستاذ" in c or "استاذ" in c]
            teacher_col = t_col_name[0] if t_col_name else "اسم الأستاذ"

            teacher_registrations_count = 0
            if not df_final.empty and teacher_col in df_final.columns:
                teacher_registrations_count = len(df_final[df_final[teacher_col].astype(str).str.strip() == current_teacher_name])

            if teacher_registrations_count >= 3:
                st.error(f"❌ الأستاذ الفاضل {current_teacher_name}، لقد تجاوزت الحد الأقصى المسموح به لتسجيل المذكرات (03 مذكرات).")
            else:
                if st.session_state.get('saved_successfully', False):
                    st.success("أستاذنا الكريم، لقد تم -بنجاح- تسجيل مذكرتكم في قاعدة البيانات.")
                    
                    st.markdown("---")
                    st.write("### ✍️ إرفاق التوقيع الشخصي على الاستمارة")
                    uploaded_sig = st.file_uploader("قم برفع صورة إمضاء الأستاذ المشرف (اختياري):", type=["png", "jpg", "jpeg"], key="up_sig_new_v38")
                    
                    pdf_data = generate_pdf_document(
                        st.session_state.last_form_num, current_teacher_name, 
                        st.session_state.last_spec, 
                        st.session_state.last_st1_n, st.session_state.last_st1_r,
                        st.session_state.last_st2_n, st.session_state.last_st2_r,
                        st.session_state.last_title,
                        signature_file=uploaded_sig
                    )
                    
                    st.download_button("🖨️ الاستمارة جاهزة للطباعة والتحميل (PDF)", data=pdf_data, file_name=f"استمارة_{st.session_state.last_form_num}.pdf", mime="application/pdf", key="dl_pdf_v38")
                    
                    if st.button("📝 تسجيل مذكرة أخرى", key="reset_reg_v38"):
                        st.session_state.saved_successfully = False
                        st.rerun()
                else:
                    st.subheader(f"مذكرات الأستاذ: {current_teacher_name} (المسجلة حالياً: {teacher_registrations_count} من 3)")
                    selected_spec = st.selectbox("اختر التخصص:", SPECIALTIES, key="sb_spec_v38")
                    df_students = load_data_from_sheet(SHEET_STUDENTS)

                    students_options = []
                    spec_col_map = {
                        "لسانيات عامة": ("تخصص لسانيات عامة", "رقم تسجيل لسانيات عامة"),
                        "أدب عربي حديث ومعاصر": ("تخصص أدب حديث ومعاصر", "رقم تسجيل أدب حديث ومعاصر"),
                        "نقد حديث معاصر": ("تخصص نقد حديث ومعاصر", "رقم تسجيل نقد حديث ومعاصر"),
                        "أدب شعبي": ("تخصص أدب شعبي", "رقم تسجيل أدب شعبي")
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
                    with col_s1: st1 = st.selectbox("اختر الطالب الأول (إجباري):", ["-- اختر الطالب --"] + students_options, key="st1_v38")
                    st2_opts = [s for s in students_options if s != st1]
                    with col_s2: st2 = st.selectbox("اختر الطالب الثاني (اختياري):", ["-- لا يوجد / خيار فردي --"] + st2_opts, key="st2_v38")

                    df_titles = load_data_from_sheet(SHEET_TITLES)
                    available_titles = []
                    if not df_titles.empty:
                        for i in range(0, len(df_titles.columns) - 1, 2):
                            tit_c = df_titles.columns[i]
                            tch_c = df_titles.columns[i+1]
                            matched = df_titles[df_titles[tch_c].astype(str).str.strip() == current_teacher_name]
                            if not matched.empty:
                                available_titles.extend(matched[tit_c].dropna().unique().tolist())

                    selected_title_dropdown = st.selectbox("اختر عنوان المذكرة الخاصة بك:", ["-- اختر العنوان --"] + available_titles, key="sb_title_v38")

                    if st.button("💾 حفظ في قاعدة البيانات", key="btn_save_v38"):
                        if st1 != "-- اختر الطالب --" and selected_title_dropdown != "-- اختر العنوان --":
                            next_form_num = len(df_final) + 1 if not df_final.empty else 1
                            
                            st1_n = st1.split(" - ")[0].strip()
                            st1_r = st1.split(" - ")[1].strip() if " - " in st1 else ""
                            st2_n = st2.split(" - ")[0].strip() if st2 != "-- لا يوجد / خيار فردي --" else ""
                            st2_r = st2.split(" - ")[1].strip() if " - " in st2 and st2 != "-- لا يوجد / خيار فردي --" else ""

                            summary_data = {
                                "رقم الاستمارة": str(next_form_num),
                                "اسم الأستاذ": current_teacher_name,
                                "تخصص الطالب": selected_spec,
                                "اسم الطالب 1": st1_n,
                                "رقم تسجيل 1": st1_r,
                                "اسم الطالب 2": st2_n,
                                "رقم تسجيل 2": st2_r,
                                "عنوان المذكرة": selected_title_dropdown.strip(),
                                "تاريخ التسجيل": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "رابط الاستمارة": "غير مرفوع"
                            }
                            if save_data_to_sheet(summary_data, SHEET_FINAL_REGISTRATIONS):
                                st.session_state.saved_successfully = True
                                st.session_state.last_form_num = next_form_num
                                st.session_state.last_spec = selected_spec
                                st.session_state.last_st1_n = st1_n
                                st.session_state.last_st1_r = st1_r
                                st.session_state.last_st2_n = st2_n
                                st.session_state.last_st2_r = st2_r
                                st.session_state.last_title = selected_title_dropdown
                                st.rerun()

    with t_sub_tab_registered:
        if st.session_state.teacher_logged_in:
            teacher_curr = str(st.session_state.current_teacher).strip()
            st.subheader(f"📚 العناوين المسجلة باسم الأستاذ: {teacher_curr}")
            if st.button("🔄 تحديث إظهار العناوين", key="btn_ref_reg_v38"):
                st.cache_data.clear()
                st.rerun()

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
                        st.markdown("### 🖨️ طباعة الاستمارة وأرشفتها سحابياً")
                        titles_list_for_print = my_reg["عنوان المذكرة"].dropna().tolist() if "عنوان المذكرة" in my_reg.columns else []
                        selected_title_to_print = st.selectbox("اختر عنوان المذكرة لطباعتها ورؤية رابطها:", ["-- اختر العنوان --"] + titles_list_for_print, key="sb_print_reg_v38")
                        
                        if selected_title_to_print != "-- اختر العنوان --":
                            uploaded_sig_reg = st.file_uploader("قم برفع صورة إمضاء الأستاذ المشرف:", type=["png", "jpg", "jpeg"], key="up_sig_reg_v38")
                            p_row = my_reg[my_reg["عنوان المذكرة"] == selected_title_to_print].iloc[0]
                            
                            pdf_bytes_row = generate_pdf_document(
                                p_row.get("رقم الاستمارة", "1"),
                                teacher_curr,
                                p_row.get("تخصص الطالب", ""),
                                p_row.get("اسم الطالب 1", ""),
                                p_row.get("رقم تسجيل 1", ""),
                                p_row.get("اسم الطالب 2", ""),
                                p_row.get("رقم تسجيل 2", ""),
                                p_row.get("عنوان المذكرة", ""),
                                signature_file=uploaded_sig_reg
                            )

                            col_dl, col_up = st.columns(2)
                            with col_dl:
                                st.download_button(
                                    label=f"🖨️ تحميل استمارة «{selected_title_to_print[:20]}...»",
                                    data=pdf_bytes_row,
                                    file_name=f"استمارة_{p_row.get('رقم الاستمارة', '1')}_{teacher_curr}.pdf",
                                    mime="application/pdf",
                                    key="btn_dl_registered_pdf_v38"
                                )
                            with col_up:
                                if st.button("☁️ أرشفة الملف على Google Drive وإظهار الرابط", key="btn_upload_to_gsheet_v38"):
                                    res = upload_form_file_to_sheet(p_row.get("رقم الاستمارة", "1"), teacher_curr, pdf_bytes_row)
                                    if res and res.get("file_url"):
                                        st.success("✅ تم حفظ الاستمارة بنجاح على Google Drive!")
                                        st.markdown(f"🔗 **رابط الاستمارة المباشر:** [{res.get('file_url')}]({res.get('file_url')})")
                                    else:
                                        st.error("تعذر رفع الملف، يرجى مراجعة إعدادات Google Drive في الشيت.")
                    else:
                        st.info("لا توجد مذكرات مسجلة باسمك بعد.")
            else:
                st.info("لا توجد مذكرات مسجلة بالقاعدة بعد.")
