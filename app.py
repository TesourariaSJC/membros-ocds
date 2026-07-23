import os
import io
import base64
import urllib.request
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, inspect, text, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ReportLab para geração de PDF A4 em Python puro
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

# Configuração da página
st.set_page_config(page_title="Gestão OCDS — Província São José", layout="wide", page_icon="📜")

# Lista de UFs do Brasil
UFS_BRASIL = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO"
]

# Regionais Oficiais
REGIONAIS_OCDS = [
    "Regional São João da Cruz",
    "Regional Santa Teresinha do Menino Jesus e da Santa Face"
]

# Tipos de Agrupamento
TIPOS_COMUNIDADE = [
    "Comunidade com Ereção Canônica",
    "Comunidade sem Ereção Canônica",
    "Grupo",
    "Grupo Vocacionado",
    "Grupo Aspirante"
]

# --- BANCO DE DADOS ---
db_url = None
if "DATABASE_URL" in st.secrets:
    db_url = st.secrets["DATABASE_URL"]
else:
    db_url = os.environ.get("DATABASE_URL", "sqlite:///ocds_membros.db")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

@st.cache_resource
def get_engine(url):
    return create_engine(url, pool_pre_ping=True)

try:
    engine = get_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

    # --- MODELO COMUNIDADE / GRUPO ---
    class Comunidade(Base):
        __tablename__ = "comunidades"

        id = Column(Integer, primary_key=True)
        nome = Column(String(200), nullable=False)
        cidade = Column(String(150))
        uf = Column(String(10))
        regional = Column(String(150))
        tipo_grupo = Column(String(100)) # Ereção Canônica, sem Ereção, Grupo, Vocacionado, Aspirante
        
        data_criacao = Column(String(30))
        data_aceite_provisorio = Column(String(30))
        data_aceite_definitivo = Column(String(30))
        data_erecao_canonica = Column(String(30))

        # Dados do Conselho Local
        trienio = Column(String(50)) # MM/AAAA a MM/AAAA
        presidente_nome = Column(String(200))
        presidente_tel = Column(String(50))
        presidente_email = Column(String(150))

        formador_nome = Column(String(200))
        formador_tel = Column(String(50))
        formador_email = Column(String(150))

        conselheiro_1 = Column(String(200))
        conselheiro_2 = Column(String(200))
        conselheiro_3 = Column(String(200))
        secretario_nome = Column(String(200))
        tesoureiro_nome = Column(String(200))

        observacoes = Column(Text)

    # --- MODELO MEMBRO ---
    class Membro(Base):
        __tablename__ = "membros"

        id = Column(Integer, primary_key=True)
        nome = Column(String(200), nullable=False)
        nome_religioso = Column(String(200))
        data_nascimento = Column(String(30))
        rg = Column(String(30))
        cpf = Column(String(40))
        estado_civil = Column(String(50))
        conjuge = Column(String(200))
        endereco = Column(String(250))
        bairro = Column(String(150))
        cidade = Column(String(150))
        uf = Column(String(10))
        comunidade = Column(String(150))
        regional = Column(String(150))

        data_entrada = Column(String(30))
        data_admissao = Column(String(30))
        quem_realizou_admissao = Column(String(200))
        data_promessas_temp = Column(String(30))
        quem_realizou_promessas_temp = Column(String(200))
        data_promessas_def = Column(String(30))
        quem_realizou_promessas_def = Column(String(200))
        data_votos = Column(String(30))
        quem_realizou_votos = Column(String(200))
        data_sanatio = Column(String(30))

        afastamentos = relationship("Afastamento", back_populates="membro", cascade="all, delete-orphan")

    class Afastamento(Base):
        __tablename__ = "afastamentos"

        id = Column(Integer, primary_key=True)
        membro_id = Column(Integer, ForeignKey("membros.id"), nullable=False)
        data_afastamento = Column(String(30))
        motivo = Column(Text)
        data_retorno = Column(String(30))

        membro = relationship("Membro", back_populates="afastamentos")

    def atualizar_tabelas_banco():
        Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)
        if inspector.has_table("membros"):
            colunas_membros = [c['name'] for c in inspector.get_columns("membros")]
            novas = {
                "comunidade": "VARCHAR(150)", "regional": "VARCHAR(150)", "uf": "VARCHAR(10)",
                "data_entrada": "VARCHAR(30)",
                "data_admissao": "VARCHAR(30)", "quem_realizou_admissao": "VARCHAR(200)",
                "data_promessas_temp": "VARCHAR(30)", "quem_realizou_promessas_temp": "VARCHAR(200)",
                "data_promessas_def": "VARCHAR(30)", "quem_realizou_promessas_def": "VARCHAR(200)",
                "data_votos": "VARCHAR(30)", "quem_realizou_votos": "VARCHAR(200)", "data_sanatio": "VARCHAR(30)"
            }
            with engine.connect() as conn:
                for col, tipo in novas.items():
                    if col not in colunas_membros:
                        try:
                            conn.execute(text(f"ALTER TABLE membros ADD COLUMN {col} {tipo};"))
                            conn.commit()
                        except Exception:
                            pass

    atualizar_tabelas_banco()

except Exception as e:
    st.error(f"Erro ao conectar com o banco de dados: {e}")
    st.stop()

def get_db():
    return SessionLocal()

# --- CARREGAMENTO GARANTIDO DO BRASÃO ORIGINAL DA OCDS ---
URL_BRASAO_ORIGINAL = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Coat_of_arms_of_Carmelites.svg/500px-Coat_of_arms_of_Carmelites.svg.png"

@st.cache_data
def get_brasao_b64():
    try:
        req = urllib.request.Request(URL_BRASAO_ORIGINAL, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            img_bytes = response.read()
            return base64.b64encode(img_bytes).decode('utf-8')
    except Exception:
        return None

# --- USUÁRIOS DO SISTEMA ---
if "usuarios_db" not in st.session_state:
    st.session_state["usuarios_db"] = {
        "admin": {"senha": "admin123", "nome": "Administrador", "role": "adm"},
        "inclusao": {"senha": "inc123", "nome": "Operador (Inclusão)", "role": "inclusao"},
        "leitor": {"senha": "vis123", "nome": "Usuário (Visualização)", "role": "visualizacao"}
    }

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_nome" not in st.session_state:
    st.session_state["usuario_nome"] = ""
if "usuario_role" not in st.session_state:
    st.session_state["usuario_role"] = ""

# --- CABEÇALHO PERSONALIZADO ---
def render_header():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&display=swap');
            .header-title {
                font-family: 'Cinzel', serif;
                color: #4A2C11;
                font-size: 26px;
                font-weight: 700;
                margin-bottom: -5px;
                line-height: 1.2;
            }
            .header-subtitle {
                font-family: 'Cinzel', serif;
                color: #7A4B1E;
                font-size: 18px;
                font-weight: 600;
                margin-top: 0px;
                margin-bottom: 10px;
            }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 5])
    with col1:
        b64_logo = get_brasao_b64()
        if b64_logo:
            st.markdown(f'<img src="data:image/png;base64,{b64_logo}" width="110">', unsafe_allow_html=True)
        else:
            st.write("✝️ **OCDS**")
    with col2:
        st.markdown('<div class="header-title">Ordem dos Carmelitas Descalços Seculares</div>', unsafe_allow_html=True)
        st.markdown('<div class="header-subtitle">Província São José</div>', unsafe_allow_html=True)
    st.divider()

