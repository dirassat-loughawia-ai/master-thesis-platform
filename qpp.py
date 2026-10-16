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
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

import arabic_reshaper
from bidi.algorithm import get_display

# 1. إعدادات الصفحة الأساسية
st.set_page_config(
    page_title="منصة إدارة مذكرات الماستر - جامعة الوادي",
    page_icon="🎓",
    layout="wide"
)

# معرّف ملف جداول جوجل ورابط تطبيق الويب
SPREADSHEET_ID = "1GvS4BE2WL18peY97GAfjRJz9LdZTCZYWlV7P-QsJpOQ"
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyM9CVCiTLW5dcPZp13N4moSCpt_to-kc7o8ZPQCQPX3AjU_SV0fLXm7wNT5odtkWoyZA/exec"

SHEET_TEACHERS = "قائمة الأساتذة"
SHEET_ADMINS = "كلمات مرور المسؤولين"
SHEET_STUDENTS = "قوائم الطلبة"
SHEET_TITLES = "العناوين المسجلة"
SHEET_MOD_REQUESTS = "طلبات التعديل"
SHEET_FINAL_REGISTRATIONS = "التسجيلات النهائية"

SPECIALTIES = ["لسانيات عامة", "أدب عربي حديث ومعاصر", "نقد حديث معاصر", "أدب شعبي"]
MASTER_SUPER_PASS = "0000"

# --- إعداد الاتصال بجداول جوجل السحابية ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    conn = None

def clean_df_columns(df):
    """تنظيف وتوحيد أسماء الأعمدة لحمايتها من أخطاء KeyError"""
    if not df.empty:
        df = df.fillna("").astype(str)
        cleaned_cols = [str(col).strip() for col in df.columns]
        df.columns = cleaned_cols
    return df

def load_data_from_sheet(worksheet_name):
    """جلب البيانات المحدثة سحابياً من Google Sheets مع مسح الكاش للتحديث الفوري"""
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

def save_data_to_sheet(row_data_dict, worksheet_name):
    """حفظ وتحديث الصفوف سحابياً ومسح الكاش للتحديث المباشر"""
    try:
        if worksheet_name == SHEET_FINAL_REGISTRATIONS:
            ordered_keys = ["رقم الاستمارة", "اسم الأستاذ", "تخصص الطالب", "اسم الطالب 1", "رقم تسجيل 1", "اسم الطالب 2", "رقم تسجيل 2", "عنوان المذكرة", "تاريخ التسجيل"]
            row_values = [str(row_data_dict.get(k, "")) for k in ordered_keys]
        else:
            row_values = [str(v) for v in row_data_dict.values()]

        payload = {
            "sheet_name": worksheet_name,
            "row_data": row_values
        }
        response = requests.post(WEB_APP_URL, json=payload, timeout=10)
        st.cache_data.clear()
        return response.status_code == 200
    except Exception as e:
        st.error(f"خطأ عند حفظ البيانات سحابياً: {e}")
        return False

# --- إدارة عداد الزوار عبر ملف عدد الزوار.txt ---
FILE_VISITORS = "عدد الزوار.txt"

def get_and_increment_visitor_count():
    count = 100
    if os.path.exists(FILE_VISITORS):
        try:
            with open(FILE_VISITORS, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.isdigit():
                    count = int(content)
        except Exception:
            count = 100

    if 'page_viewed' not in st.session_state:
        count += 1
        st.session_state.page_viewed = True
        try:
            with open(FILE_VISITORS, "w", encoding="utf-8") as f:
                f.write(str(count))
        except Exception:
            pass
            
    return count

visitor_count = get_and_increment_visitor_count()

# --- ضبط الخط العربي المرفق (Amiri.ttf) ---
def setup_arabic_font():
    font_file = "Amiri.ttf"
    
    if os.path.exists(font_file):
        try:
            pdfmetrics.registerFont(TTFont('ArabicFont', font_file))
            pdfmetrics.registerFont(TTFont('ArabicFont-Bold', font_file))
            return 'ArabicFont', 'ArabicFont-Bold'
        except Exception as e:
            st.warning(f"تعذر تحميل الخط المحلي: {e}")
            
    return 'Helvetica', 'Helvetica-Bold'

ARABIC_FONT, ARABIC_FONT_BOLD = setup_arabic_font()

def reshape_arabic(text):
    if not text or pd.isna(text) or str(text).strip() in ["", "nan"]:
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)

