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
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbwfViyMv6ZM-7k_OOL9LopddSlYFVD6rVPBEPVyHRg45hW_T-IMIPfhl1WcuDgnjtlQVg/exec"

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
        response = requests.post(WEB_APP_URL, json=payload, timeout=10)
        st.cache_data.clear()
        return response.status_code == 200
    except Exception as e:
        st.error(f"خطأ في الاتصال السحابي: {e}")
        return False

def save_data_to_sheet(row_data_dict, worksheet_name):
    if worksheet_name == SHEET_FINAL_REGISTRATIONS:
        ordered_keys = ["رقم الاستمارة", "اسم الأستاذ", "تخصص الطالب", "اسم الطالب 1", "رقم تسجيل 1", "اسم الطالب 2", "رقم تسجيل 2", "عنوان المذكرة", "تاريخ التسجيل"]
        row_values = [str(row_data_dict.get(k, "")).strip() for k in ordered_keys]
    else:
        row_values = [str(v).strip() for v in row_data_dict.values()]

    payload = {
        "action": "append",
        "sheet_name": worksheet_name,
        "row_data": row_values
    }
    return send_payload_to_script(payload)

def delete_registration_from_sheet(form_num):
    payload = {
        "action": "delete_row",
        "sheet_name": SHEET_FINAL_REGISTRATIONS,
        "key_val": str(form_num).strip()
    }
    return send_payload_to_script(payload)

def update_registration_in_sheet(form_num, row_data_dict):
    ordered_keys = ["رقم الاستمارة", "اسم الأستاذ", "تخصص الطالب", "اسم الطالب 1", "رقم تسجيل 1", "اسم الطالب 2", "رقم تسجيل 2", "عنوان المذكرة", "تاريخ التسجيل"]
    row_values = [str(row_data_dict.get(k, "")).strip() for k in ordered_keys]
    payload = {
        "action": "update_row",
        "sheet_name": SHEET_FINAL_REGISTRATIONS,
        "key_val": str(form_num).strip(),
        "row_data": row_values
    }
    return send_payload_to_script(payload)

def update_title_in_sheets_after_approval(teacher_name, orig_title, new_title):
    """تحديث واستبدال العنوان القديم بالعنوان الجديد في جميع الأوراق السحابية"""
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
    if not text or pd.isna(text) or str(text).strip() in ["", "nan"]:
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)

def draw_icon_if_exists(can, icon_name, x, y, width=50, height=50):
    if os.path.exists(icon_name):
        try:
            can.drawImage(icon_name, x, y, width=width, height=height, mask='auto')
        except Exception:
            pass

# --- 5. توليد PDF مع رفع التوقيع تلقائياً بحجم مخصص ومحدد ---
def generate_pdf_document(form_num, teacher_name, specialty, student1_info, student2_info, title, signature_file=None):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    page_width, page_height = letter
    center_x = page_width / 2.0

    can.setLineWidth(2)
    can.rect(20, 20, page_width - 40, page_height - 40)

    # رسم الأيقونات أقصى اليمين واليسار
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

    # إظهار أسماء الطلبة
    y_st = page_height - 390
    can.setFont(ARABIC_FONT_BOLD, 11)
    can.drawRightString(page_width - 50, y_st, reshape_arabic(f"الطالب الأول: {student1_info}"))
    if student2_info and str(student2_info).strip() not in ["", "---", "nan", "لا يوجد / خيار فردي"]:
        can.drawRightString(page_width - 50, y_st - 30, reshape_arabic(f"الطالب الثاني: {student2_info}"))

    y_sig = y_st - 80
    can.drawRightString(page_width - 60, y_sig, reshape_arabic("إمضاء المشرف:"))
    can.drawString(60, y_sig, reshape_arabic("مسؤول الشعبة:"))

    # وضع صورة التوقيع تلقائياً وبحجم مخصص ومناسب
    if signature_file is not None:
        try:
            sig_img = Image.open(signature_file)
            sig_bytes = BytesIO()
            sig_img.save(sig_bytes, format='PNG')
            sig_bytes.seek(0)
            can.drawImage(sig_bytes, page_width - 150, y_sig - 45, width=90, height=45, mask='auto')
        except Exception:
            pass

    can.setFont(ARABIC_FONT_BOLD, 12)
    can.drawCentredString(center_x, 35, reshape_arabic("السنة الجامعية: 2026-2027"))

    can.save()
    packet.seek(0)
    return packet.getvalue()

