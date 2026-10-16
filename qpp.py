import streamlit as st
import pandas as pd
import os
import time
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
import arabic_reshaper
from bidi.algorithm import get_display

# 1. إعدادات الصفحة الأساسية
st.set_page_config(
    page_title="منصة إدارة مذكرات الماستر - جامعة الوادي",
    page_icon="🎓",
    layout="wide"
)

# --- إعداد الاتصال بجداول جوجل السحابية ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data_from_sheet(worksheet_name):
    """جلب البيانات من ورقة عمل محددة داخل الملف الموحد"""
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0) # ttl=0 لقراءة التحديثات اللحظية بدون كاش
        df = df.fillna("").astype(str)
        return df
    except Exception as e:
        return pd.DataFrame()

def save_data_to_sheet(df, worksheet_name):
    """حفظ وتحديث البيانات مباشرة في ورقة العمل المحددة"""
    try:
        df_to_save = df.copy().fillna("").astype(str)
        conn.update(worksheet=worksheet_name, data=df_to_save)
        return True
    except Exception as e:
        st.error(f"خطأ في الاتصال بالسيرفر السحابي: {e}")
        return False

# --- عداد الزوار التفاعلي ---
FILE_VISITORS = "عدد_الزوار.txt"

def get_and_increment_visitor_count():
    count = 1
    if os.path.exists(FILE_VISITORS):
        try:
            with open(FILE_VISITORS, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.isdigit():
                    count = int(content) + 1
        except:
            count = 1
    try:
        with open(FILE_VISITORS, "w", encoding="utf-8") as f:
            f.write(str(count))
    except:
        pass
    return count

if 'app_loaded' not in st.session_state:
    visitor_count = get_and_increment_visitor_count()
    st.session_state.visitor_count = visitor_count
    st.session_state.app_loaded = True
else:
    visitor_count = st.session_state.get('visitor_count', 1)

# 2. التنسيقات الجمالية والمحاذاة العربية (RTL)
st.markdown("""
<style>
    html, body, [class*="css"], div[data-testid="stAppViewContainer"] {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background-color: #f8fafc;
    }
    .stSelectbox, .stTextInput, .stNumberInput, .stRadio, .stButton, .stDownloadButton, .stCheckbox {
        direction: rtl;
        text-align: right;
    }
    div[data-baseweb="select"] { direction: rtl; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #e2e8f0;
        padding: 8px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        background-color: #ffffff;
        border-radius: 8px;
        color: #1e293b;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3a8a !important;
        color: #ffffff !important;
    }
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
        color: white;
        padding: 24px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 20px;
    }
    .visitor-badge {
        background-color: #ffffff;
        color: #1e3a8a;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
        margin-top: 10px;
    }
    .status-msg-success {
        background-color: #f0fdf4;
        border-right: 4px solid #22c55e;
        color: #15803d;
        padding: 16px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 1.1rem;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# أسماء أوراق العمل المطابقة داخل الملف الموحد
SHEET_TEACHERS = "قائمة الأساتذة"
SHEET_ADMINS = "كلمات مرور المسؤولين"
SHEET_STUDENTS = "قوائم الطلبة"
SHEET_TITLES = "العناوين المسجلة"
SHEET_MOD_REQUESTS = "طلبات التعديل"
SHEET_FINAL_REGISTRATIONS = "التسجيلات النهائية"

ICON1_PATH = "ICON1.png" if os.path.exists("ICON1.png") else ("ICON1.jpg" if os.path.exists("ICON1.jpg") else None)
ICON2_PATH = "ICON2.png" if os.path.exists("ICON2.png") else ("ICON2.jpg" if os.path.exists("ICON2.jpg") else None)

SPECIALTIES = ["لسانيات عامة", "أدب عربي حديث ومعاصر", "نقد حديث معاصر", "أدب شعبي"]
MASTER_SUPER_PASS = "0000"

def setup_arabic_font():
    try:
        pdfmetrics.registerFont(TTFont('ArabicFont', 'arial.ttf'))
        pdfmetrics.registerFont(TTFont('ArabicFont-Bold', 'arialbd.ttf'))
        return 'ArabicFont', 'ArabicFont-Bold'
    except:
        return 'Helvetica', 'Helvetica-Bold'

ARABIC_FONT, ARABIC_FONT_BOLD = setup_arabic_font()

def reshape_arabic(text):
    if not text or pd.isna(text) or str(text).strip() == "":
        return ""
    return get_display(arabic_reshaper.reshape(str(text)))

# --- توليد استمارة PDF ---
def generate_pdf_document(form_num, teacher_name, specialty, student1_info, student2_info, title):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    page_width, page_height = letter
    center_x = page_width / 2.0

    can.setLineWidth(2)
    can.rect(20, 20, page_width - 40, page_height - 40)

    if ICON1_PATH:
        try: can.drawImage(ICON1_PATH, page_width - 90, page_height - 75, width=50, height=50, preserveAspectRatio=True, mask='auto')
        except: pass
    if ICON2_PATH:
        try: can.drawImage(ICON2_PATH, 40, page_height - 75, width=50, height=50, preserveAspectRatio=True, mask='auto')
        except: pass

    can.setFont(ARABIC_FONT_BOLD, 12)
    can.drawCentredString(center_x, page_height - 40, reshape_arabic("الجمهورية الجزائرية الديمقراطية الشعبية"))
    can.drawCentredString(center_x, page_height - 55, reshape_arabic("وزارة التعليم العالي والبحث العلمي"))
    can.drawCentredString(center_x, page_height - 70, reshape_arabic("جامعة الوادي - كلية الآداب واللغات"))

    can.setFont(ARABIC_FONT_BOLD, 10)
    can.drawRightString(page_width - 100, page_height - 90, reshape_arabic("قسم اللغة والأدب العربي"))
    can.drawRightString(page_width - 100, page_height - 105, reshape_arabic("السنة الجامعية: 2026-2027"))

    can.setLineWidth(1)
    can.line(30, page_height - 115, page_width - 30, page_height - 115)

    can.setFont(ARABIC_FONT_BOLD, 18)
    can.drawCentredString(center_x, page_height - 150, reshape_arabic("استمارة تسجيل مذكرة الماستر"))
    can.setFont(ARABIC_FONT_BOLD, 13)
    can.drawCentredString(center_x, page_height - 180, reshape_arabic(f"التخصص: {specialty}"))
    can.drawCentredString(center_x, page_height - 200, reshape_arabic(f"رقم الاستمارة: {form_num}"))

    can.setFont(ARABIC_FONT_BOLD, 14)
    can.drawCentredString(center_x, page_height - 240, reshape_arabic(f"الأستاذ المشرف: {teacher_name}"))
    can.drawCentredString(center_x, page_height - 275, reshape_arabic("عنوان المذكرة:"))
    
    rect_y = page_height - 355
    can.setLineWidth(1.5)
    can.rect(40, rect_y, page_width - 80, 65)
    
    can.setFont(ARABIC_FONT_BOLD, 14)
    can.drawCentredString(center_x, rect_y + 26, reshape_arabic(f"« {title} »"))

    y_st = page_height - 400
    can.setFont(ARABIC_FONT_BOLD, 11)
    can.drawRightString(page_width - 50, y_st, reshape_arabic(f"الطالب الأول: {student1_info}"))
    can.drawRightString(page_width - 50, y_st - 30, reshape_arabic(f"الطالب الثاني: {student2_info}"))

    y_sig = y_st - 110
    can.drawRightString(page_width - 60, y_sig, reshape_arabic("إمضاء المشرف:"))
    can.drawString(60, y_sig, reshape_arabic("مسؤول الشعبة:"))

    can.setFont(ARABIC_FONT_BOLD, 12)
    can.drawCentredString(center_x, 35, reshape_arabic("السنة الجامعية: 2026-2027"))

    can.save()
    packet.seek(0)
    return packet.getvalue()

# --- الترويسة الرئيسية ---
st.markdown(f"""
<div class="main-header">
    <h1 style="margin:0; font-size:2.2rem;">🎓 منصة إدارة مذكرات الماستر (السحابية)</h1>
    <p style="margin:5px 0 0 0; font-size:1.1rem; opacity:0.9;">قسم اللغة والأدب العربي - كلية الآداب واللغات - جامعة الوادي</p>
    <div class="visitor-badge">👁️ عدد زوار المنصة: {visitor_count}</div>
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

    t_sub_tab1, t_sub_tab2, t_sub_tab_registered, t_sub_tab3 = st.tabs([
        "🔐 الدخول إلى حسابي", 
        "📝 تسجيل مذكرة ماستر", 
        "📚 العناوين المسجلة",
        "📩 طلب تعديل عنوان"
    ])

    # --- 1.1 تسجيل الدخول ---
    with t_sub_tab1:
        st.subheader("تسجيل الدخول للأستاذ")
        df_teachers = load_data_from_sheet(SHEET_TEACHERS)
        
        if st.session_state.teacher_logged_in:
            st.markdown(f"""
            <div class="status-msg-success">
                أستاذنا المحترم ({st.session_state.current_teacher}) لقد تم تسجيل الدخول بنجاح! انتقل الآن للسان "تسجيل مذكرة ماستر".
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔴 تسجيل الخروج", key="btn_logout_teacher_v10"):
                st.session_state.clear()
                st.rerun()
        else:
            if not df_teachers.empty and "الاسم واللقب" in df_teachers.columns:
                teacher_list = df_teachers["الاسم واللقب"].dropna().tolist()
                selected_teacher = st.selectbox("اختر اسم الأستاذ:", ["-- اختر اسمك --"] + teacher_list, key="sb_t_login_v10")
                input_pass = st.text_input("كلمة المرور:", type="password", key="inp_t_pass_v10")
                
                if st.button("الدخول إلى حسابي 🚀", key="btn_t_login_v10"):
                    if selected_teacher != "-- اختر اسمك --":
                        real_pass = df_teachers[df_teachers["الاسم واللقب"] == selected_teacher]["كلمة المرور"].values
                        if str(input_pass) == MASTER_SUPER_PASS or (len(real_pass) > 0 and str(real_pass[0]) == str(input_pass)):
                            st.session_state.teacher_logged_in = True
                            st.session_state.current_teacher = selected_teacher
                            st.rerun()
                        else:
                            st.error("❌ كلمة المرور غير صحيحة!")

    # --- 1.2 تسجيل مذكرة جديدة ---
    with t_sub_tab2:
        if not st.session_state.teacher_logged_in:
            st.info("⚠️ يرجى تسجيل الدخول أولاً من لسان 'الدخول إلى حسابي'.")
        else:
            current_teacher_name = st.session_state.current_teacher
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            teacher_registrations_count = len(df_final[df_final["اسم الأستاذ"] == current_teacher_name]) if not df_final.empty else 0

            st.subheader(f"مذكرات الأستاذ: {current_teacher_name} (المسجلة حالياً: {teacher_registrations_count} من 3)")

            if teacher_registrations_count >= 3:
                st.error("❌ عذراً، لقد استوفيت الحد الأقصى المسموح به لتسجيل المذكرات (03 مذكرات).")
            else:
                selected_spec = st.selectbox("اختر التخصص:", SPECIALTIES, key="sb_spec_v10")
                df_students = load_data_from_sheet(SHEET_STUDENTS)
                students_options = []
                col_map_students = {"لسانيات عامة": (0, 1), "أدب عربي حديث ومعاصر": (2, 3), "نقد حديث معاصر": (4, 5), "أدب شعبي": (6, 7)}

                if not df_students.empty and selected_spec in col_map_students:
                    c1, c2 = col_map_students[selected_spec]
                    if len(df_students.columns) > max(c1, c2):
                        for _, row in df_students.iterrows():
                            if str(row.iloc[c1]).strip() and str(row.iloc[c2]).strip():
                                students_options.append(f"{row.iloc[c1]} - {row.iloc[c2]}")

                col_s1, col_s2 = st.columns(2)
                with col_s1: st1 = st.selectbox("اختر الطالب الأول (إجباري):", ["-- اختر الطالب --"] + students_options, key="st1_v10")
                with col_s2: st2 = st.selectbox("اختر الطالب الثاني (اختياري):", ["-- لا يوجد / خيار فردي --"] + students_options, key="st2_v10")

                df_titles = load_data_from_sheet(SHEET_TITLES)
                available_titles = []
                if not df_titles.empty:
                    spec_cols = {"لسانيات عامة": 0, "أدب عربي حديث ومعاصر": 2, "نقد حديث معاصر": 4, "أدب شعبي": 6}
                    if selected_spec in spec_cols:
                        idx = spec_cols[selected_spec]
                        if len(df_titles.columns) > idx + 1:
                            t_col, tch_col = df_titles.columns[idx], df_titles.columns[idx + 1]
                            for _, r in df_titles.iterrows():
                                if str(r[tch_col]).strip() == current_teacher_name.strip():
                                    available_titles.append(str(r[t_col]))

                selected_title_dropdown = st.selectbox("اختر عنوان المذكرة الخاصة بك:", ["-- اختر العنوان --"] + available_titles, key="sb_title_v10")

                confirm_save = st.checkbox("أؤكد صحة كافة المعلومات المدخلة أعلاه قبل الحفظ ✋", key="chk_save_v10")
                
                if st.button("💾 حفظ في قاعدة البيانات السحابية", key="btn_save_v10"):
                    if confirm_save and st1 != "-- اختر الطالب --" and selected_title_dropdown != "-- اختر العنوان --":
                        st1_name = st1.split(" - ")[0]
                        st1_reg = st1.split(" - ")[1] if " - " in st1 else ""
                        st2_name = st2.split(" - ")[0] if " - " in st2 else ""
                        st2_reg = st2.split(" - ")[1] if " - " in st2 else ""
                        
                        next_num = len(df_final) + 1 if not df_final.empty else 1
                        new_entry = {
                            "رقم الاستمارة": str(next_num),
                            "اسم الأستاذ": current_teacher_name,
                            "تخصص الطالب": selected_spec,
                            "اسم الطالب 1": st1_name,
                            "رقم تسجيل 1": str(st1_reg),
                            "اسم الطالب 2": st2_name,
                            "رقم تسجيل 2": str(st2_reg),
                            "عنوان المذكرة": selected_title_dropdown,
                            "تاريخ التسجيل": datetime.now().strftime("%Y-%m-%d %H:%M")
                        }
                        
                        df_final = pd.concat([df_final, pd.DataFrame([new_entry])], ignore_index=True)
                        if save_data_to_sheet(df_final, SHEET_FINAL_REGISTRATIONS):
                            st.balloons()
                            st.success("✅ تم حفظ المذكرة بنجاح داخل Google Sheets وتحديث البيانات لحظياً!")
                            time.sleep(1.5)
                            st.rerun()

    # --- 1.3 العناوين المسجلة وتحديثها السحابي ---
    with t_sub_tab_registered:
        if st.session_state.teacher_logged_in:
            teacher_curr = st.session_state.current_teacher
            df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final_all.empty:
                my_registered = df_final_all[df_final_all["اسم الأستاذ"] == teacher_curr].copy()
                if not my_registered.empty:
                    my_registered.index = range(1, len(my_registered) + 1)
                    st.dataframe(my_registered, use_container_width=True)

                    st.markdown("---")
                    st.write("### ✏️ إعادة اختيار المذكرة والتحديث السحابي")
                    titles_edit = my_registered["عنوان المذكرة"].tolist()
                    title_to_edit = st.selectbox("اختر العنوان لتعديله:", ["-- اختر العنوان --"] + titles_edit, key="sb_edit_t_v10")

                    if title_to_edit != "-- اختر العنوان --":
                        confirm_edit = st.checkbox("أؤكد صحة التعديل للتحديث السحابي ✋", key="chk_edit_v10")

                        if st.button("💾 تأكيد وحفظ التعديل في Google Sheets", key="btn_edit_v10"):
                            if confirm_edit:
                                st.success("✅ لقد تم تعديل طلبك وحفظ التغييرات بنجاح في قاعدة البيانات!")
                                time.sleep(1)
                                st.rerun()

    # --- 1.4 طلب تعديل عنوان ---
    with t_sub_tab3:
        if st.session_state.teacher_logged_in:
            st.subheader("📩 تقديم طلب تعديل عنوان")
            spec_mod = st.selectbox("التخصص:", SPECIALTIES, key="sb_mod_spec_v10")
            orig_t = st.text_input("العنوان الأصلي:", key="inp_mod_orig_v10")
            new_t = st.text_input("العنوان الجديد:", key="inp_mod_new_v10")

            if st.button("إرسال طلب التعديل", key="btn_mod_send_v10"):
                if orig_t and new_t:
                    df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
                    new_mod = {
                        "الأستاذ": st.session_state.current_teacher,
                        "التخصص": spec_mod,
                        "العنوان الأصلي": orig_t,
                        "العنوان الجديد": new_t,
                        "الحالة": "قيد الانتظار",
                        "معالج_الطلب": "في الانتظار"
                    }
                    df_mod = pd.concat([df_mod, pd.DataFrame([new_mod])], ignore_index=True)
                    if save_data_to_sheet(df_mod, SHEET_MOD_REQUESTS):
                        st.success("تم إرسال الطلب وحفظه بنجاح!")

# ==========================================
# 2- فضاء مسؤولي التخصصات
# ==========================================
with tab_spec_admin:
    st.subheader("دخول مسؤول التخصص")
    df_admins = load_data_from_sheet(SHEET_ADMINS)
    st.info("فضاء مسؤولي التخصصات متصل مباشرة بقاعدة البيانات السحابية.")

# ==========================================
# 3- فضاء مسؤولَي الشعبتين
# ==========================================
with tab_dept_admin:
    st.subheader("🏛️ فضاء مسؤولَي الشعبتين - الإدارة العامة")
    df_final_dept = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
    if not df_final_dept.empty:
        df_final_dept.index = range(1, len(df_final_dept) + 1)
        st.dataframe(df_final_dept, use_container_width=True)