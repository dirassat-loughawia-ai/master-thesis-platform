import streamlit as st
import pandas as pd
import os
import time
import requests
import urllib.parse
from datetime import datetime
from io import BytesIO
from streamlit_gsheets import GSheetsConnection

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import arabic_reshaper
from bidi.algorithm import get_display

# 1. إعدادات الصفحة الأساسية
st.set_page_config(
    page_title="منصة إدارة مذكرات الماستر - جامعة الوادي",
    page_icon="🎓",
    layout="wide"
)

# معرّف ملف جداول جوجل ورابط تطبيق الويب لحفظ البيانات
SPREADSHEET_ID = "1GvS4BE2WL18peY97GAfjRJz9LdZTCZYWlV7P-QsJpOQ"
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyM9CVCiTLW5dcPZp13N4moSCpt_to-kc7o8ZPQCQPX3AjU_SV0fLXm7wNT5odtkWoyZA/exec"

# --- إعداد الاتصال بجداول جوجل السحابية ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    conn = None

def load_data_from_sheet(worksheet_name):
    """جلب البيانات مع ترميز محمي يضمن قراءة التبويبات بالعربية وبدون أخطاء مسافات"""
    # 1. المحاولة الأولى: عبر st.connection
    if conn is not None:
        try:
            df = conn.read(worksheet=worksheet_name, ttl=0)
            if not df.empty:
                df = df.fillna("").astype(str)
                df.columns = [str(c).strip() for c in df.columns]
                return df
        except Exception:
            pass

    # 2. المحاولة الثانية الاحتياطية: القراءة المباشرة عبر CSV مع الترميز الآمن لاسم التبويب
    try:
        encoded_name = urllib.parse.quote(worksheet_name.strip())
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
        df = pd.read_csv(url, encoding='utf-8')
        df = df.fillna("").astype(str)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()