def generate_general_report_pdf(df_data, selected_specs, title_prefix="التقرير العام"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=100, bottomMargin=50)
    title_style = ParagraphStyle('ReportTitle', fontName=ARABIC_FONT_BOLD, fontSize=15, alignment=TA_CENTER, spaceAfter=15)
    cell_style = ParagraphStyle('TableCell', fontName=ARABIC_FONT, fontSize=9, alignment=TA_CENTER)
    header_cell_style = ParagraphStyle('HeaderCell', fontName=ARABIC_FONT_BOLD, fontSize=10, alignment=TA_CENTER, textColor=colors.white)

    story = []
    spec_col = [c for c in df_data.columns if "تخصص" in c or "التخصص" in c]
    spec_col_name = spec_col[0] if spec_col else "تخصص الطالب"
    
    df_filtered = df_data[df_data[spec_col_name].isin(selected_specs)].copy() if (selected_specs and spec_col_name in df_data.columns) else df_data.copy()
    specs_str = " - ".join(selected_specs) if selected_specs else "جميع التخصصات"
    story.append(Paragraph(reshape_arabic(f"{title_prefix} لتسجيلات مذكرات الماستر\n({specs_str})"), title_style))
    story.append(Spacer(1, 10))

    if not df_filtered.empty:
        raw_headers = ["عنوان المذكرة", "الطلبة المسجلون", "التخصص", "المشرف", "رقم الاستمارة", "م"]
        table_data = [[Paragraph(reshape_arabic(h), header_cell_style) for h in raw_headers]]

        for idx, (_, row) in enumerate(df_filtered.iterrows(), 1):
            st1_name = str(row.get('اسم الطالب 1', '')).strip()
            st1_reg = str(row.get('رقم تسجيل 1', '')).strip()
            st1_str = f"{st1_name} ({st1_reg})" if st1_reg else st1_name

            st2_name = str(row.get('اسم الطالب 2', '')).strip()
            st2_reg = str(row.get('رقم تسجيل 2', '')).strip()
            st2_str = f"{st2_name} ({st2_reg})" if (st2_name and st2_name not in ['---', 'nan', 'لا يوجد / خيار فردي']) else ''
            
            students_comb = f"{st1_str}\n{st2_str}" if st2_str else st1_str

            row_cells = [
                Paragraph(reshape_arabic(str(row.get("عنوان المذكرة", ""))), cell_style),
                Paragraph(reshape_arabic(students_comb), cell_style),
                Paragraph(reshape_arabic(str(row.get(spec_col_name, ""))), cell_style),
                Paragraph(reshape_arabic(str(row.get("اسم الأستاذ", ""))), cell_style),
                Paragraph(str(row.get("رقم الاستمارة", "")), cell_style),
                Paragraph(str(idx), cell_style)
            ]
            table_data.append(row_cells)

        t = Table(table_data, colWidths=[125, 140, 90, 100, 60, 25])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        story.append(t)
    else:
        story.append(Paragraph(reshape_arabic("لا توجد تسجيلات مطابقة للتخصصات المختارة."), title_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- 6. الواجهة وتسهيلات الاستخدام ---
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

    t_sub_tab1, t_sub_tab2, t_sub_tab_edit, t_sub_tab_registered, t_sub_tab3, t_sub_tab4 = st.tabs([
        "🔐 الدخول إلى حسابي", 
        "📝 تسجيل مذكرة ماستر", 
        "✏️ تصحيح/تعديل تسجيل",
        "📚 العناوين المسجلة",
        "📩 طلب تعديل عنوان",
        "📊 متابعة طلبات التعديل"
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
            if st.button("🔴 تسجيل الخروج", key="btn_logout_teacher_v36"):
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
                selected_teacher = st.selectbox("اختر اسم الأستاذ:", ["-- اختر اسمك --"] + teacher_list, key="sb_t_login_v36")
                input_pass = st.text_input("كلمة المرور:", type="password", key="inp_t_pass_v36")
                
                if st.button("الدخول إلى حسابي 🚀", key="btn_t_login_v36"):
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
                    uploaded_sig = st.file_uploader("قم برفع صورة إمضاء الأستاذ المشرف (اختياري):", type=["png", "jpg", "jpeg"], key="up_sig_new_v36")
                    
                    pdf_data = generate_pdf_document(
                        st.session_state.last_form_num, current_teacher_name, 
                        st.session_state.last_spec, st.session_state.last_st1, 
                        st.session_state.last_st2, st.session_state.last_title,
                        signature_file=uploaded_sig
                    )
                    
                    if uploaded_sig:
                        st.success("✅ تم دمج التوقيع الرقمي بنجاح في الاستمارة!")
                    
                    st.download_button("🖨️ الاستمارة جاهزة للطباعة والتحميل (PDF)", data=pdf_data, file_name=f"استمارة_{st.session_state.last_form_num}.pdf", mime="application/pdf", key="dl_pdf_v36")
                    
                    if st.button("📝 تسجيل مذكرة أخرى", key="reset_reg_v36"):
                        st.session_state.saved_successfully = False
                        st.rerun()
                else:
                    st.subheader(f"مذكرات الأستاذ: {current_teacher_name} (المسجلة حالياً: {teacher_registrations_count} من 3)")
                    selected_spec = st.selectbox("اختر التخصص:", SPECIALTIES, key="sb_spec_v36")
                    df_students = load_data_from_sheet(SHEET_STUDENTS)

                    all_registered_students = set()
                    all_registered_regs = set()
                    if not df_final.empty:
                        for _, r in df_final.iterrows():
                            if pd.notna(r.get("اسم الطالب 1")) and str(r.get("اسم الطالب 1")).strip():
                                all_registered_students.add(str(r.get("اسم الطالب 1")).strip())
                                all_registered_regs.add(str(r.get("رقم تسجيل 1")).strip())
                            if pd.notna(r.get("اسم الطالب 2")) and str(r.get("اسم الطالب 2")).strip():
                                all_registered_students.add(str(r.get("اسم الطالب 2")).strip())
                                all_registered_regs.add(str(r.get("رقم تسجيل 2")).strip())

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
                                if s_n and s_n != 'nan' and (s_n not in all_registered_students) and (s_r not in all_registered_regs):
                                    students_options.append(f"{s_n} - {s_r}")

                    col_s1, col_s2 = st.columns(2)
                    with col_s1: st1 = st.selectbox("اختر الطالب الأول (إجباري):", ["-- اختر الطالب --"] + students_options, key="st1_v36")
                    st2_opts = [s for s in students_options if s != st1]
                    with col_s2: st2 = st.selectbox("اختر الطالب الثاني (اختياري):", ["-- لا يوجد / خيار فردي --"] + st2_opts, key="st2_v36")

                    df_titles = load_data_from_sheet(SHEET_TITLES)
                    available_titles = []
                    if not df_titles.empty:
                        for i in range(0, len(df_titles.columns) - 1, 2):
                            tit_c = df_titles.columns[i]
                            tch_c = df_titles.columns[i+1]
                            matched = df_titles[df_titles[tch_c].astype(str).str.strip() == current_teacher_name]
                            if not matched.empty:
                                available_titles.extend(matched[tit_c].dropna().unique().tolist())

                    selected_title_dropdown = st.selectbox("اختر عنوان المذكرة الخاصة بك:", ["-- اختر العنوان --"] + available_titles, key="sb_title_v36")

                    if st.button("💾 حفظ في قاعدة البيانات", key="btn_save_v36"):
                        if st1 != "-- اختر الطالب --" and selected_title_dropdown != "-- اختر العنوان --":
                            next_form_num = len(df_final) + 1 if not df_final.empty else 1
                            summary_data = {
                                "رقم الاستمارة": str(next_form_num),
                                "اسم الأستاذ": current_teacher_name,
                                "تخصص الطالب": selected_spec,
                                "اسم الطالب 1": st1.split(" - ")[0].strip(),
                                "رقم تسجيل 1": st1.split(" - ")[1].strip() if " - " in st1 else "",
                                "اسم الطالب 2": st2.split(" - ")[0].strip() if st2 != "-- لا يوجد / خيار فردي --" else "",
                                "رقم تسجيل 2": st2.split(" - ")[1].strip() if " - " in st2 and st2 != "-- لا يوجد / خيار فردي --" else "",
                                "عنوان المذكرة": selected_title_dropdown.strip(),
                                "تاريخ التسجيل": datetime.now().strftime("%Y-%m-%d %H:%M")
                            }
                            if save_data_to_sheet(summary_data, SHEET_FINAL_REGISTRATIONS):
                                st.session_state.saved_successfully = True
                                st.session_state.last_form_num = next_form_num
                                st.session_state.last_spec = selected_spec
                                st.session_state.last_st1 = st1
                                st.session_state.last_st2 = st2
                                st.session_state.last_title = selected_title_dropdown
                                st.rerun()

    with t_sub_tab_edit:
        if st.session_state.teacher_logged_in:
            teacher_curr = str(st.session_state.current_teacher).strip()
            st.subheader("✏️ تصحيح أخطاء التسجيل (استدراك موضوع أو طلبة مذكراتك)")
            
            df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final_all.empty:
                t_col_name = [c for c in df_final_all.columns if "أستاذ" in c or "استاذ" in c]
                if t_col_name:
                    my_reg = df_final_all[df_final_all[t_col_name[0]].astype(str).str.strip() == teacher_curr].copy()
                    if not my_reg.empty:
                        reg_forms = my_reg["رقم الاستمارة"].tolist() if "رقم الاستمارة" in my_reg.columns else []
                        selected_form_to_edit = st.selectbox("اختر رقم استمارة المذكرة المراد تصحيحها:", ["-- اختر رقم الاستمارة --"] + reg_forms, key="sb_edit_form_v36")
                        
                        if selected_form_to_edit != "-- اختر رقم الاستمارة --":
                            target_row = my_reg[my_reg["رقم الاستمارة"] == selected_form_to_edit].iloc[0]
                            st.info(f"📍 **المعلومات الحالية:** التخصص: `{target_row.get('تخصص الطالب', '')}` | العنوان: `{target_row.get('عنوان المذكرة', '')}`")
                            
                            edit_spec = st.selectbox("تعديل التخصص:", SPECIALTIES, index=SPECIALTIES.index(target_row.get('تخصص الطالب', SPECIALTIES[0])) if target_row.get('تخصص الطالب') in SPECIALTIES else 0, key="sb_edit_spec_v36")
                            
                            df_titles = load_data_from_sheet(SHEET_TITLES)
                            available_titles = []
                            if not df_titles.empty:
                                for i in range(0, len(df_titles.columns) - 1, 2):
                                    tit_c = df_titles.columns[i]
                                    tch_c = df_titles.columns[i+1]
                                    matched = df_titles[df_titles[tch_c].astype(str).str.strip() == teacher_curr]
                                    if not matched.empty:
                                        available_titles.extend(matched[tit_c].dropna().unique().tolist())

                            curr_title = target_row.get('عنوان المذكرة', '')
                            if curr_title not in available_titles: available_titles.append(curr_title)

                            edit_title = st.selectbox("تصحيح اختيار العنوان:", available_titles, index=available_titles.index(curr_title) if curr_title in available_titles else 0, key="sb_edit_title_v36")
                            
                            df_students = load_data_from_sheet(SHEET_STUDENTS)
                            students_options = []
                            spec_col_map = {
                                "لسانيات عامة": ("تخصص لسانيات عامة", "رقم تسجيل لسانيات عامة"),
                                "أدب عربي حديث ومعاصر": ("تخصص أدب حديث ومعاصر", "رقم تسجيل أدب حديث ومعاصر"),
                                "نقد حديث معاصر": ("تخصص نقد حديث ومعاصر", "رقم تسجيل نقد حديث ومعاصر"),
                                "أدب شعبي": ("تخصص أدب شعبي", "رقم تسجيل أدب شعبي")
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

                            c_st1 = f"{target_row.get('اسم الطالب 1', '')} - {target_row.get('رقم تسجيل 1', '')}"
                            c_st2 = f"{target_row.get('اسم الطالب 2', '')} - {target_row.get('رقم تسجيل 2', '')}" if target_row.get('اسم الطالب 2') else "-- لا يوجد / خيار فردي --"

                            if c_st1 not in students_options and target_row.get('اسم الطالب 1'): students_options.append(c_st1)

                            col_es1, col_es2 = st.columns(2)
                            with col_es1: edit_st1 = st.selectbox("تصحيح الطالب الأول:", students_options, index=students_options.index(c_st1) if c_st1 in students_options else 0, key="sb_edit_st1_v36")
                            st2_edit_opts = ["-- لا يوجد / خيار فردي --"] + [s for s in students_options if s != edit_st1]
                            with col_es2: edit_st2 = st.selectbox("تصحيح الطالب الثاني:", st2_edit_opts, index=st2_edit_opts.index(c_st2) if c_st2 in st2_edit_opts else 0, key="sb_edit_st2_v36")

                            if st.button("💾 حفظ التصحيحات والتعديلات", key="btn_save_edit_v36"):
                                updated_data = {
                                    "رقم الاستمارة": str(selected_form_to_edit),
                                    "اسم الأستاذ": teacher_curr,
                                    "تخصص الطالب": edit_spec,
                                    "اسم الطالب 1": edit_st1.split(" - ")[0].strip(),
                                    "رقم تسجيل 1": edit_st1.split(" - ")[1].strip() if " - " in edit_st1 else "",
                                    "اسم الطالب 2": edit_st2.split(" - ")[0].strip() if edit_st2 != "-- لا يوجد / خيار فردي --" else "",
                                    "رقم تسجيل 2": edit_st2.split(" - ")[1].strip() if " - " in edit_st2 and edit_st2 != "-- لا يوجد / خيار فردي --" else "",
                                    "عنوان المذكرة": edit_title.strip(),
                                    "تاريخ التسجيل": datetime.now().strftime("%Y-%m-%d %H:%M")
                                }
                                if update_registration_in_sheet(selected_form_to_edit, updated_data):
                                    st.success("✅ تم تصحيح بيانات المذكرة بنجاح وتحديث القاعدة السحابية!")
                                    st.rerun()

    with t_sub_tab_registered:
        if st.session_state.teacher_logged_in:
            teacher_curr = str(st.session_state.current_teacher).strip()
            st.subheader(f"📚 العناوين المسجلة باسم الأستاذ: {teacher_curr}")
            if st.button("🔄 تحديث قاعدة البيانات وإظهار العناوين المسجلة", key="btn_ref_reg_v36"):
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

                        col_p1, col_del = st.columns(2)
                        with col_p1:
                            st.markdown("### 🖨️ طباعة واستخراج الاستمارة مع التوقيع")
                            titles_list_for_print = my_reg["عنوان المذكرة"].dropna().tolist() if "عنوان المذكرة" in my_reg.columns else []
                            selected_title_to_print = st.selectbox("اختر عنوان المذكرة لطباعتها:", ["-- اختر العنوان للطباعة --"] + titles_list_for_print, key="sb_print_reg_v36")
                            
                            if selected_title_to_print != "-- اختر العنوان للطباعة --":
                                uploaded_sig_reg = st.file_uploader("قم برفع صورة إمضاء الأستاذ المشرف:", type=["png", "jpg", "jpeg"], key="up_sig_reg_v36")
                                p_row = my_reg[my_reg["عنوان المذكرة"] == selected_title_to_print].iloc[0]
                                st1_c = f"{p_row.get('اسم الطالب 1', '')} - {p_row.get('رقم تسجيل 1', '')}"
                                st2_c = f"{p_row.get('اسم الطالب 2', '')} - {p_row.get('رقم تسجيل 2', '')}"
                                
                                pdf_bytes_row = generate_pdf_document(
                                    p_row.get("رقم الاستمارة", "1"),
                                    teacher_curr,
                                    p_row.get("تخصص الطالب", ""),
                                    st1_c,
                                    st2_c,
                                    p_row.get("عنوان المذكرة", ""),
                                    signature_file=uploaded_sig_reg
                                )
                                if uploaded_sig_reg:
                                    st.success("✅ الاستمارة جاهزة للطباعة والتحميل!")
                                st.download_button(
                                    label=f"🖨️ تحميل استمارة «{selected_title_to_print[:20]}...»",
                                    data=pdf_bytes_row,
                                    file_name=f"استمارة_{p_row.get('رقم الاستمارة', '1')}_{teacher_curr}.pdf",
                                    mime="application/pdf",
                                    key="btn_dl_registered_pdf_v36"
                                )

                        with col_del:
                            st.markdown("### 🗑️ إلغاء وحذف تسجيل مذكرة")
                            form_to_del = st.selectbox("اختر الاستمارة المراد حذفها تماماً:", ["-- اختر الاستمارة للحذف --"] + my_reg["رقم الاستمارة"].tolist(), key="sb_del_form_v36")
                            if form_to_del != "-- اختر الاستمارة للحذف --":
                                confirm_del = st.checkbox("أؤكد رغبتي في حذف هذه المذكرة نهائياً من قاعدة البيانات ⚠️", key="chk_confirm_del_v36")
                                if st.button("❌ حذف المذكرة نهائياً", key="btn_delete_reg_v36"):
                                    if confirm_del:
                                        if delete_registration_from_sheet(form_to_del):
                                            st.success("تم حذف المذكرة نهائياً من قاعدة البيانات!")
                                            st.rerun()
                    else:
                        st.info("لا توجد مذكرات مسجلة باسمك بعد.")
            else:
                st.info("لا توجد مذكرات مسجلة بالقاعدة بعد.")

    with t_sub_tab3:
        if st.session_state.teacher_logged_in:
            st.subheader("📩 تقديم طلب تعديل طفيف على عنوان مذكرة")
            teacher_curr = str(st.session_state.current_teacher).strip()
            selected_spec_mod = st.selectbox("اختر التخصص المرتبط بالعنوان:", SPECIALTIES, key="sb_mod_spec_v36")
            
            df_titles = load_data_from_sheet(SHEET_TITLES)
            my_titles = []
            if not df_titles.empty:
                for i in range(0, len(df_titles.columns) - 1, 2):
                    tit_c = df_titles.columns[i]
                    tch_c = df_titles.columns[i+1]
                    matched = df_titles[df_titles[tch_c].astype(str).str.strip() == teacher_curr]
                    if not matched.empty:
                        my_titles.extend(matched[tit_c].dropna().unique().tolist())

            orig_t = st.selectbox("اختر العنوان الأصلي المراد تعديله:", ["-- اختر العنوان الأصلي --"] + my_titles, key="sb_mod_orig_dropdown_v36")
            new_t = st.text_input("العنوان الجديد المقترح:", key="inp_mod_new_v36")

            if st.button("إرسال طلب التعديل لمسؤول التخصص 📤", key="btn_mod_send_v36"):
                if orig_t != "-- اختر العنوان الأصلي --" and new_t.strip():
                    new_mod = {
                        "الأستاذ": teacher_curr,
                        "التخصص": selected_spec_mod,
                        "العنوان الأصلي": orig_t.strip(),
                        "العنوان الجديد": new_t.strip(),
                        "الحالة": "في الانتظار",
                        "معالج_الطلب": "في الانتظار"
                    }
                    if save_data_to_sheet(new_mod, SHEET_MOD_REQUESTS):
                        st.success("تم إرسال الطلب وحفظه بنجاح!")
                        st.rerun()

    with t_sub_tab4:
        if st.session_state.teacher_logged_in:
            st.subheader("📊 متابعة طلبات التعديل والقرارات المتخذة")
            teacher_curr = str(st.session_state.current_teacher).strip()
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            if not df_mod.empty:
                t_col = [c for c in df_mod.columns if "أستاذ" in c or "استاذ" in c or "الأستاذ" in c]
                if t_col:
                    my_mods = df_mod[df_mod[t_col[0]].astype(str).str.strip() == teacher_curr].copy()
                    if not my_mods.empty:
                        my_mods.index = range(1, len(my_mods) + 1)
                        st.dataframe(my_mods, use_container_width=True)
                    else:
                        st.info("لا توجد طلبات تعديل مقدمة من طرفك.")

# ==========================================
# 2- فضاء مسؤولي التخصصات
# ==========================================
with tab_spec_admin:
    if 'spec_admin_logged_in' not in st.session_state:
        st.session_state.spec_admin_logged_in = False
        st.session_state.current_spec_admin = ""

    if not st.session_state.spec_admin_logged_in:
        st.subheader("دخول مسؤول التخصص")
        col_admin_spec, col_admin_pass = st.columns(2)
        with col_admin_spec: admin_selected_spec = st.selectbox("اختر التخصص للمسؤول:", SPECIALTIES, key="sb_admin_spec_login_v36")
        with col_admin_pass: admin_pass_input = st.text_input("كلمة مرور المسؤول:", type="password", key="admin_p_in_v36")

        if st.button("تسجيل الدخول كمسؤول تخصص 🚀", key="btn_login_spec_admin_v36"):
            df_admins = load_data_from_sheet(SHEET_ADMINS)
            if str(admin_pass_input) == MASTER_SUPER_PASS:
                st.session_state.spec_admin_logged_in = True
                st.session_state.current_spec_admin = admin_selected_spec
                st.rerun()
            elif not df_admins.empty:
                spec_col = [c for c in df_admins.columns if "تخصص" in c][0]
                pass_col = [c for c in df_admins.columns if "كلمة" in c or "مرور" in c][0]
                match = df_admins[df_admins[spec_col] == admin_selected_spec]
                if not match.empty and str(match[pass_col].values[0]) == str(admin_pass_input):
                    st.session_state.spec_admin_logged_in = True
                    st.session_state.current_spec_admin = admin_selected_spec
                    st.rerun()
                else:
                    st.error("كلمة المرور غير صحيحة!")
    else:
        admin_selected_spec = st.session_state.current_spec_admin
        st.success(f"مرحباً بك، مسؤول تخصص: **{admin_selected_spec}**")
        
        adm_tab1, adm_tab2, adm_tab3, adm_tab_stats, adm_tab_print = st.tabs([
            "📚 العناوين وحالتها", 
            "👥 الطلبة المسجلون", 
            "📩 طلبات التعديل", 
            "📈 إحصائيات التخصص",
            "🖨️ طباعة التقرير العام"
        ])

        with adm_tab1:
            st.write("### قائمة العناوين وإمكانية البحث")
            df_titles = load_data_from_sheet(SHEET_TITLES)
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            
            tit_col_name = [c for c in df_final.columns if "عنوان" in c]
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
                            status_str = "🔴 موضوع مسجل" if t_val in registered_titles else "🟢 موضوع غير مسجل"
                            titles_status.append({"عنوان المذكرة": t_val, "الأستاذ المشرف": tch_val, "الحالة": status_str})
            
            df_status_disp = pd.DataFrame(titles_status)
            if not df_status_disp.empty:
                df_status_disp.index = range(1, len(df_status_disp) + 1)
                st.dataframe(df_status_disp, use_container_width=True)

        with adm_tab2:
            st.write(f"### 👥 قائمة الطلبة المسجلين بتخصص: {admin_selected_spec}")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            spec_col = [c for c in df_final.columns if "تخصص" in c or "التخصص" in c]
            if not df_final.empty and spec_col:
                spec_registrations = df_final[df_final[spec_col[0]] == admin_selected_spec].copy()
                spec_registrations.index = range(1, len(spec_registrations) + 1)
                st.dataframe(spec_registrations, use_container_width=True)

        with adm_tab3:
            st.write("### 📩 البت في طلبات التعديل (مع التحديث المباشر للعنوان في الشيت)")
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            spec_mod_col = [c for c in df_mod.columns if "تخصص" in c or "التخصص" in c]
            if not df_mod.empty and spec_mod_col:
                spec_reqs = df_mod[df_mod[spec_mod_col[0]] == admin_selected_spec].copy()
                spec_reqs.index = range(1, len(spec_reqs) + 1)
                st.dataframe(spec_reqs, use_container_width=True)

                orig_col_name = [c for c in spec_reqs.columns if "أصلي" in c or "اصلي" in c or "العنوان" in c][0]
                status_col_name = [c for c in spec_reqs.columns if "حالة" in c or "الحالة" in c][0]

                pending_reqs = spec_reqs[spec_reqs[status_col_name].isin(["قيد الانتظار", "في الانتظار"])]

                if not pending_reqs.empty:
                    req_orig_title = st.selectbox("اختر طلب التعديل للبت فيه:", ["-- اختر الطلب --"] + pending_reqs[orig_col_name].tolist(), key="sb_mod_dec_v36")
                    if req_orig_title != "-- اختر الطلب --":
                        selected_req_row = pending_reqs[pending_reqs[orig_col_name] == req_orig_title].iloc[0]
                        teacher_name_req = selected_req_row.get("الأستاذ", "")
                        new_title_req = selected_req_row.get("العنوان الجديد", "")

                        col_a, col_r = st.columns(2)
                        with col_a:
                            if st.button("قبول التعديل وتحديث العنوان ✅", key="btn_accept_v36"):
                                if update_mod_request_status_in_sheet(req_orig_title, "تعديل مقبول", admin_selected_spec, teacher_name=teacher_name_req, new_title=new_title_req):
                                    st.success("تم تسجيل القبول وتحديث العنوان الجديد سحابياً في جميع الأوراق!")
                                    st.rerun()
                        with col_r:
                            if st.button("رفض التعديل ❌", key="btn_reject_v36"):
                                if update_mod_request_status_in_sheet(req_orig_title, "تعديل مرفوض", admin_selected_spec):
                                    st.warning("تم تسجيل الرفض بنجاح!")
                                    st.rerun()

        with adm_tab_stats:
            st.write(f"### 📈 إحصائيات التخصص: {admin_selected_spec}")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            spec_col = [c for c in df_final.columns if "تخصص" in c or "التخصص" in c]
            t_col = [c for c in df_final.columns if "أستاذ" in c or "استاذ" in c]
            if not df_final.empty and spec_col:
                df_spec = df_final[df_final[spec_col[0]] == admin_selected_spec]
                st.metric("عدد المذكرات المسجلة", len(df_spec))
                st.metric("عدد الأساتذة المشرفين", df_spec[t_col[0]].nunique() if t_col else 0)

        with adm_tab_print:
            st.write(f"### 🖨️ طباعة التقرير العام لتخصص: {admin_selected_spec}")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if st.button("📥 إنشاء وتصدير التقرير العام (PDF)", key="btn_print_spec_pdf_v36"):
                pdf_b = generate_general_report_pdf(df_final, [admin_selected_spec], title_prefix=f"تقرير تخصص {admin_selected_spec}")
                st.download_button("🖨️ تحميل الملف", data=pdf_b, file_name=f"تقرير_{admin_selected_spec}.pdf", mime="application/pdf", key="dl_spec_pdf_v36")

# ==========================================
# 3- فضاء مسؤولَي الشعبتين
# ==========================================
with tab_dept_admin:
    if 'dept_admin_logged_in' not in st.session_state:
        st.session_state.dept_admin_logged_in = False

    if not st.session_state.dept_admin_logged_in:
        st.subheader("دخول مسؤولَي الشعبتين")
        dept_pass_input = st.text_input("كلمة مرور مسؤول الشعبة:", type="password", key="dept_p_in_v36")
        if st.button("تسجيل الدخول كمسؤول شعبة 🚀", key="btn_login_dept_admin_v36"):
            if dept_pass_input in ["1234", MASTER_SUPER_PASS]:
                st.session_state.dept_admin_logged_in = True
                st.rerun()
            else:
                st.error("كلمة المرور غير صحيحة!")
    else:
        st.subheader("🏛️ فضاء مسؤولَي الشعبتين - الإدارة العامة")
        d_tab1, d_tab2, d_tab3, d_tab4 = st.tabs([
            "📚 المواضيع المسجلة بالقسم",
            "📩 إدارة طلبات التعديل",
            "📈 التفاصيل والإحصائيات العامة",
            "🖨️ طباعة التقرير العام"
        ])

        with d_tab1:
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final.empty:
                df_final.index = range(1, len(df_final) + 1)
                st.dataframe(df_final, use_container_width=True)

        with d_tab2:
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            if not df_mod.empty:
                df_mod.index = range(1, len(df_mod) + 1)
                st.dataframe(df_mod, use_container_width=True)

        with d_tab3:
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            st.metric("إجمالي المذكرات المسجلة بالقسم", len(df_final) if not df_final.empty else 0)

        with d_tab4:
            selected_specs_report = st.multiselect("حدد التخصصات المطلوب طباعتها:", options=SPECIALTIES, default=SPECIALTIES, key="ms_dept_v36")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if st.button("📥 تصدير التقرير العام (PDF)", key="btn_print_dept_pdf_v36"):
                pdf_b = generate_general_report_pdf(df_final, selected_specs_report)
                st.download_button("🖨️ تحميل الملف", data=pdf_b, file_name="التقرير_العام.pdf", mime="application/pdf", key="dl_dept_pdf_v36")
