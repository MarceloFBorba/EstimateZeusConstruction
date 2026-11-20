import streamlit as st
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image
import pandas as pd
import json
import os
import io
from datetime import datetime


st.set_page_config(
    page_title="Zeus Construction Inc - Create Invoice",
    page_icon="assets/logo_zeus.png" if os.path.exists("assets/logo_zeus.png") else "⚒️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================
#   CSV: Estados e cidades
# =========================
@st.cache_data
def load_us_states_cities(csv_file):
    data = pd.read_csv(csv_file)
    states = sorted([str(s) for s in data["state_id"].dropna().unique()])
    state_city_map = {
        state: sorted(list(set(str(c) for c in data[data["state_id"] == state]["city"].dropna())))
        for state in states
    }
    return state_city_map

us_states_cities = load_us_states_cities("uscities.csv")  # ajuste o caminho se necessário

# =========================
#   Persistência JSON
# =========================
DATA_FILE = "customer_records.json"

def load_records(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def save_records(file_path, records):
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=4, ensure_ascii=False)

customer_records = load_records(DATA_FILE)

# =========================
#   PDF
# =========================
class CustomPDF(FPDF):
    def footer(self):
        self.set_y(-18)
        self.set_fill_color(15, 15, 15)
        self.rect(0, self.get_y(), self.w, 18, style="F")
        self.set_y(-12)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, "COMMERCIAL ROOFING   |   COATINGS   |   RESTORATION   |   TPO   |   EPDM", align="C")
        self.set_text_color(0, 0, 0)


def table_row(pdf, col_widths, values, line_height=10, alignments=None):
    """
    Desenha uma linha de tabela onde uma ou mais colunas podem quebrar linha,
    mantendo TODAS as colunas com a mesma altura (sem desalinhamento).
    Requer fpdf2 (pip install fpdf2).
    """
    if alignments is None:
        alignments = ["C"] * len(values)

    x0 = pdf.get_x()
    y0 = pdf.get_y()

    # Descobrir quantas linhas cada célula precisa
    lines_per_cell = []
    for w, txt in zip(col_widths, values):
        txt = "" if txt is None else str(txt)
        # split_only=True: calcula linhas sem desenhar
        lines = pdf.multi_cell(w, line_height, txt, split_only=True)
        lines_per_cell.append(len(lines) if lines else 1)

    max_lines = max(lines_per_cell)
    row_height = max_lines * line_height

    # Desenhar célula por célula com mesma altura
    x = x0
    for i, (w, txt) in enumerate(zip(col_widths, values)):
        txt = "" if txt is None else str(txt)

        # Borda da célula (altura total da linha)
        pdf.rect(x, y0, w, row_height)

        # Escrever texto
        pdf.set_xy(x, y0)

        if lines_per_cell[i] > 1:
            # célula quebrável (top-aligned)
            pdf.multi_cell(w, line_height, txt, border=0, align="L")
        else:
            # centralizar verticalmente textos curtos
            y_text = y0 + (row_height - line_height) / 2
            pdf.set_xy(x, y_text)
            pdf.cell(w, line_height, txt, border=0, align=alignments[i])

        x += w

    # Próxima linha
    pdf.set_xy(x0, y0 + row_height)


def _first_existing_logo_path():
    logo_candidates = [
        "LogoAtualZ.png",

    ]
    for logo_path in logo_candidates:
        if os.path.exists(logo_path):
            return logo_path
    return None


ICON_SVG_FILES = {
    "pin": os.path.join("assets", "icons", "location.svg"),
    "phone": os.path.join("assets", "icons", "phone.svg"),
    "envelope": os.path.join("assets", "icons", "email.svg"),
    "globe": os.path.join("assets", "icons", "web.svg"),
    "check": os.path.join("assets", "icons", "check.svg"),
    "scope": os.path.join("assets", "icons", "scope.svg"),
    "pricing": os.path.join("assets", "icons", "pricing.svg"),
    "acceptance": os.path.join("assets", "icons", "acceptance.svg"),
}

_icon_svg_cache = {}


def _svg_icon_bytes(kind, color):
    hex_color = "%02X%02X%02X" % color
    cache_key = (kind, hex_color)
    if cache_key not in _icon_svg_cache:
        with open(ICON_SVG_FILES[kind], encoding="utf-8") as f:
            svg = f.read()
        svg = svg.replace("currentColor", f"#{hex_color}")
        _icon_svg_cache[cache_key] = svg.encode("utf-8")
    return io.BytesIO(_icon_svg_cache[cache_key])


def _draw_contact_icon(pdf, kind, x, y, size, color):
    pdf.image(_svg_icon_bytes(kind, color), x=x, y=y, w=size, h=size)


def _fit_text(pdf, text, max_w):
    if pdf.get_string_width(text) <= max_w:
        return text
    ellipsis = "..."
    while text and pdf.get_string_width(text + ellipsis) > max_w:
        text = text[:-1]
    return (text + ellipsis) if text else ellipsis


def _draw_label_value(
    pdf,
    x,
    y,
    label,
    value,
    label_w=34,
    value_w=53,
    label_size=10,
    value_size=10,
    label_color=(20, 20, 20),
    value_color=(20, 20, 20),
    value_bold=False,
):
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B", label_size)
    pdf.set_text_color(*label_color)
    pdf.cell(label_w, 6, label, border=0)
    pdf.set_font("Helvetica", "B" if value_bold else "", value_size)
    pdf.set_text_color(*value_color)
    pdf.cell(value_w, 6, value, border=0)