# --- FUNÇÕES GERADORAS DE PDF VIA REPORTLAB ---

def get_reportlab_logo_image():
    b64_logo = get_brasao_b64()
    if b64_logo:
        try:
            img_bytes = base64.b64decode(b64_logo)
            img_buffer = io.BytesIO(img_bytes)
            rl_img = RLImage(img_buffer, width=2.2*cm, height=2.2*cm)
            rl_img.hAlign = 'CENTER'
            return rl_img
        except Exception:
            return None
    return None

def gerar_pdf_membro_a4(m):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('T1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=colors.HexColor("#4A2C11"), alignment=1)
    subtitle_style = ParagraphStyle('T2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor("#7A4B1E"), alignment=1)
    section_style = ParagraphStyle('S1', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor("#FFFFFF"), backColor=colors.HexColor("#4A2C11"), spaceBefore=10, spaceAfter=5, borderPadding=4)
    text_bold = ParagraphStyle('TB', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor("#4A2C11"))
    text_normal = ParagraphStyle('TN', fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor("#222222"))

    story = []
    logo = get_reportlab_logo_image()
    if logo:
        story.append(logo)
        story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Ordem dos Carmelitas Descalços Seculares", title_style))
    story.append(Paragraph("Província São José — Ficha Cadastral do Membro", subtitle_style))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("1. DADOS PESSOAIS", section_style))
    data_pessoais = [
        [Paragraph("<b>Nome Completo:</b>", text_bold), Paragraph(m.nome or "-", text_normal), Paragraph("<b>Nome Religioso:</b>", text_bold), Paragraph(m.nome_religioso or "-", text_normal)],
        [Paragraph("<b>Data Nasc.:</b>", text_bold), Paragraph(m.data_nascimento or "-", text_normal), Paragraph("<b>Estado Civil:</b>", text_bold), Paragraph(m.estado_civil or "-", text_normal)],
        [Paragraph("<b>RG:</b>", text_bold), Paragraph(m.rg or "-", text_normal), Paragraph("<b>CPF:</b>", text_bold), Paragraph(m.cpf or "-", text_normal)],
        [Paragraph("<b>Cônjuge:</b>", text_bold), Paragraph(m.conjuge or "-", text_normal), Paragraph("<b>Cidade/UF:</b>", text_bold), Paragraph(f"{m.cidade or '-'} / {m.uf or '-'} ({m.bairro or '-'})", text_normal)],
        [Paragraph("<b>Endereço:</b>", text_bold), Paragraph(m.endereco or "-", text_normal), Paragraph("", text_normal), Paragraph("", text_normal)]
    ]
    t1 = Table(data_pessoais, colWidths=[3*cm, 6*cm, 3*cm, 6*cm])
    t1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FAF8F5")), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2D8CD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(t1)

    story.append(Paragraph("2. VINCULAÇÃO E COMUNIDADE", section_style))
    data_vinc = [
        [Paragraph("<b>Regional:</b>", text_bold), Paragraph(m.regional or "-", text_normal)],
        [Paragraph("<b>Comunidade:</b>", text_bold), Paragraph(m.comunidade or "-", text_normal)]
    ]
    t2 = Table(data_vinc, colWidths=[4*cm, 14*cm])
    t2.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FAF8F5")), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2D8CD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(t2)

    story.append(Paragraph("3. CAMINHADA E ETAPAS OCDS", section_style))
    data_ocds = [
        [Paragraph("<b>Data de Entrada:</b>", text_bold), Paragraph(m.data_entrada or "-", text_normal), Paragraph("<b>Sanatio:</b>", text_bold), Paragraph(m.data_sanatio or "-", text_normal)],
        [Paragraph("<b>Admissão:</b>", text_bold), Paragraph(m.data_admissao or "-", text_normal), Paragraph("<b>Realizada por:</b>", text_bold), Paragraph(m.quem_realizou_admissao or "-", text_normal)],
        [Paragraph("<b>Promessas Temp.:</b>", text_bold), Paragraph(m.data_promessas_temp or "-", text_normal), Paragraph("<b>Realizada por:</b>", text_bold), Paragraph(m.quem_realizou_promessas_temp or "-", text_normal)],
        [Paragraph("<b>Promessas Def.:</b>", text_bold), Paragraph(m.data_promessas_def or "-", text_normal), Paragraph("<b>Realizada por:</b>", text_bold), Paragraph(m.quem_realizou_promessas_def or "-", text_normal)],
        [Paragraph("<b>Votos:</b>", text_bold), Paragraph(m.data_votos or "-", text_normal), Paragraph("<b>Realizada por:</b>", text_bold), Paragraph(m.quem_realizou_votos or "-", text_normal)]
    ]
    t3 = Table(data_ocds, colWidths=[3.5*cm, 5.5*cm, 3.5*cm, 5.5*cm])
    t3.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FAF8F5")), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2D8CD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(t3)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def gerar_pdf_comunidade_a4(c, membros_comunidade):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('T1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.HexColor("#4A2C11"), alignment=1)
    subtitle_style = ParagraphStyle('T2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor("#7A4B1E"), alignment=1)
    section_style = ParagraphStyle('S1', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor("#FFFFFF"), backColor=colors.HexColor("#4A2C11"), spaceBefore=8, spaceAfter=4, borderPadding=3)
    text_bold = ParagraphStyle('TB', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.HexColor("#4A2C11"))
    text_normal = ParagraphStyle('TN', fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor("#222222"))

    story = []
    logo = get_reportlab_logo_image()
    if logo:
        story.append(logo)
        story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Ordem dos Carmelitas Descalços Seculares", title_style))
    story.append(Paragraph(f"Ficha Cadastral da Comunidade / Grupo: {c.nome}", subtitle_style))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("1. DADOS GERAIS E HISTÓRICO", section_style))
    d_geral = [
        [Paragraph("<b>Nome:</b>", text_bold), Paragraph(c.nome or "-", text_normal), Paragraph("<b>Classificação:</b>", text_bold), Paragraph(c.tipo_grupo or "-", text_normal)],
        [Paragraph("<b>Cidade/UF:</b>", text_bold), Paragraph(f"{c.cidade or '-'} / {c.uf or '-'}", text_normal), Paragraph("<b>Regional:</b>", text_bold), Paragraph(c.regional or "-", text_normal)],
        [Paragraph("<b>Data Criação:</b>", text_bold), Paragraph(c.data_criacao or "-", text_normal), Paragraph("<b>Aceite Provisório:</b>", text_bold), Paragraph(c.data_aceite_provisorio or "-", text_normal)],
        [Paragraph("<b>Aceite Definitivo:</b>", text_bold), Paragraph(c.data_aceite_definitivo or "-", text_normal), Paragraph("<b>Ereção Canônica:</b>", text_bold), Paragraph(c.data_erecao_canonica or "-", text_normal)]
    ]
    t1 = Table(d_geral, colWidths=[3.5*cm, 5.5*cm, 3.5*cm, 5.5*cm])
    t1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FAF8F5")), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2D8CD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(t1)

    story.append(Paragraph("2. CONSELHO LOCAL", section_style))
    d_cons = [
        [Paragraph("<b>Triênio Vigente:</b>", text_bold), Paragraph(c.trienio or "-", text_normal), Paragraph("", text_bold), Paragraph("", text_normal)],
        [Paragraph("<b>Presidente:</b>", text_bold), Paragraph(f"{c.presidente_nome or '-'} (Tel: {c.presidente_tel or '-'} | Email: {c.presidente_email or '-'})", text_normal), Paragraph("", text_bold), Paragraph("", text_normal)],
        [Paragraph("<b>Formador(a):</b>", text_bold), Paragraph(f"{c.formador_nome or '-'} (Tel: {c.formador_tel or '-'} | Email: {c.formador_email or '-'})", text_normal), Paragraph("", text_bold), Paragraph("", text_normal)],
        [Paragraph("<b>Conselheiro 1:</b>", text_bold), Paragraph(c.conselheiro_1 or "-", text_normal), Paragraph("<b>Conselheiro 2:</b>", text_bold), Paragraph(c.conselheiro_2 or "-", text_normal)],
        [Paragraph("<b>Conselheiro 3:</b>", text_bold), Paragraph(c.conselheiro_3 or "-", text_normal), Paragraph("<b>Secretário(a):</b>", text_bold), Paragraph(c.secretario_nome or "-", text_normal)],
        [Paragraph("<b>Tesoureiro(a):</b>", text_bold), Paragraph(c.tesoureiro_nome or "-", text_normal), Paragraph("", text_bold), Paragraph("", text_normal)]
    ]
    t2 = Table(d_cons, colWidths=[3.5*cm, 5.5*cm, 3.5*cm, 5.5*cm])
    t2.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FAF8F5")), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2D8CD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(t2)

    if c.observacoes:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(f"<b>Observações:</b> {c.observacoes}", text_normal))

    story.append(Paragraph(f"3. MEMBROS VINCULADOS ({len(membros_comunidade)} Registrados)", section_style))
    t_membros_data = [[Paragraph("<b>Nome Completo</b>", text_bold), Paragraph("<b>Nome Religioso</b>", text_bold), Paragraph("<b>Admissão</b>", text_bold), Paragraph("<b>Prom. Def.</b>", text_bold)]]
    for mb in membros_comunidade:
        t_membros_data.append([
            Paragraph(mb.nome or "-", text_normal),
            Paragraph(mb.nome_religioso or "-", text_normal),
            Paragraph(mb.data_admissao or "-", text_normal),
            Paragraph(mb.data_promessas_def or "-", text_normal)
        ])
    t3 = Table(t_membros_data, colWidths=[6*cm, 5*cm, 3.5*cm, 3.5*cm])
    t3.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EFE8E1")), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2D8CD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3)]))
    story.append(t3)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def gerar_pdf_relatorio_geral_comunidades_a4(comunidades, titulo_relatorio):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('T1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.HexColor("#4A2C11"), alignment=1)
    subtitle_style = ParagraphStyle('T2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor("#7A4B1E"), alignment=1)
    section_style = ParagraphStyle('S1', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor("#FFFFFF"), backColor=colors.HexColor("#4A2C11"), spaceBefore=8, spaceAfter=4, borderPadding=3)
    text_bold = ParagraphStyle('TB', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor("#4A2C11"))
    text_normal = ParagraphStyle('TN', fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor("#222222"))

    story = []
    logo = get_reportlab_logo_image()
    if logo:
        story.append(logo)
        story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Ordem dos Carmelitas Descalços Seculares", title_style))
    story.append(Paragraph(f"Província São José — {titulo_relatorio}", subtitle_style))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph(f"LISTAGEM DAS COMUNIDADES / GRUPOS ({len(comunidades)} Encontrados)", section_style))

    table_data = [[
        Paragraph("<b>Nome da Comunidade</b>", text_bold),
        Paragraph("<b>Cidade/UF</b>", text_bold),
        Paragraph("<b>Regional</b>", text_bold),
        Paragraph("<b>Ereção Canônica</b>", text_bold),
        Paragraph("<b>Presidente</b>", text_bold),
        Paragraph("<b>Contato</b>", text_bold)
    ]]

    for c in comunidades:
        table_data.append([
            Paragraph(c.nome or "-", text_normal),
            Paragraph(f"{c.cidade or '-'}/{c.uf or '-'}", text_normal),
            Paragraph(c.regional or "-", text_normal),
            Paragraph(c.data_erecao_canonica or "-", text_normal),
            Paragraph(c.presidente_nome or "-", text_normal),
            Paragraph(c.presidente_tel or c.presidente_email or "-", text_normal)
        ])

    t = Table(table_data, colWidths=[4.5*cm, 2.5*cm, 3.5*cm, 2.3*cm, 2.7*cm, 2.5*cm])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EFE8E1")), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2D8CD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- TELA DE LOGIN ---
if not st.session_state["autenticado"]:
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        b64_logo = get_brasao_b64()
        if b64_logo:
            st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{b64_logo}" width="120"></div>', unsafe_allow_html=True)
        st.markdown("<h3 style='color: #4A2C11; font-family: serif; text-align: center;'>Ordem dos Carmelitas Descalços Seculares</h3>", unsafe_allow_html=True)
        st.markdown("<h5 style='color: #7A4B1E; font-family: serif; text-align: center; margin-top: -10px;'>Província São José</h5>", unsafe_allow_html=True)
        st.markdown("---")
        st.subheader("🔒 Acesso ao Sistema")
        
        with st.form("login_form"):
            user_input = st.text_input("Usuário")
            pass_input = st.text_input("Senha", type="password")
            btn_login = st.form_submit_button("Entrar no Sistema")

            if btn_login:
                users = st.session_state["usuarios_db"]
                if user_input in users and users[user_input]["senha"] == pass_input:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_nome"] = users[user_input]["nome"]
                    st.session_state["usuario_role"] = users[user_input]["role"]
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    st.stop()

# --- INTERFACE PRINCIPAL ---
render_header()

user_role = st.session_state["usuario_role"]
user_name = st.session_state["usuario_nome"]

st.sidebar.markdown(f"👤 **Usuário:** {user_name}")
st.sidebar.caption(f"Perfil: {user_role.upper()}")

if st.sidebar.button("🚪 Sair / Logout"):
    st.session_state["autenticado"] = False
    st.session_state["usuario_nome"] = ""
    st.session_state["usuario_role"] = ""
    st.rerun()

st.sidebar.divider()

if user_role == "adm":
    opcoes_menu = [
        "📋 Listar Membros",
        "➕ Cadastrar Membro",
        "🏰 Cadastrar / Gerenciar Comunidade ou Grupo",
        "✏️ Editar / Afastamentos / Excluir Membro",
        "📊 Relatórios e Estatísticas",
        "🔐 Gestão e Manutenção"
    ]
elif user_role == "inclusao":
    opcoes_menu = [
        "📋 Listar Membros",
        "➕ Cadastrar Membro",
        "🏰 Cadastrar / Gerenciar Comunidade ou Grupo",
        "📊 Relatórios e Estatísticas"
    ]
else:
    opcoes_menu = [
        "📋 Listar Membros",
        "📊 Relatórios e Estatísticas"
    ]

menu = st.sidebar.radio("📌 Navegação", opcoes_menu)
db = get_db()

# --- OPÇÃO 1: LISTAR MEMBROS ---
if menu == "📋 Listar Membros":
    st.subheader("📋 Membros Cadastrados")
    membros = db.query(Membro).all()
    if membros:
        dados = []
        for m in membros:
            dados.append({
                "ID": m.id,
                "Nome": m.nome,
                "Nome Religioso": m.nome_religioso or "-",
                "UF": m.uf or "-",
                "Comunidade": m.comunidade or "-",
                "Regional": m.regional or "-",
                "Admissão": m.data_admissao or "-",
                "Prom. Temp.": m.data_promessas_temp or "-",
                "Prom. Def.": m.data_promessas_def or "-",
                "Votos": m.data_votos or "-"
            })
        st.dataframe(dados, use_container_width=True)
    else:
        st.info("Nenhum membro cadastrado ainda.")

# --- OPÇÃO 2: CADASTRAR MEMBRO ---
elif menu == "➕ Cadastrar Membro":
    st.subheader("➕ Cadastrar Novo Membro")
    comunidades_db = db.query(Comunidade).all()
    lista_comunidades_nomes = [c.nome for c in comunidades_db] if comunidades_db else ["Alegria da Sagrada Face Itapetininga"]

    with st.form("form_cadastro_membro"):
        st.markdown("### 1. Dados Pessoais")
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome Completo *")
            nome_religioso = st.text_input("Nome Religioso")
            data_nascimento = st.text_input("Data de Nascimento (DD/MM/AAAA)")
            rg = st.text_input("RG")
            cpf = st.text_input("CPF")
            estado_civil = st.text_input("Estado Civil")
        with col2:
            conjuge = st.text_input("Cônjuge")
            endereco = st.text_input("Endereço")
            bairro = st.text_input("Bairro")
            cidade = st.text_input("Cidade")
            uf = st.selectbox("Unidade da Federação (UF)", UFS_BRASIL, index=24)
            comunidade = st.selectbox("Comunidade / Grupo", lista_comunidades_nomes)
            regional = st.selectbox("Regional", REGIONAIS_OCDS)

        st.markdown("### 2. Caminhada na OCDS")
        col_ocds1, col_ocds2 = st.columns(2)
        with col_ocds1:
            data_entrada = st.text_input("Data de Entrada na OCDS")
            data_admissao = st.text_input("Data da Admissão")
            quem_realizou_admissao = st.text_input("Quem realizou a Admissão")
            data_promessas_temp = st.text_input("Data das Promessas Temporárias")
            quem_realizou_promessas_temp = st.text_input("Quem realizou as Promessas Temporárias")
        with col_ocds2:
            data_promessas_def = st.text_input("Data das Promessas Definitivas")
            quem_realizou_promessas_def = st.text_input("Quem realizou as Promessas Definitivas")
            data_votos = st.text_input("Data dos Votos")
            quem_realizou_votos = st.text_input("Quem realizou os Votos")
            data_sanatio = st.text_input("Data da Sanatio")

        submetido = st.form_submit_button("Salvar Membro")
        if submetido:
            if not nome:
                st.error("O campo Nome Completo é obrigatório!")
            else:
                existente = db.query(Membro).filter(func.lower(Membro.nome) == nome.strip().lower()).first()
                if existente:
                    st.warning(f"⚠️ O membro '{nome}' já possui cadastro no banco (ID #{existente.id}).")
                else:
                    novo_membro = Membro(
                        nome=nome.strip(), nome_religioso=nome_religioso, data_nascimento=data_nascimento,
                        rg=rg, cpf=cpf, estado_civil=estado_civil, conjuge=conjuge,
                        endereco=endereco, bairro=bairro, cidade=cidade, uf=uf, comunidade=comunidade,
                        regional=regional, data_entrada=data_entrada,
                        data_admissao=data_admissao, quem_realizou_admissao=quem_realizou_admissao,
                        data_promessas_temp=data_promessas_temp, quem_realizou_promessas_temp=quem_realizou_promessas_temp,
                        data_promessas_def=data_promessas_def, quem_realizou_promessas_def=quem_realizou_promessas_def,
                        data_votos=data_votos, quem_realizou_votos=quem_realizou_votos, data_sanatio=data_sanatio
                    )
                    db.add(novo_membro)
                    db.commit()
                    st.success(f"Membro '{nome}' cadastrado com sucesso!")

# --- OPÇÃO 3: CADASTRO E GESTÃO DE COMUNIDADES / GRUPOS ---
elif menu == "🏰 Cadastrar / Gerenciar Comunidade ou Grupo":
    st.subheader("🏰 Cadastro e Gestão de Comunidades / Grupos")
    
    aba_cad, aba_edit = st.tabs(["➕ Cadastrar Nova Comunidade/Grupo", "✏️ Editar / Excluir Comunidade/Grupo"])

    with aba_cad:
        with st.form("form_nova_comunidade"):
            st.markdown("#### 1. Identificação da Comunidade / Grupo")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                nome_com = st.text_input("Nome da Comunidade ou Grupo *")
                cidade_com = st.text_input("Cidade")
                uf_com = st.selectbox("UF", UFS_BRASIL, index=24)
            with col_c2:
                regional_com = st.selectbox("Regional", REGIONAIS_OCDS)
                tipo_com = st.selectbox("Classificação / Tipo do Agrupamento", TIPOS_COMUNIDADE)

            st.markdown("#### 2. Datas Históricas")
            cd1, cd2 = st.columns(2)
            with cd1:
                dt_criacao = st.text_input("Data de Criação (DD/MM/AAAA)")
                dt_aceite_prov = st.text_input("Data do Aceite Provisório (DD/MM/AAAA)")
            with cd2:
                dt_aceite_def = st.text_input("Data do Aceite Definitivo (DD/MM/AAAA)")
                dt_erecao = st.text_input("Data da Ereção Canônica (DD/MM/AAAA)")

            st.markdown("#### 3. Dados do Conselho Local")
            trienio = st.text_input("Triênio Vigente", placeholder="Ex: 01/2024 a 12/2026")
            
            cp1, cp2, cp3 = st.columns(3)
            with cp1:
                pres_nome = st.text_input("Nome do Presidente")
                pres_tel = st.text_input("Telefone do Presidente")
                pres_email = st.text_input("E-mail do Presidente")
            with cp2:
                form_nome = st.text_input("Nome do Formador(a)")
                form_tel = st.text_input("Telefone do Formador(a)")
                form_email = st.text_input("E-mail do Formador(a)")
            with cp3:
                sec_nome = st.text_input("Nome do Secretário(a)")
                tes_nome = st.text_input("Nome do Tesoureiro(a)")

            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                cons1 = st.text_input("Nome do Conselheiro 1")
            with cc2:
                cons2 = st.text_input("Nome do Conselheiro 2")
            with cc3:
                cons3 = st.text_input("Nome do Conselheiro 3")

            obs_com = st.text_area("Observações Pertinentes")

            btn_salvar_com = st.form_submit_button("Salvar Comunidade / Grupo")

            if btn_salvar_com:
                if not nome_com:
                    st.error("O Nome da Comunidade ou Grupo é obrigatório!")
                else:
                    nova_c = Comunidade(
                        nome=nome_com.strip(), cidade=cidade_com, uf=uf_com, regional=regional_com,
                        tipo_grupo=tipo_com, data_criacao=dt_criacao, data_aceite_provisorio=dt_aceite_prov,
                        data_aceite_definitivo=dt_aceite_def, data_erecao_canonica=dt_erecao,
                        trienio=trienio, presidente_nome=pres_nome, presidente_tel=pres_tel, presidente_email=pres_email,
                        formador_nome=form_nome, formador_tel=form_tel, formador_email=form_email,
                        conselheiro_1=cons1, conselheiro_2=cons2, conselheiro_3=cons3,
                        secretario_nome=sec_nome, tesoureiro_nome=tes_nome, observacoes=obs_com
                    )
                    db.add(nova_c)
                    db.commit()
                    st.success(f"Comunidade/Grupo '{nome_com}' cadastrada com sucesso!")

    with aba_edit:
        comunidades_lista = db.query(Comunidade).all()
        if not comunidades_lista:
            st.info("Nenhuma comunidade cadastrada para edição.")
        else:
            mapa_c = {f"{c.id} - {c.nome} ({c.cidade}/{c.uf})": c.id for c in comunidades_lista}
            com_sel = st.selectbox("Selecione a Comunidade para editar:", list(mapa_c.keys()))
            c_id = mapa_c[com_sel]
            com_obj = db.query(Comunidade).filter(Comunidade.id == c_id).first()

            if com_obj:
                with st.form("form_edit_comunidade"):
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        e_nome = st.text_input("Nome", value=com_obj.nome or "")
                        e_cidade = st.text_input("Cidade", value=com_obj.cidade or "")
                        uf_i = UFS_BRASIL.index(com_obj.uf) if com_obj.uf in UFS_BRASIL else 24
                        e_uf = st.selectbox("UF", UFS_BRASIL, index=uf_i)
                    with col_e2:
                        reg_i = REGIONAIS_OCDS.index(com_obj.regional) if com_obj.regional in REGIONAIS_OCDS else 0
                        e_regional = st.selectbox("Regional", REGIONAIS_OCDS, index=reg_i)
                        tipo_i = TIPOS_COMUNIDADE.index(com_obj.tipo_grupo) if com_obj.tipo_grupo in TIPOS_COMUNIDADE else 0
                        e_tipo = st.selectbox("Classificação", TIPOS_COMUNIDADE, index=tipo_i)

                    c_d1, c_d2 = st.columns(2)
                    with c_d1:
                        e_dt_criacao = st.text_input("Data de Criação", value=com_obj.data_criacao or "")
                        e_dt_prov = st.text_input("Aceite Provisório", value=com_obj.data_aceite_provisorio or "")
                    with c_d2:
                        e_dt_def = st.text_input("Aceite Definitivo", value=com_obj.data_aceite_definitivo or "")
                        e_dt_erecao = st.text_input("Ereção Canônica", value=com_obj.data_erecao_canonica or "")

                    e_trienio = st.text_input("Triênio Vigente", value=com_obj.trienio or "")
                    
                    e_p1, e_p2, e_p3 = st.columns(3)
                    with e_p1:
                        e_pres_n = st.text_input("Presidente Nome", value=com_obj.presidente_nome or "")
                        e_pres_t = st.text_input("Presidente Tel", value=com_obj.presidente_tel or "")
                        e_pres_e = st.text_input("Presidente Email", value=com_obj.presidente_email or "")
                    with e_p2:
                        e_form_n = st.text_input("Formador Nome", value=com_obj.formador_nome or "")
                        e_form_t = st.text_input("Formador Tel", value=com_obj.formador_tel or "")
                        e_form_e = st.text_input("Formador Email", value=com_obj.formador_email or "")
                    with e_p3:
                        e_sec = st.text_input("Secretário Nome", value=com_obj.secretario_nome or "")
                        e_tes = st.text_input("Tesoureiro Nome", value=com_obj.tesoureiro_nome or "")

                    e_c1, e_c2, e_c3 = st.columns(3)
                    with e_c1:
                        e_cons1 = st.text_input("Conselheiro 1", value=com_obj.conselheiro_1 or "")
                    with e_c2:
                        e_cons2 = st.text_input("Conselheiro 2", value=com_obj.conselheiro_2 or "")
                    with e_c3:
                        e_cons3 = st.text_input("Conselheiro 3", value=com_obj.conselheiro_3 or "")

                    e_obs = st.text_area("Observações", value=com_obj.observacoes or "")

                    btn_up_com = st.form_submit_button("Salvar Alterações da Comunidade")

                if btn_up_com:
                    com_obj.nome = e_nome
                    com_obj.cidade = e_cidade
                    com_obj.uf = e_uf
                    com_obj.regional = e_regional
                    com_obj.tipo_grupo = e_tipo
                    com_obj.data_criacao = e_dt_criacao
                    com_obj.data_aceite_provisorio = e_dt_prov
                    com_obj.data_aceite_definitivo = e_dt_def
                    com_obj.data_erecao_canonica = e_dt_erecao
                    com_obj.trienio = e_trienio
                    com_obj.presidente_nome = e_pres_n
                    com_obj.presidente_tel = e_pres_t
                    com_obj.presidente_email = e_pres_e
                    com_obj.formador_nome = e_form_n
                    com_obj.formador_tel = e_form_t
                    com_obj.formador_email = e_form_e
                    com_obj.conselheiro_1 = e_cons1
                    com_obj.conselheiro_2 = e_cons2
                    com_obj.conselheiro_3 = e_cons3
                    com_obj.secretario_nome = e_sec
                    com_obj.tesoureiro_nome = e_tes
                    com_obj.observacoes = e_obs

                    db.commit()
                    st.success("Comunidade atualizada!")
                    st.rerun()

                st.divider()
                if st.button("🗑️ Excluir esta Comunidade", type="primary"):
                    db.delete(com_obj)
                    db.commit()
                    st.warning("Comunidade excluída com sucesso!")
                    st.rerun()

# --- OPÇÃO 4: EDITAR MEMBROS ---
elif menu == "✏️ Editar / Afastamentos / Excluir Membro":
    st.subheader("✏️ Edição Completa de Membros e Afastamentos")
    membros = db.query(Membro).all()
    comunidades_db = db.query(Comunidade).all()
    lista_comunidades_nomes = [c.nome for c in comunidades_db] if comunidades_db else ["Alegria da Sagrada Face Itapetininga"]

    if not membros:
        st.info("Nenhum membro cadastrado.")
    else:
        opcoes_membros = {f"{m.id} - {m.nome}": m.id for m in membros}
        selecionado = st.selectbox("Selecione o membro para editar:", list(opcoes_membros.keys()))
        membro_id = opcoes_membros[selecionado]
        membro = db.query(Membro).filter(Membro.id == membro_id).first()

        if membro:
            tab1, tab2 = st.tabs(["Dados Cadastrais e OCDS", "Afastamentos"])

            with tab1:
                with st.form("form_edicao"):
                    st.markdown("#### 1. Dados Pessoais")
                    c1, c2 = st.columns(2)
                    with c1:
                        nome = st.text_input("Nome", value=membro.nome or "")
                        nome_religioso = st.text_input("Nome Religioso", value=membro.nome_religioso or "")
                        data_nascimento = st.text_input("Data Nasc.", value=membro.data_nascimento or "")
                        rg = st.text_input("RG", value=membro.rg or "")
                        cpf = st.text_input("CPF", value=membro.cpf or "")
                        estado_civil = st.text_input("Estado Civil", value=membro.estado_civil or "")
                    with c2:
                        conjuge = st.text_input("Cônjuge", value=membro.conjuge or "")
                        endereco = st.text_input("Endereço", value=membro.endereco or "")
                        bairro = st.text_input("Bairro", value=membro.bairro or "")
                        cidade = st.text_input("Cidade", value=membro.cidade or "")
                        uf_index = UFS_BRASIL.index(membro.uf) if membro.uf in UFS_BRASIL else 24
                        uf = st.selectbox("Unidade da Federação (UF)", UFS_BRASIL, index=uf_index)
                        
                        com_index = lista_comunidades_nomes.index(membro.comunidade) if membro.comunidade in lista_comunidades_nomes else 0
                        comunidade = st.selectbox("Comunidade / Grupo", lista_comunidades_nomes, index=com_index)
                        
                        reg_index = REGIONAIS_OCDS.index(membro.regional) if membro.regional in REGIONAIS_OCDS else 0
                        regional = st.selectbox("Regional", REGIONAIS_OCDS, index=reg_index)

                    st.markdown("#### 2. Caminhada OCDS")
                    co1, co2 = st.columns(2)
                    with co1:
                        data_entrada = st.text_input("Data de Entrada", value=membro.data_entrada or "")
                        data_admissao = st.text_input("Data Admissão", value=membro.data_admissao or "")
                        quem_realizou_admissao = st.text_input("Quem realizou Admissão", value=membro.quem_realizou_admissao or "")
                        data_promessas_temp = st.text_input("Data Prom. Temp.", value=membro.data_promessas_temp or "")
                        quem_realizou_promessas_temp = st.text_input("Quem realizou Prom. Temp.", value=membro.quem_realizou_promessas_temp or "")
                    with co2:
                        data_promessas_def = st.text_input("Data Prom. Def.", value=membro.data_promessas_def or "")
                        quem_realizou_promessas_def = st.text_input("Quem realizou Prom. Def.", value=membro.quem_realizou_promessas_def or "")
                        data_votos = st.text_input("Data Votos", value=membro.data_votos or "")
                        quem_realizou_votos = st.text_input("Quem realizou Votos", value=membro.quem_realizou_votos or "")
                        data_sanatio = st.text_input("Data Sanatio", value=membro.data_sanatio or "")

                    btn_atualizar = st.form_submit_button("Salvar Alterações do Membro")

                if btn_atualizar:
                    membro.nome = nome
                    membro.nome_religioso = nome_religioso
                    membro.data_nascimento = data_nascimento
                    membro.rg = rg
                    membro.cpf = cpf
                    membro.estado_civil = estado_civil
                    membro.conjuge = conjuge
                    membro.endereco = endereco
                    membro.bairro = bairro
                    membro.cidade = cidade
                    membro.uf = uf
                    membro.comunidade = comunidade
                    membro.regional = regional
                    membro.data_entrada = data_entrada
                    membro.data_admissao = data_admissao
                    membro.quem_realizou_admissao = quem_realizou_admissao
                    membro.data_promessas_temp = data_promessas_temp
                    membro.quem_realizou_promessas_temp = quem_realizou_promessas_temp
                    membro.data_promessas_def = data_promessas_def
                    membro.quem_realizou_promessas_def = quem_realizou_promessas_def
                    membro.data_votos = data_votos
                    membro.quem_realizou_votos = quem_realizou_votos
                    membro.data_sanatio = data_sanatio

                    db.commit()
                    st.success(f"✅ Ficha cadastral de '{membro.nome}' atualizada com sucesso!")
                    st.rerun()

                st.divider()
                if st.button("🗑️ Excluir Definitivamente este Membro", type="primary"):
                    db.delete(membro)
                    db.commit()
                    st.warning("Membro excluído com sucesso!")
                    st.rerun()

            with tab2:
                st.markdown("#### Histórico de Afastamentos")
                afastamentos = db.query(Afastamento).filter(Afastamento.membro_id == membro.id).all()
                if afastamentos:
                    dados_af = []
                    for af in afastamentos:
                        dados_af.append({
                            "Data Afastamento": af.data_afastamento,
                            "Motivo": af.motivo,
                            "Data Retorno": af.data_retorno or "Em afastamento"
                        })
                    st.table(dados_af)
                else:
                    st.info("Nenhum afastamento registrado para este membro.")

                st.markdown("#### Registrar Novo Afastamento")
                with st.form("form_afastamento"):
                    dt_afast = st.text_input("Data do Afastamento")
                    motivo_afast = st.text_area("Motivo do Afastamento")
                    dt_ret = st.text_input("Data de Retorno (opcional)")
                    btn_af = st.form_submit_button("Salvar Afastamento")

                if btn_af:
                    novo_af = Afastamento(
                        membro_id=membro.id,
                        data_afastamento=dt_afast,
                        motivo=motivo_afast,
                        data_retorno=dt_ret
                    )
                    db.add(novo_af)
                    db.commit()
                    st.success("Afastamento registrado!")
                    st.rerun()

# --- OPÇÃO 5: RELATÓRIOS E ESTATÍSTICAS ---
elif menu == "📊 Relatórios e Estatísticas":
    st.subheader("📊 Relatórios e Indicadores OCDS")
    
    tipo_relatorio = st.radio("Selecione o relatório desejado:", [
        "1 - Relatório Individual do Membro", 
        "2 - Relatório Individual de Comunidade e/ou Grupo",
        "3 - Relatório Geral da Comunidade com Ereção Canônica",
        "4 - Relatório Geral das Comunidades sem Ereção Canônica",
        "5 - Relatório Geral dos Grupos",
        "6 - Relatório Geral dos Grupos Vocacionados",
        "7 - Relatório Geral de Grupos Aspirantes",
        "8 - Resumo Numérico / Estatístico (Filtrável)"
    ])

    membros_all = db.query(Membro).all()
    comunidades_all = db.query(Comunidade).all()

    # --- 1. RELATÓRIO INDIVIDUAL DO MEMBRO ---
    if tipo_relatorio == "1 - Relatório Individual do Membro":
        if not membros_all:
            st.info("Sem membros cadastrados para gerar relatório.")
        else:
            opcoes = {f"{m.id} - {m.nome}": m.id for m in membros_all}
            m_id = opcoes[st.selectbox("Escolha o Membro:", list(opcoes.keys()))]
            m = db.query(Membro).filter(Membro.id == m_id).first()

            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"### 📄 Ficha Cadastral: {m.nome}")
            with col_b:
                pdf_data = gerar_pdf_membro_a4(m)
                st.download_button(
                    label="🖨️ Imprimir Ficha A4 (PDF)",
                    data=pdf_data,
                    file_name=f"Ficha_Membro_{m.nome.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )

            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Nome Religioso:** {m.nome_religioso or '-'}")
                st.write(f"**Data de Nascimento:** {m.data_nascimento or '-'}")
                st.write(f"**CPF:** {m.cpf or '-'}")
                st.write(f"**RG:** {m.rg or '-'}")
                st.write(f"**Estado Civil:** {m.estado_civil or '-'}")
                st.write(f"**Cônjuge:** {m.conjuge or '-'}")
                st.write(f"**Endereço:** {m.endereco or '-'}, {m.bairro or '-'}, {m.cidade or '-'} / {m.uf or '-'}")
            with c2:
                st.write(f"**Comunidade:** {m.comunidade or '-'}")
                st.write(f"**Regional:** {m.regional or '-'}")
                st.write(f"**Data de Entrada:** {m.data_entrada or '-'}")
                st.write(f"**Admissão:** {m.data_admissao or '-'} (Por: {m.quem_realizou_admissao or '-'})")
                st.write(f"**Promessas Temp.:** {m.data_promessas_temp or '-'} (Por: {m.quem_realizou_promessas_temp or '-'})")
                st.write(f"**Promessas Def.:** {m.data_promessas_def or '-'} (Por: {m.quem_realizou_promessas_def or '-'})")
                st.write(f"**Votos:** {m.data_votos or '-'} (Por: {m.quem_realizou_votos or '-'})")

    # --- 2. RELATÓRIO INDIVIDUAL DE COMUNIDADE ---
    elif tipo_relatorio == "2 - Relatório Individual de Comunidade e/ou Grupo":
        if not comunidades_all:
            st.info("Nenhuma comunidade cadastrada.")
        else:
            c_opcoes = {f"{c.id} - {c.nome} ({c.cidade}/{c.uf})": c.id for c in comunidades_all}
            c_id = c_opcoes[st.selectbox("Escolha a Comunidade / Grupo:", list(c_opcoes.keys()))]
            com = db.query(Comunidade).filter(Comunidade.id == c_id).first()

            membros_com = db.query(Membro).filter(Membro.comunidade == com.nome).all()

            col_ca, col_cb = st.columns([3, 1])
            with col_ca:
                st.markdown(f"### 🏰 Ficha de Comunidade: {com.nome}")
            with col_cb:
                pdf_com_data = gerar_pdf_comunidade_a4(com, membros_com)
                st.download_button(
                    label="🖨️ Imprimir Ficha Comunidade (PDF)",
                    data=pdf_com_data,
                    file_name=f"Ficha_Comunidade_{com.nome.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )

            st.markdown("---")
            d1, d2 = st.columns(2)
            with d1:
                st.write(f"**Classificação:** {com.tipo_grupo or '-'}")
                st.write(f"**Cidade/UF:** {com.cidade or '-'} / {com.uf or '-'}")
                st.write(f"**Regional:** {com.regional or '-'}")
                st.write(f"**Data Criação:** {com.data_criacao or '-'}")
                st.write(f"**Aceite Provisório:** {com.data_aceite_provisorio or '-'}")
                st.write(f"**Aceite Definitivo:** {com.data_aceite_definitivo or '-'}")
                st.write(f"**Ereção Canônica:** {com.data_erecao_canonica or '-'}")
            with d2:
                st.write(f"**Triênio:** {com.trienio or '-'}")
                st.write(f"**Presidente:** {com.presidente_nome or '-'} (Tel: {com.presidente_tel or '-'} | Email: {com.presidente_email or '-'})")
                st.write(f"**Formador(a):** {com.formador_nome or '-'} (Tel: {com.formador_tel or '-'} | Email: {com.formador_email or '-'})")
                st.write(f"**Conselheiros:** {com.conselheiro_1 or '-'}, {com.conselheiro_2 or '-'}, {com.conselheiro_3 or '-'}")
                st.write(f"**Secretário(a):** {com.secretario_nome or '-'}")
                st.write(f"**Tesoureiro(a):** {com.tesoureiro_nome or '-'}")

            if com.observacoes:
                st.info(f"**Observações:** {com.observacoes}")

            st.markdown(f"#### Membros Vinculados ({len(membros_com)})")
            if membros_com:
                st.dataframe([{"Nome": m.nome, "Nome Religioso": m.nome_religioso or "-", "Admissão": m.data_admissao or "-", "Prom. Def.": m.data_promessas_def or "-"} for m in membros_com], use_container_width=True)
            else:
                st.write("Nenhum membro vinculado a esta comunidade até o momento.")

    # --- 3 A 7. RELATÓRIOS GERAIS DE COMUNIDADES POR TIPO ---
    elif tipo_relatorio in [
        "3 - Relatório Geral da Comunidade com Ereção Canônica",
        "4 - Relatório Geral das Comunidades sem Ereção Canônica",
        "5 - Relatório Geral dos Grupos",
        "6 - Relatório Geral dos Grupos Vocacionados",
        "7 - Relatório Geral de Grupos Aspirantes"
    ]:
        filtro_tipo_map = {
            "3 - Relatório Geral da Comunidade com Ereção Canônica": "Comunidade com Ereção Canônica",
            "4 - Relatório Geral das Comunidades sem Ereção Canônica": "Comunidade sem Ereção Canônica",
            "5 - Relatório Geral dos Grupos": "Grupo",
            "6 - Relatório Geral dos Grupos Vocacionados": "Grupo Vocacionado",
            "7 - Relatório Geral de Grupos Aspirantes": "Grupo Aspirante"
        }
        tipo_alvo = filtro_tipo_map[tipo_relatorio]
        filtradas = [c for c in comunidades_all if c.tipo_grupo == tipo_alvo]

        col_ha, col_hb = st.columns([3, 1])
        with col_ha:
            st.markdown(f"### 📊 {tipo_relatorio.split(' - ')[1]}")
        with col_hb:
            pdf_geral_com_bytes = gerar_pdf_relatorio_geral_comunidades_a4(filtradas, tipo_relatorio.split(' - ')[1])
            st.download_button(
                label="🖨️ Imprimir Relatório Geral (PDF)",
                data=pdf_geral_com_bytes,
                file_name=f"Relatorio_{tipo_alvo.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )

        st.markdown(f"**Total de Agrupamentos Encontrados:** {len(filtradas)}")
        if filtradas:
            dados_t = []
            for c in filtradas:
                dados_t.append({
                    "Nome": c.nome,
                    "Cidade/UF": f"{c.cidade or '-'}/{c.uf or '-'}",
                    "Regional": c.regional or "-",
                    "Ereção Canônica": c.data_erecao_canonica or "-",
                    "Presidente": c.presidente_nome or "-",
                    "Contato Presidente": c.presidente_tel or c.presidente_email or "-"
                })
            st.dataframe(dados_t, use_container_width=True)
        else:
            st.warning(f"Nenhum registro encontrado para '{tipo_alvo}'.")

    # --- 8. RESUMO ESTATÍSTICO GERAL DE MEMBROS ---
    else:
        st.markdown("### 📈 Resumo Estatístico Geral")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            regionais = list(set([m.regional for m in membros_all if m.regional]))
            regionais.insert(0, "Todas as Regionais")
            filtro_reg = st.selectbox("Filtrar por Regional:", regionais)

        with col_f2:
            comunidades = list(set([m.comunidade for m in membros_all if m.comunidade]))
            comunidades.insert(0, "Todas as Comunidades")
            filtro_com = st.selectbox("Filtrar por Comunidade:", comunidades)

        membros_filtrados = membros_all
        if filtro_reg != "Todas as Regionais":
            membros_filtrados = [m for m in membros_filtrados if m.regional == filtro_reg]
        if filtro_com != "Todas as Comunidades":
            membros_filtrados = [m for m in membros_filtrados if m.comunidade == filtro_com]

        tot_admissao = sum(1 for m in membros_filtrados if m.data_admissao and m.data_admissao.strip() != "")
        tot_temp = sum(1 for m in membros_filtrados if m.data_promessas_temp and m.data_promessas_temp.strip() != "")
        tot_def = sum(1 for m in membros_filtrados if m.data_promessas_def and m.data_promessas_def.strip() != "")
        tot_votos = sum(1 for m in membros_filtrados if m.data_votos and m.data_votos.strip() != "")

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Admissões", tot_admissao)
        k2.metric("Promessas Temporárias", tot_temp)
        k3.metric("Promessas Definitivas", tot_def)
        k4.metric("Votos", tot_votos)

        st.markdown("---")
        st.markdown(f"#### Listagem ({len(membros_filtrados)} Registros)")
        dados_resumo = []
        for m in membros_filtrados:
            dados_resumo.append({
                "Nome": m.nome,
                "Regional": m.regional or "-",
                "Comunidade": m.comunidade or "-",
                "UF": m.uf or "-",
                "Admissão": "Sim" if m.data_admissao else "Não",
                "Promessas Temp.": "Sim" if m.data_promessas_temp else "Não",
                "Promessas Def.": "Sim" if m.data_promessas_def else "Não",
                "Votos": "Sim" if m.data_votos else "Não"
            })
        st.dataframe(dados_resumo, use_container_width=True)

# --- OPÇÃO 6: GESTÃO E MANUTENÇÃO (ADM) ---
elif menu == "🔐 Gestão e Manutenção" and user_role == "adm":
    st.subheader("🔐 Gestão de Senhas do Sistema")
    
    users = st.session_state["usuarios_db"]
    usuario_alvo = st.selectbox("Selecione o usuário:", list(users.keys()), format_func=lambda u: f"{u} ({users[u]['nome']})")

    with st.form("form_senha"):
        nova_senha = st.text_input("Nova Senha", type="password")
        confirma_senha = st.text_input("Confirme a Nova Senha", type="password")
        btn_mudar_senha = st.form_submit_button("Atualizar Senha")

        if btn_mudar_senha:
            if not nova_senha:
                st.error("A senha não pode estar em branco.")
            elif nova_senha != confirma_senha:
                st.error("As senhas digitadas não coincidem.")
            else:
                st.session_state["usuarios_db"][usuario_alvo]["senha"] = nova_senha
                st.success(f"Senha do usuário '{usuario_alvo}' atualizada com sucesso!")

db.close()