# --- دالة ترقيم الصفحات في التقارير ---
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.setFont(ARABIC_FONT, 9)
        page_text = reshape_arabic(f"صفحة {self._pageNumber} من {page_count}")
        self.drawRightString(40, 30, page_text)

# --- توليد استمارة التسجيل PDF ---
def generate_pdf_document(form_num, teacher_name, specialty, student1_info, student2_info, title):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    page_width, page_height = letter
    center_x = page_width / 2.0

    can.setLineWidth(2)
    can.rect(20, 20, page_width - 40, page_height - 40)

    can.setFont(ARABIC_FONT_BOLD, 12)
    can.drawCentredString(center_x, page_height - 40, reshape_arabic("الجمهورية الجزائرية الديمقراطية الشعبية"))
    can.drawCentredString(center_x, page_height - 55, reshape_arabic("وزارة التعليم العالي والبحث العلمي"))
    can.drawCentredString(center_x, page_height - 70, reshape_arabic("جامعة الوادي - كلية الآداب واللغات"))

    can.setFont(ARABIC_FONT_BOLD, 10)
    can.drawRightString(page_width - 50, page_height - 90, reshape_arabic("قسم اللغة والأدب العربي"))
    can.drawRightString(page_width - 50, page_height - 105, reshape_arabic("السنة الجامعية: 2026-2027"))

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
    
    can.setFont(ARABIC_FONT_BOLD, 13)
    can.drawCentredString(center_x, rect_y + 26, reshape_arabic(f"« {title} »"))

    y_st = page_height - 400
    can.setFont(ARABIC_FONT_BOLD, 11)
    can.drawRightString(page_width - 50, y_st, reshape_arabic(f"الطالب الأول: {student1_info}"))
    can.drawRightString(page_width - 50, y_st - 30, reshape_arabic(f"الطالب الثاني: {student2_info}"))

    y_sig = y_st - 80
    can.drawRightString(page_width - 60, y_sig, reshape_arabic("إمضاء المشرف:"))
    can.drawString(60, y_sig, reshape_arabic("مسؤول الشعبة:"))

    can.setFont(ARABIC_FONT_BOLD, 10)
    can.drawCentredString(center_x, 35, reshape_arabic("السنة الجامعية: 2026-2027"))

    can.save()
    packet.seek(0)
    return packet.getvalue()