def generate_pdf(customer_name, address, city, state, zip_code, po_number, items, date, prepared_by="Andre Esprenger"):
    pdf = CustomPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)
    pdf.set_font("Helvetica", size=10)

    # Page geometry
    left = 12
    right = 198
    width = right - left
    orange = (245, 99, 23)

    # Header: logo + company contacts, split into two equal columns, vertically centered
    header_half = width / 2
    divider_x = left + header_half
    header_top = 6
    header_bottom = 53
    header_span = header_bottom - header_top

    logo_w = 46
    logo_path = _first_existing_logo_path()
    if logo_path:
        with Image.open(logo_path) as logo_im:
            logo_iw, logo_ih = logo_im.size
        logo_h = logo_w * logo_ih / logo_iw
        logo_x = left + (header_half - logo_w) / 2
        logo_y = header_top + (header_span - logo_h) / 2
        pdf.image(logo_path, x=logo_x, y=logo_y, w=logo_w)

    right_col_x = divider_x + 8
    pdf.set_draw_color(*orange)
    pdf.set_line_width(0.4)
    pdf.line(divider_x, 4, divider_x, header_bottom)
    pdf.set_line_width(0.2)

    title_h = 8.5
    line_h = 5.3
    icon_size = 4.2
    icon_gap = 2.2
    text_x = right_col_x + icon_size + icon_gap

    contact_block_h = title_h + (2 * line_h) + (3 * line_h)
    contact_y = header_top + (header_span - contact_block_h) / 2
    pdf.set_xy(right_col_x, contact_y)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*orange)
    pdf.cell(0, title_h, "ZEUS CONSTRUCTION INC.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 11)

    row_y = contact_y + title_h
    _draw_contact_icon(pdf, "pin", right_col_x, row_y + (2 * line_h - icon_size) / 2, icon_size, orange)
    pdf.set_xy(text_x, row_y)
    pdf.multi_cell(0, line_h, "6145 Broadway Suite 45\nDenver, CO 80216")

    row_y += 2 * line_h
    _draw_contact_icon(pdf, "phone", right_col_x, row_y + (line_h - icon_size) / 2, icon_size, orange)
    pdf.set_xy(text_x, row_y)
    pdf.cell(0, line_h, "720 316-5616", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    row_y += line_h
    _draw_contact_icon(pdf, "envelope", right_col_x, row_y + (line_h - icon_size) / 2, icon_size, orange)
    pdf.set_xy(text_x, row_y)
    pdf.cell(0, line_h, "andre@zeusconstructioninc.com", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    row_y += line_h
    _draw_contact_icon(pdf, "globe", right_col_x, row_y + (line_h - icon_size) / 2, icon_size, orange)
    pdf.set_xy(text_x, row_y)
    pdf.cell(0, line_h, "zeusconstructioninc.com", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_draw_color(*orange)
    pdf.set_line_width(1.2)
    pdf.line(left, 55, right, 55)
    pdf.set_line_width(0.2)

    # Title band + proposal metadata
    proposal_no = po_number.strip() if po_number and po_number.strip() else "ZC-2026-001"
    formatted_date = pd.to_datetime(date).strftime("%m/%d/%Y")

    title_size = 14
    title_h = 9
    title_y = 58 + (22 - title_h) / 2
    pdf.set_font("Helvetica", "B", title_size)
    title_w1 = pdf.get_string_width("COMMERCIAL ROOFING")
    title_w2 = pdf.get_string_width(" PROPOSAL")

    pdf.set_xy(left, title_y)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(title_w1, title_h, "COMMERCIAL ROOFING")
    pdf.set_text_color(*orange)
    pdf.cell(title_w2, title_h, " PROPOSAL")

    # Calcula o meio exato da página com base nas margens existentes
    mid_x = (left + right) / 2

    # Desenha a linha divisória no centro exato (mid_x)
    pdf.set_draw_color(*orange)
    pdf.set_line_width(0.3)
    pdf.line(mid_x, 58, mid_x, 80)
    pdf.set_line_width(0.2)

    # Define o início dos textos da direita dando um pequeno espaçamento (ex: 8) após a linha central
    meta_x = mid_x + 8

    _draw_label_value(pdf, meta_x, 60, "PROPOSAL NO.:", proposal_no, label_w=32, value_w=40, label_size=10, value_size=11)
    _draw_label_value(pdf, meta_x, 67, "PROPOSAL DATE:", formatted_date, label_w=32, value_w=40, label_size=10, value_size=11, value_color=orange, value_bold=True)
    _draw_label_value(pdf, meta_x, 74, "PREPARED BY:", prepared_by, label_w=32, value_w=40, label_size=10, value_size=11)

    pdf.set_draw_color(160, 160, 160)
    pdf.set_line_width(0.4)
    pdf.line(left, 85, right, 85)
    pdf.set_line_width(0.2)
    
    # Company and project address block
    row_y = 90
    row_h = 23  # 23 vai exatamente até a linha inferior em 113
    half = width / 2
    pdf.set_draw_color(160, 160, 160)
    pdf.set_line_width(0.4)
    # Usa mid_x para a linha ficar perfeitamente alinhada com a de cima
    pdf.line(mid_x, row_y, mid_x, row_y + row_h)
    pdf.set_line_width(0.2)

    # Títulos das seções (laranja, tamanho 9)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*orange)
    pdf.set_xy(left, row_y + 1)
    pdf.cell(half, 5, "COMPANY", align="L")
    pdf.set_xy(meta_x, row_y + 1)  # Começa em meta_x (mesmo alinhamento de PROPOSAL NO.)
    pdf.cell(right - meta_x, 5, "PROJECT ADDRESS", align="L")

    # Nome da Empresa / Cliente (com quebra automática antes da linha divisória)
    company_w = (mid_x - left) - 4  # Para 4mm antes da linha central
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(15, 15, 15)
    pdf.set_xy(left, row_y + 7)
    # multi_cell quebra a linha sozinho se o nome for grande!
    pdf.multi_cell(company_w, 5.5, customer_name.strip(), align="L")

    # Endereço do Projeto (com quebra automática antes da borda direita)
    address_w = (right - meta_x) - 4
    full_address = f"{address}\n{city} {state} {zip_code}".strip()
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(meta_x, row_y + 7)
    pdf.multi_cell(address_w, 5, full_address, align="L")

    pdf.set_draw_color(160, 160, 160)
    pdf.set_line_width(0.4)
    pdf.line(left, 113, right, 113)
    pdf.set_line_width(0.2)

    # Items table: units / description / price / total, for every item, with a grand total row
    col_units_w = 22
    col_price_w = 32
    col_total_w = 34
    col_desc_w = width - col_units_w - col_price_w - col_total_w
    col_units_x = left
    col_desc_x = left + col_units_w
    col_price_x = col_desc_x + col_desc_w
    col_total_x = col_price_x + col_price_w

    table_items = items if items else [{"description": "RHINO BOND SYSTEM", "units": 0, "price": 0.0}]
    n_items = len(table_items)

    header_h = 8
    total_row_h = 9
    table_y = 118
    scope_lines = 6
    add_lines = 4
    total_blank_lines = scope_lines + add_lines

    # Solve the table row height and the Scope of Work / Additional Pricing line
    # spacing together, so ACCEPTANCE always stays a safe distance above the
    # footer no matter how many items are on the invoice. Blank decorative lines
    # shrink first; the item rows only shrink once those hit their floor.
    ACCEPT_Y_SAFE = 244
    ROW_H_DEFAULT, ROW_H_FLOOR = 8.5, 4.5
    SPACING_DEFAULT, SPACING_FLOOR = 6.5, 3.2
    fixed_overhead = 6 + 5 + 1 + 5 + 6  # gap after table + section leads/trails + gap before ACCEPTANCE
    remaining = (ACCEPT_Y_SAFE - table_y) - (header_h + total_row_h) - fixed_overhead

    row_h = min(ROW_H_DEFAULT, (remaining - total_blank_lines * SPACING_DEFAULT) / n_items)
    if row_h >= ROW_H_FLOOR:
        line_spacing = SPACING_DEFAULT
    else:
        row_h = ROW_H_FLOOR
        line_spacing = max(SPACING_FLOOR, (remaining - n_items * ROW_H_FLOOR) / total_blank_lines)
    row_h = max(ROW_H_FLOOR, row_h)

    table_h = header_h + n_items * row_h + total_row_h
    pdf.set_fill_color(225, 225, 225)
    pdf.rect(left, table_y, width, header_h, style="F")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.set_xy(col_units_x, table_y)
    pdf.cell(col_units_w, header_h, "UNITS", align="C")
    pdf.set_xy(col_desc_x + 3, table_y)
    pdf.cell(col_desc_w - 3, header_h, "DESCRIPTION")
    pdf.set_xy(col_price_x, table_y)
    pdf.cell(col_price_w - 4, header_h, "PRICE", align="R")
    pdf.set_xy(col_total_x, table_y)
    pdf.cell(col_total_w - 4, header_h, "TOTAL", align="R")

    pdf.set_draw_color(225, 225, 225)
    pdf.line(left, table_y + header_h, right, table_y + header_h)

    grand_total = 0.0
    row_top = table_y + header_h
    pdf.set_draw_color(238, 238, 238)
    for idx, table_item in enumerate(table_items):
        desc = str(table_item.get("description", "")).strip() or "-"
        units = float(table_item.get("units", 0) or 0)
        price = float(table_item.get("price", 0) or 0)
        row_total = units * price
        grand_total += row_total

        text_h = min(5.5, row_h - 1)
        text_y = row_top + (row_h - text_h) / 2

        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(20, 20, 20)
        pdf.set_xy(col_units_x, text_y)
        pdf.cell(col_units_w, text_h, f"{units:g}", align="C")
        pdf.set_xy(col_desc_x + 3, text_y)
        pdf.cell(col_desc_w - 5, text_h, _fit_text(pdf, desc, col_desc_w - 7))
        pdf.set_xy(col_price_x, text_y)
        pdf.cell(col_price_w - 4, text_h, f"${price:,.2f}", align="R")
        pdf.set_xy(col_total_x, text_y)
        pdf.cell(col_total_w - 4, text_h, f"${row_total:,.2f}", align="R")

        row_top += row_h
        if idx < n_items - 1:
            pdf.line(left, row_top, right, row_top)

    pdf.set_draw_color(*orange)
    pdf.set_line_width(0.6)
    pdf.line(left, row_top, right, row_top)
    pdf.set_line_width(0.2)

    total_text_h = min(6, total_row_h - 1.5)
    total_text_y = row_top + (total_row_h - total_text_h) / 2
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(20, 20, 20)
    pdf.set_xy(col_price_x, total_text_y)
    pdf.cell(col_price_w - 4, total_text_h, "TOTAL", align="R")
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*orange)
    pdf.set_xy(col_total_x, total_text_y)
    pdf.cell(col_total_w - 4, total_text_h, f"${grand_total:,.2f}", align="R")

    table_bottom = table_y + table_h

    # Scope of Work and Additional Pricing are kept blank for now (row_h / line_spacing
    # were already solved above so this always lands a safe distance above the footer).
    scope_y = table_bottom + 6

    pdf.set_xy(left + 1, scope_y)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(44, 8, "SCOPE OF WORK")
    pdf.set_draw_color(*orange)
    pdf.line(left + 45, scope_y + 4, right, scope_y + 4)
    pdf.set_draw_color(238, 238, 238)
    for i in range(1, scope_lines + 1):
        y = scope_y + 5 + (i * line_spacing)
        pdf.line(left, y, right, y)

    # Additional pricing (kept blank for now)
    add_y = scope_y + 5 + scope_lines * line_spacing + 1
    pdf.set_xy(left + 1, add_y)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(53, 8, "ADDITIONAL PRICING")
    pdf.set_draw_color(*orange)
    pdf.line(left + 56, add_y + 4, right, add_y + 4)
    pdf.set_draw_color(238, 238, 238)
    for i in range(1, add_lines + 1):
        y = add_y + 5 + (i * line_spacing)
        pdf.line(left, y, right, y)

    # Acceptance block
    accept_y = add_y + 5 + add_lines * line_spacing + 6
    pdf.set_xy(left + 1, accept_y)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(36, 8, "ACCEPTANCE")

    pdf.set_font("Helvetica", "I", 9)
    pdf.set_xy(left, accept_y + 8)
    pdf.multi_cell(
        70,
        4,
        "The above scope of work and pricing is accepted. "
        "By signing below, you authorize Zeus "
        "Construction Inc. to proceed with the "
        "work as outlined in this proposal.",
        align='J'
    )

    sign_x = 86
    pdf.set_draw_color(90, 90, 90)
    pdf.line(sign_x, accept_y + 10, sign_x + 45, accept_y + 10)
    pdf.line(sign_x + 50, accept_y + 10, sign_x + 95, accept_y + 10)
    pdf.line(sign_x, accept_y + 24, sign_x + 45, accept_y + 24)
    pdf.line(sign_x + 50, accept_y + 24, sign_x + 95, accept_y + 24)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(sign_x + 7, accept_y + 10)
    pdf.cell(30, 5, "AUTHORIZED SIGNATURE")
    pdf.set_xy(sign_x + 63, accept_y + 10)
    pdf.cell(20, 5, "PRINTED NAME")
    pdf.set_xy(sign_x + 20, accept_y + 24)
    pdf.cell(8, 5, "TITLE")
    pdf.set_xy(sign_x + 69, accept_y + 24)
    pdf.cell(8, 5, "DATE")

    return pdf


# =========================
#   Streamlit UI (Modern Redesign)
# ==# Injeta CSS personalizado para o novo design moderno (Dark Theme)
st.markdown(
    """
    <style>
    /* Fundo da aplicação */
    .stApp {
        background-color: #0E1117 !important;
        color: #F3F4F6 !important;
    }
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 3rem !important;
        max-width: 1350px !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* Cards com bordas arredondadas e sombra suave no tema dark */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #161B26 !important;
        border-radius: 16px !important;
        border: 1px solid #232B3B !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.45) !important;
        padding: 24px !important;
    }

    /* Rótulos (Labels) de todos os campos garantidos em cor clara */
    label, [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span {
        color: #E2E8F0 !important;
        -webkit-text-fill-color: #E2E8F0 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }

    /* Inputs de texto, número e data */
    input, textarea {
        background-color: #0F131D !important;
        color: #F8FAFC !important;
        -webkit-text-fill-color: #F8FAFC !important;
        font-size: 14px !important;
        font-weight: 500 !important;
    }
    .stTextInput input, .stNumberInput input, .stDateInput input {
        background-color: #0F131D !important;
        color: #F8FAFC !important;
        -webkit-text-fill-color: #F8FAFC !important;
        border: 1.2px solid #2D3748 !important;
        border-radius: 8px !important;
    }
    .stTextInput input::placeholder, .stNumberInput input::placeholder {
        color: #64748B !important;
        -webkit-text-fill-color: #64748B !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #FF5A00 !important;
        box-shadow: 0 0 0 2px rgba(255, 90, 0, 0.25) !important;
    }

    /* Controles do stNumberInput (+ / -) */
    .stNumberInput button {
        background-color: #1A202C !important;
        color: #E2E8F0 !important;
        border: 1px solid #2D3748 !important;
    }
    .stNumberInput button:hover {
        background-color: #2D3748 !important;
        color: #FFFFFF !important;
    }

    /* Selectboxes e dropdowns */
    div[data-baseweb="select"],
    div[data-baseweb="select"] > div {
        background-color: #0F131D !important;
        border: 1.2px solid #2D3748 !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="select"] * {
        background-color: transparent !important;
        color: #F8FAFC !important;
        -webkit-text-fill-color: #F8FAFC !important;
    }
    div[data-baseweb="select"][aria-disabled="true"],
    div[data-baseweb="select"][aria-disabled="true"] > div {
        background-color: #141822 !important;
        border-color: #1F2633 !important;
        opacity: 0.65 !important;
        cursor: not-allowed !important;
    }
    div[data-baseweb="select"] svg {
        fill: #94A3B8 !important;
    }
    div[data-baseweb="popover"] {
        background-color: #161B26 !important;
        border: 1px solid #2D3748 !important;
        border-radius: 8px !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5) !important;
    }
    div[data-baseweb="popover"] ul {
        background-color: #161B26 !important;
    }
    div[data-baseweb="popover"] li,
    div[data-baseweb="menu"] li {
        background-color: #161B26 !important;
        color: #F8FAFC !important;
        -webkit-text-fill-color: #F8FAFC !important;
        font-size: 14px !important;
    }
    div[data-baseweb="popover"] li:hover,
    div[data-baseweb="popover"] li[aria-selected="true"],
    div[data-baseweb="menu"] li:hover {
        background-color: #242D3D !important;
        color: #FF5A00 !important;
        -webkit-text-fill-color: #FF5A00 !important;
    }

    /* Datepicker container e calendário popover */
    div[data-baseweb="input"] {
        background-color: #0F131D !important;
        border: 1.2px solid #2D3748 !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="input"] svg {
        fill: #94A3B8 !important;
    }
    div[data-baseweb="calendar"],
    div[data-baseweb="calendar"] * {
        background-color: #161B26 !important;
        color: #F8FAFC !important;
    }
    div[data-baseweb="calendar"] [aria-selected="true"] {
        background-color: #FF5A00 !important;
        color: #FFFFFF !important;
    }

    /* Botão "+ Add Item" verde vibrante */
    div:has(.add-btn-marker) + div button,
    div[data-testid="element-container"]:has(.add-btn-marker) + div[data-testid="element-container"] button,
    div[data-testid="stColumn"]:has(.items-card-marker) div:has(.add-btn-marker) + div button,
    .add-item-box button {
        background-color: #16A34A !important;
        border: 1.5px solid #22C55E !important;
        border-radius: 8px !important;
        padding: 8px 22px !important;
        box-shadow: 0 2px 10px rgba(34, 197, 94, 0.35) !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
    }
    div:has(.add-btn-marker) + div button *,
    div[data-testid="element-container"]:has(.add-btn-marker) + div[data-testid="element-container"] button *,
    .add-item-box button * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 14px !important;
    }
    div:has(.add-btn-marker) + div button:hover,
    div[data-testid="element-container"]:has(.add-btn-marker) + div[data-testid="element-container"] button:hover,
    .add-item-box button:hover {
        background-color: #15803D !important;
        border-color: #16A34A !important;
        box-shadow: 0 4px 16px rgba(34, 197, 94, 0.55) !important;
        transform: translateY(-1px) !important;
    }
    div:has(.add-btn-marker) + div button:active,
    div[data-testid="element-container"]:has(.add-btn-marker) + div[data-testid="element-container"] button:active {
        transform: translateY(0px) !important;
    }

    /* Botão "Generate Invoice" VERDE vibrante */
    div:has(.gen-invoice-marker) + div button,
    div[data-testid="element-container"]:has(.gen-invoice-marker) + div[data-testid="element-container"] button {
        background-color: #16A34A !important;
        border: 1.5px solid #22C55E !important;
        border-radius: 8px !important;
        padding: 14px 24px !important;
        box-shadow: 0 4px 14px rgba(22, 163, 74, 0.35) !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
    }
    div:has(.gen-invoice-marker) + div button *,
    div[data-testid="element-container"]:has(.gen-invoice-marker) + div[data-testid="element-container"] button * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 15px !important;
    }
    div:has(.gen-invoice-marker) + div button:hover,
    div[data-testid="element-container"]:has(.gen-invoice-marker) + div[data-testid="element-container"] button:hover {
        background-color: #15803D !important;
        border-color: #16A34A !important;
        box-shadow: 0 6px 20px rgba(22, 163, 74, 0.55) !important;
        transform: translateY(-1px) !important;
    }
    div:has(.gen-invoice-marker) + div button:active,
    div[data-testid="element-container"]:has(.gen-invoice-marker) + div[data-testid="element-container"] button:active {
        transform: translateY(0px) !important;
    }

    /* Botão "Download Invoice" LARANJA Zeus vibrante */
    div[data-testid="stDownloadButton"] > button {
        background-color: #FF5A00 !important;
        border: 1.5px solid #FF7A29 !important;
        border-radius: 8px !important;
        padding: 14px 28px !important;
        box-shadow: 0 4px 16px rgba(255, 90, 0, 0.45) !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
    }
    div[data-testid="stDownloadButton"] > button * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-size: 16px !important;
        font-weight: 800 !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #E04E00 !important;
        border-color: #FF5A00 !important;
        box-shadow: 0 6px 22px rgba(255, 90, 0, 0.6) !important;
        transform: translateY(-1px) !important;
    }
    div[data-testid="stDownloadButton"] > button:active {
        transform: translateY(0px) !important;
    }

    /* Botões de exclusão (lixeira) em VERMELHO vibrante (específico para col_del) */
    div:has(.del-btn-marker) + div button,
    div[data-testid="element-container"]:has(.del-btn-marker) + div[data-testid="element-container"] button,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(5) button {
        background-color: #DC2626 !important;
        border: 1.5px solid #EF4444 !important;
        border-radius: 8px !important;
        padding: 4px 8px !important;
        min-height: 38px !important;
        width: 100% !important;
        box-shadow: 0 2px 8px rgba(220, 38, 38, 0.35) !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
    }
    div:has(.del-btn-marker) + div button *,
    div[data-testid="element-container"]:has(.del-btn-marker) + div[data-testid="element-container"] button *,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(5) button * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-size: 16px !important;
    }
    div:has(.del-btn-marker) + div button:hover,
    div[data-testid="element-container"]:has(.del-btn-marker) + div[data-testid="element-container"] button:hover,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(5) button:hover {
        background-color: #B91C1C !important;
        border-color: #DC2626 !important;
        box-shadow: 0 4px 14px rgba(220, 38, 38, 0.55) !important;
        transform: translateY(-1px) !important;
    }
    div:has(.del-btn-marker) + div button:active,
    div[data-testid="element-container"]:has(.del-btn-marker) + div[data-testid="element-container"] button:active {
        transform: translateY(0px) !important;
    }

    /* Badge de Total de cada linha */
    .item-total-badge {
        font-weight: 700;
        font-size: 15px;
        color: #F3F4F6 !important;
        text-align: right;
        padding-top: 6px;
    }

    /* ========================================================= */
    /*   SISTEMA DE DESIGN RESPONSIVO (Desktop, Tablet, Mobile)  */
    /* ========================================================= */

    /* Layout fluído global */
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 3rem !important;
        max-width: 1400px !important;
        width: 100% !important;
    }

    /* Imagens e banners sempre fluidos */
    img {
        max-width: 100% !important;
        height: auto !important;
        border-radius: 10px !important;
    }

    /* --------------------------------------------------------- */
    /* TABLETS E TELAS MÉDIAS (<= 992px)                        */
    /* --------------------------------------------------------- */
    @media (max-width: 992px) {
        .block-container {
            padding-top: 0.6rem !important;
            padding-bottom: 2.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }

        /* Os 2 cards principais (Customer e Items) empilham verticalmente ocupando 100% da tela */
        div[data-testid="stHorizontalBlock"]:has(.customer-card-marker),
        div[data-testid="stHorizontalBlock"]:has(.items-card-marker) {
            flex-direction: column !important;
            gap: 20px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.customer-card-marker) > div[data-testid="stColumn"],
        div[data-testid="stHorizontalBlock"]:has(.items-card-marker) > div[data-testid="stColumn"] {
            width: 100% !important;
            min-width: 100% !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 20px !important;
        }
    }

    /* --------------------------------------------------------- */
    /* CELULARES E TELAS PEQUENAS (<= 640px)                    */
    /* --------------------------------------------------------- */
    @media (max-width: 640px) {
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            padding-top: 0.4rem !important;
            padding-bottom: 2rem !important;
        }

        /* Cards mais compactos e arredondados no celular */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 16px 12px !important;
            border-radius: 12px !important;
        }

        /* Header da página empilha no celular: Título no topo, Load Record embaixo */
        div[data-testid="stHorizontalBlock"]:has(.header-title-box) {
            flex-direction: column !important;
            gap: 10px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.header-title-box) > div[data-testid="stColumn"] {
            width: 100% !important;
            min-width: 100% !important;
        }
        .header-title-box h1 {
            font-size: 21px !important;
        }
        .header-title-box {
            margin: 4px 0 6px 0 !important;
        }

        /* Formulário do Cliente: cada campo ocupa 100% de largura no celular para digitação fácil */
        div[data-testid="stColumn"]:has(.customer-card-marker) div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: 12px !important;
        }
        div[data-testid="stColumn"]:has(.customer-card-marker) div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            width: 100% !important;
            min-width: 100% !important;
        }

        /* Tabela de Itens no celular: mantém 1 única linha horizontal sem quebrar verticalmente */
        div[data-testid="stColumn"]:has(.items-card-marker) div[data-testid="stHorizontalBlock"]:has(.delete-item-box) {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            gap: 4px !important;
        }
        div[data-testid="stColumn"]:has(.items-card-marker) div[data-testid="stHorizontalBlock"]:has(.delete-item-box) > div[data-testid="stColumn"] {
            min-width: 0 !important;
        }

        /* No celular, remove os botões +/- do number_input para abrir o teclado numérico nativo e economizar largura */
        div[data-testid="stColumn"]:has(.items-card-marker) div[data-testid="stNumberInput"] button {
            display: none !important;
        }
        div[data-testid="stColumn"]:has(.items-card-marker) div[data-testid="stNumberInput"] input {
            padding: 6px 2px !important;
            text-align: center !important;
            font-size: 13px !important;
        }
        div[data-testid="stColumn"]:has(.items-card-marker) div[data-testid="stTextInput"] input {
            padding: 6px 6px !important;
            font-size: 13px !important;
        }

        /* Cabeçalho da tabela de itens no celular */
        .items-table-header {
            font-size: 10px !important;
            letter-spacing: 0.2px !important;
            gap: 4px !important;
        }

        /* Badge do Total da linha */
        .item-total-badge {
            font-size: 12px !important;
            padding-top: 4px !important;
        }

        /* Botão de deletar item no celular */
        div:has(.del-btn-marker) + div button,
        div[data-testid="element-container"]:has(.del-btn-marker) + div[data-testid="element-container"] button,
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(5) button {
            min-height: 34px !important;
            padding: 2px 4px !important;
        }

        /* Botão Add Item ocupa largura total no celular */
        div:has(.add-btn-marker) + div button,
        div[data-testid="element-container"]:has(.add-btn-marker) + div[data-testid="element-container"] button,
        .add-item-box button {
            width: 100% !important;
            padding: 10px !important;
            justify-content: center !important;
        }

        /* Total footer no celular */
        .total-summary-box {
            margin-top: 16px !important;
            padding-top: 12px !important;
        }
        .total-summary-box .total-label {
            font-size: 16px !important;
        }
        .total-summary-box .total-amount {
            font-size: 22px !important;
        }

        /* Botões de Ação no celular */
        div:has(> button[key="btn_gen_invoice"]) > button {
            padding: 14px 16px !important;
            font-size: 14px !important;
        }
        div[data-testid="stDownloadButton"] > button {
            padding: 14px 16px !important;
            font-size: 15px !important;
        }
    }

    /* --------------------------------------------------------- */
    /* TELAS MUITO PEQUENAS (<= 380px)                          */
    /* --------------------------------------------------------- */
    @media (max-width: 380px) {
        div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 12px 8px !important;
        }
        .items-table-header {
            font-size: 9px !important;
        }
        .item-total-badge {
            font-size: 11px !important;
        }
        .total-summary-box .total-amount {
            font-size: 20px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 1. Top Banner (Zeus Header)
if os.path.exists("assets/header_banner.png"):
    st.image("assets/header_banner.png", use_container_width=True)

# 2. Page Header (Ícone + Título + Seletor de registros anteriores)
header_col1, header_col2 = st.columns([2.5, 1.2], vertical_alignment="center")

with header_col1:
    st.markdown(
        """
        <div class="header-title-box" style="display: flex; align-items: center; gap: 16px; margin: 12px 0 16px 0;">
            <div style="width: 48px; height: 48px; border-radius: 12px; background: rgba(255, 90, 0, 0.15); border: 2px solid #FF5A00; display: flex; align-items: center; justify-content: center;">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#FF5A00" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
            </div>
            <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #F9FAFB; letter-spacing: -0.5px;">Create Invoice</h1>
                
        </div>
        """,
        unsafe_allow_html=True,
    )
with header_col2:
    selected_record = st.selectbox(
        "📂 Load Previous Record",
        options=["Select a record"] + [f"{rec.get('customer_name','')} - {rec.get('date','')}" for rec in customer_records],
        index=0,
        help="Escolha um orçamento anterior para preencher os campos automaticamente",
    )

# Inicialização e carregamento de estado
if "items_list" not in st.session_state:
    st.session_state.items_list = [
        {"units": 0.0, "description": "", "price": 0.0},
    ]

if "loaded_record_choice" not in st.session_state:
    st.session_state.loaded_record_choice = "Select a record"

# Atualiza campos se o usuário selecionou um registro
selected_data = None
if selected_record != st.session_state.loaded_record_choice:
    st.session_state.loaded_record_choice = selected_record
    if selected_record != "Select a record":
        selected_index = next(
            idx for idx, rec in enumerate(customer_records)
            if f"{rec.get('customer_name','')} - {rec.get('date','')}" == selected_record
        )
        selected_data = customer_records[selected_index]
        st.session_state["cust_name_val"] = selected_data.get("customer_name", "")
        st.session_state["phone_val"] = selected_data.get("phone", "")
        st.session_state["po_val"] = selected_data.get("po_number", "")
        st.session_state["address_val"] = selected_data.get("address", "")
        st.session_state["state_val"] = selected_data.get("state", "")
        st.session_state["city_val"] = selected_data.get("city", "")
        st.session_state["zip_val"] = selected_data.get("zip_code", "")
        st.session_state["prep_by_val"] = selected_data.get("prepared_by", "")
        if selected_data.get("items"):
            st.session_state.items_list = [
                {
                    "units": float(it.get("units", 0.0)),
                    "description": str(it.get("description", "")),
                    "price": float(it.get("price", 0.0)),
                }
                for it in selected_data["items"]
            ]
        try:
            st.session_state["date_val"] = pd.to_datetime(selected_data.get("date")).date()
        except Exception:
            st.session_state["date_val"] = datetime.today().date()
        st.rerun()

# 3. Dois Cards Lado a Lado (Customer Information + Items)
col_customer, col_items = st.columns([1, 1], gap="medium")

# -----------------
# Card Esquerdo: Customer Information
# -----------------
with col_customer:
    with st.container(border=True):
        st.markdown(
            """
            <span class="customer-card-marker" style="display:none;"></span>
            <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
                <div style="width: 42px; height: 42px; min-width: 42px; border-radius: 50%; background: #FF5A00; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(255,90,0,0.25);">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                </div>
                <div>
                    <h3 style="margin: 0; font-size: 18px; font-weight: 700; color: #F9FAFB;">Customer Information</h3>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            customer_name = st.text_input(
                "Customer Name *",
                value=st.session_state.get("cust_name_val", ""),
                placeholder="Enter customer name",
            )
        with r1_c2:
            phone = st.text_input(
                "Phone *",
                value=st.session_state.get("phone_val", ""),
                placeholder="(000) 000-0001",
            )

        # Linha 2: State e City (selecionados primeiro)
        r2_c1, r2_c2 = st.columns(2)
        with r2_c1:
            state_options = [""] + list(us_states_cities.keys())
            saved_state = st.session_state.get("state_val", "")
            state_idx = state_options.index(saved_state) if saved_state in state_options else 0
            state = st.selectbox(
                "State *",
                options=state_options,
                index=state_idx,
                help="Select state first",
            )
            # Se o usuário mudar o estado, atualiza a sessão e reseta a cidade
            if state != st.session_state.get("state_val", ""):
                st.session_state["state_val"] = state
                st.session_state["city_val"] = ""

        with r2_c2:
            # Cidades filtradas pelo estado selecionado
            cities_for_state = us_states_cities.get(state, []) if state else []
            cities_list = [""] + cities_for_state
            saved_city = st.session_state.get("city_val", "")
            city_idx = cities_list.index(saved_city) if saved_city in cities_list else 0
            city = st.selectbox(
                "City *",
                options=cities_list,
                index=city_idx,
                disabled=(not state),
                help="Select a State first to view cities" if not state else f"{len(cities_for_state)} cities available",
            )
            st.session_state["city_val"] = city

        # Linha 3: Address e Zip Code
        r3_c1, r3_c2 = st.columns(2)
        with r3_c1:
            address = st.text_input(
                "Address *",
                value=st.session_state.get("address_val", ""),
                placeholder="Enter address",
            )
        with r3_c2:
            zip_code = st.text_input(
                "Zip Code *",
                value=st.session_state.get("zip_val", ""),
                placeholder="Enter zip code",
            )

        r4_c1, r4_c2 = st.columns(2)
        with r4_c1:
            date = st.date_input(
                "Proposal Date *",
                value=st.session_state.get("date_val", datetime.today().date()),
                format="MM/DD/YYYY",
            )
        with r4_c2:
            prepared_by = st.text_input(
                "Prepared By *",
                value=st.session_state.get("prep_by_val", ""),
                placeholder="Enter preparer's name",
            )

        # PO# / Proposal No. opcional
        po_number = st.text_input(
            "Proposal No. (PO#)",
            value=st.session_state.get("po_val", ""),
            placeholder="Enter proposal number",
            help="Enter proposal number",
        )

# -----------------
# Card Direito: Items
# -----------------
with col_items:
    with st.container(border=True):
        st.markdown(
            """
            <span class="items-card-marker" style="display:none;"></span>
            <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
                <div style="width: 42px; height: 42px; min-width: 42px; border-radius: 50%; background: #FF5A00; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(255,90,0,0.25);">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                        <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                        <line x1="12" y1="22.08" x2="12" y2="12"></line>
                    </svg>
                </div>
                <div>
                    <h3 style="margin: 0; font-size: 18px; font-weight: 700; color: #F9FAFB;">Items</h3>                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Cabeçalho da tabela de itens
        st.markdown(
            """
            <div class="items-table-header" style="display: flex; font-size: 12px; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; padding: 0 4px;">
                <div style="flex: 1.5;">Units</div>
                <div style="flex: 4.2; padding-left: 6px;">Description</div>
                <div style="flex: 2.0; padding-left: 6px;">Price</div>
                <div style="flex: 1.8; text-align: right; padding-right: 4px;">Total</div>
                <div style="flex: 0.7;"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Renderização das linhas de itens
        to_delete = None
        for i in range(len(st.session_state.items_list)):
            item = st.session_state.items_list[i]
            col_u, col_d, col_p, col_t, col_del = st.columns([1.5, 4.2, 2.0, 1.8, 0.7], vertical_alignment="center")
            
            with col_u:
                item["units"] = st.number_input(
                    "Units",
                    min_value=0.0,
                    step=1.0,
                    value=float(item.get("units", 1.0)),
                    format="%.2f",
                    key=f"item_units_{i}",
                    label_visibility="collapsed",
                )
            with col_d:
                item["description"] = st.text_input(
                    "Description",
                    value=str(item.get("description", "")),
                    placeholder="Item description",
                    key=f"item_desc_{i}",
                    label_visibility="collapsed",
                )
            with col_p:
                item["price"] = st.number_input(
                    "Price",
                    min_value=0.0,
                    step=1.0,
                    value=float(item.get("price", 0.0)),
                    format="%.2f",
                    key=f"item_price_{i}",
                    label_visibility="collapsed",
                )
            with col_t:
                row_tot = item["units"] * item["price"]
                st.markdown(f"<div class='item-total-badge'>${row_tot:,.2f}</div>", unsafe_allow_html=True)
            with col_del:
                st.markdown('<div class="del-btn-marker" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("🗑️", key=f"del_item_{i}", help="Remove this item"):
                    to_delete = i

        if to_delete is not None:
            st.session_state.items_list.pop(to_delete)
            st.rerun()

        # Botão "+ Add Item" verde
        st.markdown('<div class="add-btn-marker" style="display:none;"></div>', unsafe_allow_html=True)
        if st.button("＋ Add Item", key="btn_add_item"):
            st.session_state.items_list.append({"units": 0.0, "description": "", "price": 0.0})
            st.rerun()

        # Cálculo de Total (sem Tax)
        grand_total = sum(item["units"] * item["price"] for item in st.session_state.items_list)

        st.markdown(
            f"""
            <div class="total-summary-box" style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #232B3B;">
                <div style="display: flex; justify-content: flex-end; align-items: baseline; gap: 24px;">
                    <span class="total-label" style="font-size: 18px; font-weight: 700; color: #F9FAFB;">Total</span>
                    <span class="total-amount" style="font-size: 28px; font-weight: 800; color: #FF5A00; min-width: 90px; text-align: right;">${grand_total:,.2f}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")

        # Botão de Gerar Invoice (Verde)
        st.markdown('<div class="gen-invoice-marker" style="display:none;"></div>', unsafe_allow_html=True)
        if st.button("📄 Generate Invoice", key="btn_gen_invoice", use_container_width=True):
            if customer_name and address and city and state and zip_code:
                valid_items = [
                    it for it in st.session_state.items_list
                    if it.get("description", "").strip() or it.get("units", 0) > 0
                ]
                if not valid_items:
                    valid_items = [{"description": "Roofing Services", "units": 1.0, "price": grand_total}]

                customer_info = {
                    "customer_name": customer_name.strip(),
                    "phone": phone.strip(),
                    "po_number": po_number.strip(),
                    "address": address.strip(),
                    "city": city.strip(),
                    "state": state.strip(),
                    "zip_code": zip_code.strip(),
                    "date": str(date),
                    "prepared_by": prepared_by.strip(),
                    "items": valid_items,
                }
                customer_records.append(customer_info)
                save_records(DATA_FILE, customer_records)

                final_po = po_number.strip() if po_number and po_number.strip() else "0000001"
                final_prep = prepared_by.strip() if prepared_by and prepared_by.strip() else "Andre Esprenger"
                pdf = generate_pdf(
                    customer_name=customer_name.strip(),
                    address=address.strip(),
                    city=city.strip(),
                    state=state.strip(),
                    zip_code=zip_code.strip(),
                    po_number=final_po,
                    items=valid_items,
                    date=date,
                    prepared_by=final_prep,
                )
                st.session_state["generated_pdf_bytes"] = bytes(pdf.output())
                clean_name = "".join(c for c in customer_name if c.isalnum() or c in (" ", "_")).strip().replace(" ", "_")
                st.session_state["pdf_filename"] = f"Invoice_{clean_name}_{final_po}.pdf"
                st.success("Invoice generated successfully!")
            else:
                st.warning("Please fill in all required customer fields (*).")

        # Botão de Download Invoice (aparece assim que gerado)
        if st.session_state.get("generated_pdf_bytes"):
            st.download_button(
                label="📥 Download Invoice",
                data=st.session_state["generated_pdf_bytes"],
                file_name=st.session_state.get("pdf_filename", "Invoice.pdf"),
                mime="application/pdf",
                key="btn_download_invoice",
                use_container_width=True,
            )