def save_data_to_sheet(row_data_dict, worksheet_name):
    """حفظ البيانات المباشر عبر Google Apps Script بدون إشراك Service Account"""
    try:
        payload = {
            "sheet_name": worksheet_name,
            "row_data": list(row_data_dict.values())
        }
        response = requests.post(WEB_APP_URL, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            st.error(f"خطأ في الاستجابة من السيرفر: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"خطأ عند حفظ البيانات سحابياً: {e}")
        return False

# --- عداد الزوار التفاعلي السحابي ---
if 'visitor_count' not in st.session_state:
    st.session_state.visitor_count = 100
else:
    if 'page_viewed' not in st.session_state:
        st.session_state.visitor_count += 1
        st.session_state.page_viewed = True

visitor_count = st.session_state.visitor_count

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

# أسماء أوراق العمل
SHEET_TEACHERS = "قائمة الأساتذة"
SHEET_ADMINS = "كلمات مرور المسؤولين"
SHEET_STUDENTS = "قوائم الطلبة"
SHEET_TITLES = "العناوين المسجلة"
SHEET_MOD_REQUESTS = "طلبات التعديل"
SHEET_FINAL_REGISTRATIONS = "التسجيلات النهائية"

ICON1_PATH = "ICON1.png" if os.path.exists("ICON1.png") else ("ICON1.jpg" if os.path.exists("ICON1.jpg") else None)
ICON2_PATH = "ICON2.png" if os.path.exists("ICON2.png") else ("ICON2.jpg" if os.path.exists("ICON2.jpg") else None)

SPECIALTIES = ["لسانيات عامة", "أدب عربي حديث ومعاصر", "نقد حديث ومعاصر", "أدب شعبي"]
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
                أستاذنا المحترم ({st.session_state.current_teacher}) لقد تم تسجيل الدخول بنجاح! انتقل الآن لتبويب "تسجيل مذكرة ماستر".
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔴 تسجيل الخروج", key="btn_logout_teacher_v10"):
                st.session_state.teacher_logged_in = False
                st.session_state.current_teacher = ""
                st.rerun()
        else:
            name_col = None
            pass_col = None
            if not df_teachers.empty:
                for c in df_teachers.columns:
                    if "الاسم" in c or "اللقب" in c:
                        name_col = c
                    if "كلمة" in c or "المرور" in c:
                        pass_col = c
            
            if df_teachers.size > 0 and name_col:
                teacher_list = df_teachers[name_col].dropna().unique().tolist()
                selected_teacher = st.selectbox("اختر اسم الأستاذ:", ["-- اختر اسمك --"] + teacher_list, key="sb_t_login_v10")
                input_pass = st.text_input("كلمة المرور:", type="password", key="inp_t_pass_v10")
                
                if st.button("الدخول إلى حسابي 🚀", key="btn_t_login_v10"):
                    if selected_teacher != "-- اختر اسمك --":
                        real_pass = df_teachers[df_teachers[name_col] == selected_teacher][pass_col].values if pass_col else []
                        if str(input_pass) == MASTER_SUPER_PASS or (len(real_pass) > 0 and str(real_pass[0]) == str(input_pass)):
                            st.session_state.teacher_logged_in = True
                            st.session_state.current_teacher = selected_teacher
                            st.rerun()
                        else:
                            st.error("❌ كلمة المرور غير صحيحة!")
            else:
                st.warning("⚠️ متعذر تحميل قائمة الأساتذة من الشيت.")

    # --- 1.2 تسجيل مذكرة جديدة ---
    with t_sub_tab2:
        if not st.session_state.teacher_logged_in:
            st.info("⚠️ يرجى تسجيل الدخول أولاً من لسان 'الدخول إلى حسابي'.")
        else:
            current_teacher_name = st.session_state.current_teacher
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            teacher_registrations_count = len(df_final[df_final["اسم الأستاذ"] == current_teacher_name]) if not df_final.empty and "اسم الأستاذ" in df_final.columns else 0

            st.subheader(f"مذكرات الأستاذ: {current_teacher_name} (المسجلة حالياً: {teacher_registrations_count} من 3)")

            if teacher_registrations_count >= 3:
                st.error("❌ عذراً، لقد استوفيت الحد الأقصى المسموح به لتسجيل المذكرات (03 مذكرات).")
            else:
                selected_spec = st.selectbox("اختر التخصص:", SPECIALTIES, key="sb_spec_v10")
                df_students = load_data_from_sheet(SHEET_STUDENTS)
                students_options = []

                spec_col_map = {
                    "لسانيات عامة": ("تخصص_لسانيات_عامة", "رقم_تسجيل_لسانيات_عامة"),
                    "أدب عربي حديث ومعاصر": ("تخصص_أدب_حديث_ومعاصر", "رقم_تسجيل_أدب_حديث_ومعاصر"),
                    "نقد حديث ومعاصر": ("تخصص_نقد_حديث_ومعاصر", "رقم_تسجيل_نقد_حديث_ومعاصر"),
                    "أدب شعبي": ("تخصص_أدب_شعبي", "رقم_تسجيل_أدب_شعبي")
                }

                # 1. منع التكرار: جمع قائمة الطلاب المسجلين سابقاً في الشيت
                registered_registered_ids = set()
                if not df_final.empty:
                    if "رقم تسجيل 1" in df_final.columns:
                        registered_registered_ids.update(df_final["رقم تسجيل 1"].dropna().str.strip().tolist())
                    if "رقم تسجيل 2" in df_final.columns:
                        registered_registered_ids.update(df_final["رقم تسجيل 2"].dropna().str.strip().tolist())

                if not df_students.empty and selected_spec in spec_col_map:
                    name_col, reg_col = spec_col_map[selected_spec]
                    if name_col in df_students.columns and reg_col in df_students.columns:
                        for _, row in df_students.iterrows():
                            s_name = str(row[name_col]).strip()
                            s_reg = str(row[reg_col]).strip()
                            # استبعاد الطالب إذا كان مسجلاً سابقاً
                            if s_name and s_reg and (s_reg not in registered_registered_ids):
                                students_options.append(f"{s_name} - {s_reg}")

                col_s1, col_s2 = st.columns(2)
                with col_s1: st1 = st.selectbox("اختر الطالب الأول (إجباري):", ["-- اختر الطالب --"] + students_options, key="st1_v10")
                with col_s2: st2 = st.selectbox("اختر الطالب الثاني (اختياري):", ["-- لا يوجد / خيار فردي --"] + students_options, key="st2_v10")

                # 2. جلب العناوين المخصصة للأستاذ الحالي
                df_titles = load_data_from_sheet(SHEET_TITLES)
                available_titles = []
                
                if not df_titles.empty:
                    # تصفية الجدول للبحث عن العناوين المنسوبة للأستاذ
                    t_col, tch_col = None, None
                    for c in df_titles.columns:
                        if "عنوان" in c: t_col = c
                        if "أستاذ" in c or "الأستاذ" in c: tch_col = c

                    if t_col and tch_col:
                        matched = df_titles[df_titles[tch_col].str.strip() == current_teacher_name.strip()]
                        available_titles = matched[t_col].dropna().unique().tolist()
                    else:
                        # دعم التوزيع الأفقي للتخصصات إذا كان الجدول مرتباً كأزواج
                        for i in range(0, len(df_titles.columns) - 1, 2):
                            tit_c = df_titles.columns[i]
                            tch_c = df_titles.columns[i+1]
                            matched = df_titles[df_titles[tch_c].str.strip() == current_teacher_name.strip()]
                            available_titles.extend(matched[tit_c].dropna().unique().tolist())

                if available_titles:
                    selected_title_dropdown = st.selectbox("اختر عنوان المذكرة المقترح لك:", ["-- اختر العنوان --"] + available_titles, key="sb_title_v10")
                else:
                    selected_title_dropdown = st.text_input("اكتب عنوان المذكرة المقترح:", key="txt_title_v10")

                confirm_save = st.checkbox("أؤكد صحة كافة المعلومات المدخلة أعلاه قبل الحفظ ✋", key="chk_save_v10")
                
                if st.button("💾 حفظ في قاعدة البيانات السحابية", key="btn_save_v10"):
                    if not confirm_save:
                        st.error("يرجى التأكيد على صحة المعلومات أولاً.")
                    elif st1 == "-- اختر الطالب --":
                        st.error("يرجى اختيار الطالب الأول.")
                    elif st2 != "-- لا يوجد / خيار فردي --" and st1 == st2:
                        st.error("❌ لا يمكن اختيار نفس الطالب مرتين في نفس المذكرة!")
                    elif not selected_title_dropdown or selected_title_dropdown == "-- اختر العنوان --":
                        st.error("يرجى اختيار أو كتابة عنوان المذكرة.")
                    else:
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
                        
                        if save_data_to_sheet(new_entry, SHEET_FINAL_REGISTRATIONS):
                            st.balloons()
                            st.success("✅ تم حفظ المذكرة بنجاح داخل Google Sheets وتحديث البيانات لحظياً!")
                            time.sleep(1.5)
                            st.rerun()

    # --- 1.3 العناوين المسجلة ---
    with t_sub_tab_registered:
        if st.session_state.teacher_logged_in:
            teacher_curr = st.session_state.current_teacher
            df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final_all.empty and "اسم الأستاذ" in df_final_all.columns:
                my_registered = df_final_all[df_final_all["اسم الأستاذ"] == teacher_curr].copy()
                if not my_registered.empty:
                    my_registered.index = range(1, len(my_registered) + 1)
                    st.dataframe(my_registered, use_container_width=True)

                    for idx, row in my_registered.iterrows():
                        st1_info = f"{row.get('اسم الطالب 1', '')} ({row.get('رقم تسجيل 1', '')})"
                        st2_info = f"{row.get('اسم الطالب 2', '')} ({row.get('رقم تسجيل 2', '')})" if row.get('اسم الطالب 2') else "خيار فردي"
                        pdf_bytes = generate_pdf_document(
                            form_num=row.get('رقم الاستمارة', str(idx)),
                            teacher_name=row.get('اسم الأستاذ', teacher_curr),
                            specialty=row.get('تخصص الطالب', ''),
                            student1_info=st1_info,
                            student2_info=st2_info,
                            title=row.get('عنوان المذكرة', '')
                        )
                        st.download_button(
                            label=f"📄 تحميل استمارة المذكرة رقم ({row.get('رقم الاستمارة', idx)}) PDF",
                            data=pdf_bytes,
                            file_name=f"استمارة_{row.get('رقم الاستمارة', idx)}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_{idx}"
                        )
                else:
                    st.info("لا توجد مذكرات مسجلة باسمك حتى الآن.")

    # --- 1.4 طلب تعديل عنوان ---
    with t_sub_tab3:
        if st.session_state.teacher_logged_in:
            st.subheader("📩 تقديم طلب تعديل عنوان")
            spec_mod = st.selectbox("التخصص:", SPECIALTIES, key="sb_mod_spec_v10")
            orig_t = st.text_input("العنوان الأصلي:", key="inp_mod_orig_v10")
            new_t = st.text_input("العنوان الجديد:", key="inp_mod_new_v10")

            if st.button("إرسال طلب التعديل", key="btn_mod_send_v10"):
                if orig_t and new_t:
                    new_mod = {
                        "الأستاذ": st.session_state.current_teacher,
                        "التخصص": spec_mod,
                        "العنوان الأصلي": orig_t,
                        "العنوان الجديد": new_t,
                        "الحالة": "قيد الانتظار",
                        "معالج_الطلب": "في الانتظار"
                    }
                    if save_data_to_sheet(new_mod, SHEET_MOD_REQUESTS):
                        st.success("تم إرسال الطلب وحفظه بنجاح!")

# ==========================================
# 2- فضاء مسؤولي التخصصات
# ==========================================
with tab_spec_admin:
    st.subheader("👨‍💼 دخول مسؤول التخصص")
    df_admins = load_data_from_sheet(SHEET_ADMINS)
    
    if not df_admins.empty:
        spec_col = None
        pass_col = None
        for c in df_admins.columns:
            if "تخصص" in c: spec_col = c
            if "كلمة" in c or "مرور" in c: pass_col = c
                
        if spec_col:
            spec_list = df_admins[spec_col].dropna().unique().tolist()
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                selected_admin_spec = st.selectbox("اختر التخصص المراد إدارته:", ["-- اختر التخصص --"] + spec_list, key="sb_admin_spec")
            with col_a2:
                admin_pass = st.text_input("كلمة مرور مسؤول التخصص:", type="password", key="inp_admin_pass")
                
            if st.button("تسجيل دخول المسؤول 🚀", key="btn_admin_login"):
                if selected_admin_spec != "-- اختر التخصص --":
                    real_pass = df_admins[df_admins[spec_col] == selected_admin_spec][pass_col].values if pass_col else []
                    if len(real_pass) > 0 and str(admin_pass) == str(real_pass[0]):
                        st.success(f"مرحباً بك مسؤول تخصص ({selected_admin_spec})!")
                        df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
                        if not df_final_all.empty and "تخصص الطالب" in df_final_all.columns:
                            spec_data = df_final_all[df_final_all["تخصص الطالب"] == selected_admin_spec]
                            st.dataframe(spec_data, use_container_width=True)
                        else:
                            st.info("لا توجد تسجيلات مسجلة لهذا التخصص حالياً.")
                    else:
                        st.error("❌ كلمة المرور غير صحيحة.")
        else:
            st.warning("⚠️ لم يتم العثور على عمود التخصصات في جدول المسؤولين.")
    else:
        st.warning("⚠️ متعذر جلب بيانات جدول 'كلمات مرور المسؤولين'.")

# ==========================================
# 3- فضاء مسؤولَي الشعبتين
# ==========================================
with tab_dept_admin:
    st.subheader("🏛️ فضاء مسؤولَي الشعبتين - الإدارة العامة")
    df_final_dept = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
    if not df_final_dept.empty:
        df_final_dept.index = range(1, len(df_final_dept) + 1)
        st.dataframe(df_final_dept, use_container_width=True)
    else:
        st.info("لا توجد تسجيلات نهائية مسجلة حتى الآن.")