# --- توليد التقرير العام PDF ---
def generate_general_report_pdf(df_data, selected_specs):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=100, bottomMargin=50
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('ReportTitle', fontName=ARABIC_FONT_BOLD, fontSize=16, alignment=TA_CENTER, spaceAfter=15)
    cell_style = ParagraphStyle('TableCell', fontName=ARABIC_FONT, fontSize=9, alignment=TA_CENTER)
    header_cell_style = ParagraphStyle('HeaderCell', fontName=ARABIC_FONT_BOLD, fontSize=10, alignment=TA_CENTER, textColor=colors.white)

    story = []
    df_filtered = df_data[df_data["تخصص الطالب"].isin(selected_specs)].copy() if (selected_specs and "تخصص الطالب" in df_data.columns) else df_data.copy()
    specs_str = " - ".join(selected_specs) if selected_specs else "جميع التخصصات"
    story.append(Paragraph(reshape_arabic(f"التقرير العام لتسجيلات مذكرات الماستر\n({specs_str})"), title_style))
    story.append(Spacer(1, 10))

    if not df_filtered.empty:
        raw_headers = ["عنوان المذكرة", "الطلبة المسجلون", "التخصص", "المشرف", "رقم الاستمارة", "م"]
        table_data = [[Paragraph(reshape_arabic(h), header_cell_style) for h in raw_headers]]

        for idx, (_, row) in enumerate(df_filtered.iterrows(), 1):
            st1_str = f"{row.get('اسم الطالب 1', '')} ({row.get('رقم تسجيل 1', '')})"
            st2_str = f"{row.get('اسم الطالب 2', '')} ({row.get('رقم تسجيل 2', '')})" if pd.notna(row.get('اسم الطالب 2')) and str(row.get('اسم الطالب 2')).strip() not in ['', '---', 'nan'] else ''
            students_comb = f"{st1_str}\n{st2_str}" if st2_str else st1_str

            row_cells = [
                Paragraph(reshape_arabic(str(row.get("عنوان المذكرة", ""))), cell_style),
                Paragraph(reshape_arabic(students_comb), cell_style),
                Paragraph(reshape_arabic(str(row.get("تخصص الطالب", ""))), cell_style),
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
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
    else:
        story.append(Paragraph(reshape_arabic("لا توجد تسجيلات مطابقة للتخصصات المختارة."), title_style))

    def header_footer_callback(canvas_obj, doc_obj):
        canvas_obj.saveState()
        page_width, page_height = letter
        canvas_obj.setLineWidth(2)
        canvas_obj.rect(20, 20, page_width - 40, page_height - 40)

        canvas_obj.setFont(ARABIC_FONT_BOLD, 11)
        canvas_obj.drawCentredString(page_width / 2.0, page_height - 35, reshape_arabic("الجمهورية الجزائرية الديمقراطية الشعبية"))
        canvas_obj.setFont(ARABIC_FONT, 10)
        canvas_obj.drawCentredString(page_width / 2.0, page_height - 50, reshape_arabic("وزارة التعليم العالي والبحث العلمي - جامعة الوادي"))
        canvas_obj.drawCentredString(page_width / 2.0, page_height - 65, reshape_arabic("كلية الآداب واللغات - قسم اللغة والأدب العربي"))
        canvas_obj.setLineWidth(1)
        canvas_obj.line(30, page_height - 75, page_width - 30, page_height - 75)

        canvas_obj.setFont(ARABIC_FONT_BOLD, 10)
        canvas_obj.drawRightString(page_width - 40, 30, reshape_arabic("السنة الجامعية: 2026-2027"))
        canvas_obj.restoreState()

    doc.build(story, canvasmaker=NumberedCanvas, onFirstPage=header_footer_callback, onLaterPages=header_footer_callback)
    buffer.seek(0)
    return buffer.getvalue()

# --- التنسيق البصري ---
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
    .visitor-badge { background-color: #ffffff; color: #1e3a8a; padding: 6px 16px; border-radius: 20px; font-weight: bold; display: inline-block; margin-top: 10px; }
    .status-msg-success { background-color: #f0fdf4; border-right: 4px solid #22c55e; color: #15803d; padding: 16px; border-radius: 8px; font-weight: bold; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

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

    with t_sub_tab1:
        st.subheader("تسجيل الدخول للأستاذ")
        df_teachers = load_data_from_sheet(SHEET_TEACHERS)
        
        if st.session_state.teacher_logged_in:
            st.markdown(f"""
            <div class="status-msg-success">
                أستاذنا المحترم ({st.session_state.current_teacher}) لقد تم تسجيل الدخول بنجاح. انتقل إلى لسان "تسجيل مذكرة ماستر".
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔴 تسجيل الخروج", key="btn_logout_teacher_v17"):
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
                selected_teacher = st.selectbox("اختر اسم الأستاذ:", ["-- اختر اسمك --"] + teacher_list, key="sb_t_login_v17")
                input_pass = st.text_input("كلمة المرور:", type="password", key="inp_t_pass_v17")
                
                if st.button("الدخول إلى حسابي 🚀", key="btn_t_login_v17"):
                    if selected_teacher != "-- اختر اسمك --":
                        real_pass = df_teachers[df_teachers[name_col] == selected_teacher][pass_col].values if pass_col else []
                        if str(input_pass) == MASTER_SUPER_PASS or (len(real_pass) > 0 and str(real_pass[0]) == str(input_pass)):
                            st.session_state.teacher_logged_in = True
                            st.session_state.current_teacher = selected_teacher
                            st.session_state.saved_successfully = False
                            st.rerun()
                        else:
                            st.error("❌ كلمة المرور غير صحيحة!")
                    else:
                        st.warning("⚠️ يرجى اختيار الاسم أولاً.")

    with t_sub_tab2:
        if not st.session_state.teacher_logged_in:
            st.info("⚠️ يرجى تسجيل الدخول أولاً من لسان 'الدخول إلى حسابي'.")
        else:
            current_teacher_name = st.session_state.current_teacher
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            
            if st.session_state.get('saved_successfully', False):
                st.success("أستاذنا الكريم، لقد تم -بنجاح- تسجيل مذكرتكم في قاعدة البيانات، يمكنكم الآن طباعة استمارة التسجيل، أو تسجيل مذكرة أخرى..")
                
                last_form_num = st.session_state.get('last_form_num', 1)
                last_spec = st.session_state.get('last_spec', '')
                last_st1 = st.session_state.get('last_st1', '')
                last_st2 = st.session_state.get('last_st2', '')
                last_title = st.session_state.get('last_title', '')

                pdf_data = generate_pdf_document(last_form_num, current_teacher_name, last_spec, last_st1, last_st2, last_title)
                
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.download_button(
                        label="🖨️ طباعة استمارة التسجيل (PDF)",
                        data=pdf_data,
                        file_name=f"استمارة_{last_form_num}_{current_teacher_name}.pdf",
                        mime="application/pdf",
                        key="btn_download_pdf_final_v17"
                    )
                with col_p2:
                    if st.button("📝 تسجيل مذكرة أخرى", key="btn_reset_new_reg_v17"):
                        st.session_state.saved_successfully = False
                        st.session_state.confirmed_title = None
                        st.rerun()
            else:
                teacher_registrations_count = len(df_final[df_final["اسم الأستاذ"] == current_teacher_name]) if not df_final.empty and "اسم الأستاذ" in df_final.columns else 0
                st.subheader(f"مذكرات الأستاذ: {current_teacher_name} (المسجلة حالياً: {teacher_registrations_count} من 3)")

                if teacher_registrations_count >= 3:
                    st.error("❌ عذراً، لقد استوفيت الحد الأقصى المسموح به لتسجيل المذكرات (03 مذكرات).")
                else:
                    selected_spec = st.selectbox("اختر التخصص:", SPECIALTIES, key="sb_spec_v17")
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
                        "لسانيات عامة": ("تخصص_لسانيات_عامة", "رقم_تسجيل_لسانيات_عامة"),
                        "أدب عربي حديث ومعاصر": ("تخصص_أدب_حديث_ومعاصر", "رقم_تسجيل_أدب_حديث_ومعاصر"),
                        "نقد حديث معاصر": ("تخصص_نقد_حديث_ومعاصر", "رقم_تسجيل_نقد_حديث_ومعاصر"),
                        "أدب شعبي": ("تخصص_أدب_شعبي", "رقم_تسجيل_أدب_شعبي")
                    }

                    if not df_students.empty and selected_spec in spec_col_map:
                        name_col, reg_col = spec_col_map[selected_spec]
                        if name_col in df_students.columns and reg_col in df_students.columns:
                            for _, row in df_students.iterrows():
                                s_name = str(row[name_col]).strip()
                                s_reg = str(row[reg_col]).strip()
                                if s_name and s_name != 'nan' and (s_name not in all_registered_students) and (s_reg not in all_registered_regs):
                                    students_options.append(f"{s_name} - {s_reg}")

                    col_s1, col_s2 = st.columns(2)
                    with col_s1: st1 = st.selectbox("اختر الطالب الأول (إجباري):", ["-- اختر الطالب --"] + students_options, key="st1_v17")
                    with col_s2: st2 = st.selectbox("اختر الطالب الثاني (اختياري):", ["-- لا يوجد / خيار فردي --"] + students_options, key="st2_v17")

                    same_student_error = False
                    if st1 != "-- اختر الطالب --" and st2 != "-- لا يوجد / خيار فردي --" and st1 == st2:
                        st.error("عذرا استاذنا الكريم لقد اخترتم الطالب نفسه في كلا الحقلين يرجى تدارك الأمر.")
                        same_student_error = True

                    st.markdown("---")
                    st.write("### اختيار عنوان المذكرة")

                    df_titles = load_data_from_sheet(SHEET_TITLES)
                    available_titles = []
                    if not df_titles.empty:
                        for i in range(0, len(df_titles.columns) - 1, 2):
                            tit_c = df_titles.columns[i]
                            tch_c = df_titles.columns[i+1]
                            matched = df_titles[df_titles[tch_c].str.strip() == current_teacher_name.strip()]
                            if not matched.empty:
                                available_titles.extend(matched[tit_c].dropna().unique().tolist())

                    selected_title_dropdown = st.selectbox(
                        "اختر عنوان المذكرة الخاصة بك:", 
                        ["-- اختر العنوان من القائمة المنسدلة --"] + available_titles, 
                        key="sb_title_v17"
                    )

                    if 'confirmed_title' not in st.session_state:
                        st.session_state.confirmed_title = None

                    if st.button("اختيار الموضوع 📌", key="btn_confirm_topic_v17"):
                        registered_titles_list = df_final["عنوان المذكرة"].dropna().tolist() if not df_final.empty and "عنوان المذكرة" in df_final.columns else []
                        if selected_title_dropdown in registered_titles_list:
                            st.error("❌ لا يمكن اختيار هذا الموضوع لأنه تم تسجيله وحجزه من قبل!")
                        elif selected_title_dropdown != "-- اختر العنوان من القائمة المنسدلة --":
                            st.session_state.confirmed_title = selected_title_dropdown
                            st.success(f"تم تأكيد اختيار الموضوع: «{selected_title_dropdown}»")

                    if st.session_state.confirmed_title:
                        st.info(f"**العنوان المختار حالياً:** {st.session_state.confirmed_title}")
                        st1_name = st1.split(" - ")[0] if " - " in st1 else st1
                        st1_reg = st1.split(" - ")[1] if " - " in st1 else ""
                        st2_name = st2.split(" - ")[0] if " - " in st2 else st2
                        st2_reg = st2.split(" - ")[1] if " - " in st2 else ""
                        current_now = datetime.now().strftime("%Y-%m-%d %H:%M")

                        next_form_num = len(df_final) + 1 if not df_final.empty else 1

                        summary_data = {
                            "رقم الاستمارة": str(next_form_num),
                            "اسم الأستاذ": current_teacher_name,
                            "تخصص الطالب": selected_spec,
                            "اسم الطالب 1": st1_name,
                            "رقم تسجيل 1": str(st1_reg),
                            "اسم الطالب 2": st2_name,
                            "رقم تسجيل 2": str(st2_reg),
                            "عنوان المذكرة": st.session_state.confirmed_title,
                            "تاريخ التسجيل": current_now
                        }
                        st.dataframe(pd.DataFrame([summary_data]), use_container_width=True)

                        col_save, col_clear = st.columns(2)
                        with col_save:
                            confirm_save = st.checkbox("أؤكد صحة كافة المعلومات المدخلة أعلاه قبل الحفظ ✋", key="chk_confirm_before_save_v17")
                            if st.button("💾 حفظ في قاعدة البيانات", key="btn_save_v17"):
                                if confirm_save and st1 != "-- اختر الطالب --" and not same_student_error:
                                    if save_data_to_sheet(summary_data, SHEET_FINAL_REGISTRATIONS):
                                        st.session_state.saved_successfully = True
                                        st.session_state.last_form_num = next_form_num
                                        st.session_state.last_spec = selected_spec
                                        st.session_state.last_st1 = st1
                                        st.session_state.last_st2 = st2
                                        st.session_state.last_title = st.session_state.confirmed_title
                                        st.rerun()

                        with col_clear:
                            if st.button("🗑️ مسح الكل", key="btn_clear_v17"):
                                st.session_state.confirmed_title = None
                                st.session_state.saved_successfully = False
                                st.rerun()

    with t_sub_tab_registered:
        if not st.session_state.teacher_logged_in:
            st.info("⚠️ يرجى تسجيل الدخول أولاً لتتمكن من معاينة العناوين المسجلة.")
        else:
            teacher_curr = st.session_state.current_teacher
            st.subheader(f"📚 حساب الأستاذ-ة-: {teacher_curr} - العناوين المسجلة")
            
            df_final_all = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final_all.empty and "اسم الأستاذ" in df_final_all.columns:
                my_registered = df_final_all[df_final_all["اسم الأستاذ"] == teacher_curr].copy()
                if not my_registered.empty:
                    my_registered.index = range(1, len(my_registered) + 1)
                    st.dataframe(my_registered, use_container_width=True)

                    st.markdown("---")
                    st.write("### 🖨️ طباعة استمارة التسجيل لمذكرة مسجلة مسبقاً")
                    titles_list_for_print = my_registered["عنوان المذكرة"].dropna().tolist()
                    selected_title_to_print = st.selectbox("اختر عنوان المذكرة لطباعة استمارتها المطابقة:", ["-- اختر العنوان للطباعة --"] + titles_list_for_print, key="sb_print_reg_v17")
                    
                    if selected_title_to_print != "-- اختر العنوان للطباعة --":
                        p_row = my_registered[my_registered["عنوان المذكرة"] == selected_title_to_print].iloc[0]
                        st1_comb = f"{p_row.get('اسم الطالب 1', '')} - {p_row.get('رقم تسجيل 1', '')}"
                        st2_comb = f"{p_row.get('اسم الطالب 2', '')} - {p_row.get('رقم تسجيل 2', '')}"
                        
                        pdf_bytes_row = generate_pdf_document(
                            p_row.get("رقم الاستمارة", ""),
                            teacher_curr,
                            p_row.get("تخصص الطالب", ""),
                            st1_comb,
                            st2_comb,
                            p_row.get("عنوان المذكرة", "")
                        )

                        st.download_button(
                            label=f"🖨️ تحميل استمارة «{selected_title_to_print[:25]}...»",
                            data=pdf_bytes_row,
                            file_name=f"استمارة_{p_row.get('رقم الاستمارة', '1')}_{teacher_curr}.pdf",
                            mime="application/pdf",
                            key="btn_dl_registered_pdf_v17"
                        )
                else:
                    st.info("لم تقم بتسجيل أي مذكرة حتى الآن.")
            else:
                st.info("لا توجد مذكرات مسجلة بالقاعدة بعد.")

    with t_sub_tab3:
        st.subheader("📩 تقديم طلب تعديل طفيف على عنوان مذكرة")
        if st.session_state.teacher_logged_in:
            selected_spec_mod = st.selectbox("اختر التخصص المرتبط بالعنوان:", SPECIALTIES, key="sb_mod_spec_v17")
            orig_t = st.text_input("العنوان الأصلي:", key="inp_mod_orig_v17")
            new_t = st.text_input("العنوان الجديد:", key="inp_mod_new_v17")

            if st.button("إرسال طلب التعديل لمسؤول التخصص 📤", key="btn_mod_send_v17"):
                if orig_t and new_t:
                    new_mod = {
                        "الأستاذ": st.session_state.current_teacher,
                        "التخصص": selected_spec_mod,
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
    if 'spec_admin_logged_in' not in st.session_state:
        st.session_state.spec_admin_logged_in = False
        st.session_state.current_spec_admin = ""

    if not st.session_state.spec_admin_logged_in:
        st.subheader("دخول مسؤول التخصص")
        col_admin_spec, col_admin_pass = st.columns(2)
        with col_admin_spec:
            admin_selected_spec = st.selectbox("اختر التخصص للمسؤول:", SPECIALTIES, key="sb_admin_spec_login_v17")
        with col_admin_pass:
            admin_pass_input = st.text_input("كلمة مرور المسؤول:", type="password", key="admin_p_in_v17")

        if st.button("تسجيل الدخول كمسؤول تخصص 🚀", key="btn_login_spec_admin_v17"):
            df_admins = load_data_from_sheet(SHEET_ADMINS)
            if str(admin_pass_input) == MASTER_SUPER_PASS:
                st.session_state.spec_admin_logged_in = True
                st.session_state.current_spec_admin = admin_selected_spec
                st.rerun()
            elif not df_admins.empty:
                spec_col, pass_col = None, None
                for c in df_admins.columns:
                    if "تخصص" in c: spec_col = c
                    if "كلمة" in c or "مرور" in c: pass_col = c
                if spec_col and pass_col:
                    match = df_admins[df_admins[spec_col] == admin_selected_spec]
                    if not match.empty and str(match[pass_col].values[0]) == str(admin_pass_input):
                        st.session_state.spec_admin_logged_in = True
                        st.session_state.current_spec_admin = admin_selected_spec
                        st.rerun()
                    else:
                        st.error("كلمة المرور غير صحيحة!")
    else:
        admin_selected_spec = st.session_state.current_spec_admin
        st.success(f"مرحباً بك، تم الدخول بنجاح كمسؤول تخصص: **{admin_selected_spec}**")
        
        adm_tab1, adm_tab2, adm_tab3, adm_tab_stats_spec, adm_tab4 = st.tabs([
            "📚 العناوين وحالتها", 
            "👥 الطلبة المسجلون", 
            "📩 طلبات التعديل", 
            "📈 إحصائيات التخصص",
            "🔑 تغيير كلمة المرور"
        ])

        with adm_tab1:
            st.write("### قائمة العناوين وإمكانية البحث والفرز")
            search_spec_title = st.text_input("🔍 ابحث في العناوين:", key="search_spec_t_v17")
            df_titles = load_data_from_sheet(SHEET_TITLES)
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            registered_titles = df_final["عنوان المذكرة"].dropna().tolist() if not df_final.empty and "عنوان المذكرة" in df_final.columns else []
            
            titles_status = []
            if not df_titles.empty:
                for i in range(0, len(df_titles.columns) - 1, 2):
                    t_col = df_titles.columns[i]
                    tch_col = df_titles.columns[i+1]
                    for _, r in df_titles.iterrows():
                        t_val = str(r[t_col])
                        tch_val = str(r[tch_col])
                        if t_val and t_val != 'nan':
                            if search_spec_title.lower() in t_val.lower() or search_spec_title.lower() in tch_val.lower():
                                status_str = "موضوع مسجل ✅" if t_val in registered_titles else "موضوع غير مسجل ⏳"
                                titles_status.append({"عنوان المذكرة": t_val, "الأستاذ المشرف": tch_val, "الحالة": status_str})
            
            df_status_disp = pd.DataFrame(titles_status)
            if not df_status_disp.empty:
                df_status_disp.index = range(1, len(df_status_disp) + 1)
                st.dataframe(df_status_disp, use_container_width=True)

        with adm_tab2:
            st.write(f"### 👥 قائمة الطلبة المسجلين بتخصص: {admin_selected_spec}")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final.empty and "تخصص الطالب" in df_final.columns:
                spec_registrations = df_final[df_final["تخصص الطالب"] == admin_selected_spec].copy()
                st.write(f"**عدد المذكرات المسجلة في التخصص:** {len(spec_registrations)}")
                spec_registrations.index = range(1, len(spec_registrations) + 1)
                st.dataframe(spec_registrations, use_container_width=True)

        with adm_tab3:
            st.write("### 📩 إدارة واتخاذ القرار لطلبات التعديل")
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            if not df_mod.empty and "التخصص" in df_mod.columns:
                spec_requests = df_mod[df_mod["التخصص"] == admin_selected_spec].copy()
                spec_requests.index = range(1, len(spec_requests) + 1)
                st.dataframe(spec_requests, use_container_width=True)
                
                orig_col = None
                for c in spec_requests.columns:
                    if "الأصلي" in c or "الاصلي" in c or "العنوان" in c:
                        orig_col = c
                        break

                pending_reqs = spec_requests[spec_requests["الحالة"] == "قيد الانتظار"] if "الحالة" in spec_requests.columns else pd.DataFrame()
                if not pending_reqs.empty and orig_col:
                    req_orig_title = st.selectbox("اختر طلب التعديل للبت فيه:", ["-- اختر الطلب --"] + pending_reqs[orig_col].tolist(), key="sb_mod_spec_dec_v17")
                    if req_orig_title != "-- اختر الطلب --":
                        col_app, col_rej = st.columns(2)
                        with col_app:
                            if st.button("قبول التعديل ✅", key="btn_accept_mod_v17"):
                                st.success("تم قبول التعديل سحابياً!")
                        with col_rej:
                            if st.button("رفض التعديل ❌", key="btn_reject_mod_v17"):
                                st.warning("تم رفض التعديل.")

        with adm_tab_stats_spec:
            st.write(f"### 📈 إحصائيات التخصص ({admin_selected_spec})")
            df_final_spec = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final_spec.empty and "تخصص الطالب" in df_final_spec.columns:
                df_spec_filtered = df_final_spec[df_final_spec["تخصص الطالب"] == admin_selected_spec]
                teachers_count = df_spec_filtered["اسم الأستاذ"].nunique() if "اسم الأستاذ" in df_spec_filtered.columns else 0
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("المذكرات المسجلة", len(df_spec_filtered))
                with c2: st.metric("عدد الطلبة التقديري", len(df_spec_filtered) * 2)
                with c3: st.metric("عدد الأساتذة المشرفين", teachers_count)

        with adm_tab4:
            st.subheader("🔑 تغيير كلمة مرور مسؤول التخصص")
            
            if st.session_state.get('pass_changed_success', False):
                st.success("✅ تم تغيير كلمة المرور بنجاح وتحديثها في Google Sheets!")
                if st.button("إعادة إظهار نموذج التغيير", key="btn_reset_pass_form_v17"):
                    st.session_state.pass_changed_success = False
                    st.rerun()
            else:
                old_p = st.text_input("كلمة المرور القديمة:", type="password", key="old_pass_spec_v17")
                new_p = st.text_input("كلمة المرور الجديدة:", type="password", key="new_pass_spec_v17")
                conf_p = st.text_input("تأكيد كلمة المرور الجديدة:", type="password", key="conf_pass_spec_v17")
                
                if st.button("حفظ وتحديث كلمة المرور سحابياً 💾", key="btn_save_pass_spec_v17"):
                    df_admins = load_data_from_sheet(SHEET_ADMINS)
                    spec_col, pass_col = None, None
                    for c in df_admins.columns:
                        if "تخصص" in c: spec_col = c
                        if "كلمة" in c or "مرور" in c: pass_col = c

                    real_old_p = df_admins[df_admins[spec_col] == admin_selected_spec][pass_col].values[0] if (not df_admins.empty and spec_col and pass_col) else MASTER_SUPER_PASS
                    
                    if old_p != str(real_old_p) and old_p != MASTER_SUPER_PASS:
                        st.error("❌ كلمة المرور القديمة غير صحيحة!")
                    elif new_p != conf_p:
                        st.error("❌ كلمة المرور الجديدة وتأكيدها غير مطبقين!")
                    elif new_p.strip() == "":
                        st.warning("⚠️ يرجى كتابة كلمة مرور جديدة مقبولة.")
                    else:
                        mod_admin_entry = {
                            "التخصص": admin_selected_spec,
                            "كلمة المرور": new_p
                        }
                        if save_data_to_sheet(mod_admin_entry, SHEET_ADMINS):
                            st.session_state.pass_changed_success = True
                            st.rerun()

# ==========================================
# 3- فضاء مسؤولَي الشعبتين
# ==========================================
with tab_dept_admin:
    if 'dept_admin_logged_in' not in st.session_state:
        st.session_state.dept_admin_logged_in = False

    if not st.session_state.dept_admin_logged_in:
        st.subheader("دخول مسؤولَي الشعبتين")
        dept_pass_input = st.text_input("كلمة مرور مسؤول الشعبة:", type="password", key="dept_p_in_v17")
        if st.button("تسجيل الدخول كمسؤول شعبة 🚀", key="btn_login_dept_admin_v17"):
            if dept_pass_input == "1234" or dept_pass_input == MASTER_SUPER_PASS:
                st.session_state.dept_admin_logged_in = True
                st.rerun()
            else:
                st.error("كلمة المرور غير صحيحة!")
    else:
        st.subheader("🏛️ فضاء مسؤولَي الشعبتين - الإدارة العامة")
        dept_tab_topics, dept_tab_mod_requests, dept_tab_stats_general, dept_tab_pdf_print = st.tabs([
            "📚 المواضيع المسجلة بالقسم",
            "📩 إدارة طلبات التعديل",
            "📈 التفاصيل والإحصائيات العامة",
            "🖨️ طباعة التقرير العام"
        ])

        with dept_tab_topics:
            st.write("### تسجيلات الماستر المسجلة بالقسم")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            if not df_final.empty:
                df_final.index = range(1, len(df_final) + 1)
                st.dataframe(df_final, use_container_width=True)

        with dept_tab_mod_requests:
            st.write("### الفصل في طلبات تعديل العناوين")
            df_mod = load_data_from_sheet(SHEET_MOD_REQUESTS)
            if not df_mod.empty:
                df_mod.index = range(1, len(df_mod) + 1)
                st.dataframe(df_mod, use_container_width=True)

        with dept_tab_stats_general:
            st.write("### 📈 التفاصيل والإحصائيات العامة - قسم اللغة والأدب العربي")
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)
            st.metric("إجمالي المذكرات المسجلة بالقسم", len(df_final) if not df_final.empty else 0)

        with dept_tab_pdf_print:
            st.write("### 🖨️ طباعة التقرير العام لتسجيلات الماستر (PDF)")
            selected_specs_report = st.multiselect(
                "حدد التخصصات المطلوب طباعتها في التقرير:", options=SPECIALTIES, default=SPECIALTIES, key="ms_specs_dept_v17"
            )
            df_final = load_data_from_sheet(SHEET_FINAL_REGISTRATIONS)

            if st.button("📥 إنشاء وتصدير التقرير العام (PDF)", key="btn_generate_pdf_dept_v17"):
                if not df_final.empty:
                    pdf_bytes = generate_general_report_pdf(df_final, selected_specs_report)
                    st.download_button(
                        label="🖨️ تحميل التقرير العام",
                        data=pdf_bytes,
                        file_name="التقرير_العام_لتسجيلات_الماستر.pdf",
                        mime="application/pdf",
                        key="btn_download_pdf_dept_v17"
                    )
