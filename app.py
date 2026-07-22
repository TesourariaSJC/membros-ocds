import os
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Configuração da página
st.set_page_config(page_title="Gestão de Membros OCDS", layout="wide")

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

    # Modelos
    class Membro(Base):
        __tablename__ = "membros"

        id = Column(Integer, primary_key=True)
        # Dados Pessoais
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
        comunidade = Column(String(150))
        regional = Column(String(150))

        # Dados da Caminhada OCDS
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

        # Relacionamento com Afastamentos
        afastamentos = relationship("Afastamento", back_populates="membro", cascade="all, delete-orphan")

    class Afastamento(Base):
        __tablename__ = "afastamentos"

        id = Column(Integer, primary_key=True)
        membro_id = Column(Integer, ForeignKey("membros.id"), nullable=False)
        data_afastamento = Column(String(30))
        motivo = Column(Text)
        data_retorno = Column(String(30))

        membro = relationship("Membro", back_populates="afastamentos")

    # Garante que as novas colunas sejam adicionadas se a tabela já existir
    def atualizar_colunas_banco():
        inspector = inspect(engine)
        if inspector.has_table("membros"):
            colunas_existentes = [c['name'] for c in inspector.get_columns("membros")]
            novas_colunas = {
                "comunidade": "VARCHAR(150)",
                "regional": "VARCHAR(150)",
                "data_entrada": "VARCHAR(30)",
                "data_admissao": "VARCHAR(30)",
                "quem_realizou_admissao": "VARCHAR(200)",
                "data_promessas_temp": "VARCHAR(30)",
                "quem_realizou_promessas_temp": "VARCHAR(200)",
                "data_promessas_def": "VARCHAR(30)",
                "quem_realizou_promessas_def": "VARCHAR(200)",
                "data_votos": "VARCHAR(30)",
                "quem_realizou_votos": "VARCHAR(200)",
                "data_sanatio": "VARCHAR(30)"
            }
            with engine.connect() as conn:
                for col, tipo in novas_colunas.items():
                    if col not in colunas_existentes:
                        try:
                            conn.execute(text(f"ALTER TABLE membros ADD COLUMN {col} {tipo};"))
                            conn.commit()
                        except Exception:
                            pass

    Base.metadata.create_all(bind=engine)
    atualizar_colunas_banco()

except Exception as e:
    st.error(f"Erro ao conectar com o banco de dados: {e}")
    st.stop()

def get_db():
    return SessionLocal()

# --- SISTEMA DE LOGIN NATIVO (REQUISITO 1) ---
USUARIOS = {
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

# Tela de Login
if not st.session_state["autenticado"]:
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Coat_of_arms_of_Carmelites.svg/500px-Coat_of_arms_of_Carmelites.svg.png", width=100)
        st.markdown("### Ordem dos Carmelitas Descalços Seculares")
        st.markdown("##### Província São José")
        st.subheader("🔒 Acesso ao Sistema")
        
        with st.form("login_form"):
            user_input = st.text_input("Usuário")
            pass_input = st.text_input("Senha", type="password")
            btn_login = st.form_submit_button("Entrar")

            if btn_login:
                if user_input in USUARIOS and USUARIOS[user_input]["senha"] == pass_input:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_nome"] = USUARIOS[user_input]["nome"]
                    st.session_state["usuario_role"] = USUARIOS[user_input]["role"]
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    st.stop()

# --- CABEÇALHO E BRASÃO DA OCDS (REQUISITO 6) ---
def render_header():
    col1, col2 = st.columns([1, 6])
    with col1:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Coat_of_arms_of_Carmelites.svg/500px-Coat_of_arms_of_Carmelites.svg.png", width=100)
    with col2:
        st.markdown("<h2 style='margin-bottom: 0px;'>Ordem dos Carmelitas Descalços Seculares</h2>", unsafe_allow_html=True)
        st.markdown("<h4 style='color: #666; margin-top: 0px;'>Província São José</h4>", unsafe_allow_html=True)
    st.divider()

render_header()

user_role = st.session_state["usuario_role"]
user_name = st.session_state["usuario_nome"]

# Menu lateral
st.sidebar.write(f"👤 **Usuário:** {user_name}")
st.sidebar.caption(f"Perfil: {user_role.upper()}")

if st.sidebar.button("🚪 Sair / Logout"):
    st.session_state["autenticado"] = False
    st.session_state["usuario_nome"] = ""
    st.session_state["usuario_role"] = ""
    st.rerun()

st.sidebar.divider()

if user_role == "adm":
    opcoes_menu = ["Listar Membros", "Cadastrar Novo", "Editar / Afastamentos / Excluir", "Relatórios"]
elif user_role == "inclusao":
    opcoes_menu = ["Listar Membros", "Cadastrar Novo", "Relatórios"]
else:
    opcoes_menu = ["Listar Membros", "Relatórios"]

menu = st.sidebar.selectbox("Navegação", opcoes_menu)
db = get_db()

# --- OPÇÃO 1: LISTAR ---
if menu == "Listar Membros":
    st.subheader("📋 Membros Cadastrados")
    membros = db.query(Membro).all()
    if membros:
        dados = []
        for m in membros:
            dados.append({
                "ID": m.id,
                "Nome": m.nome,
                "Nome Religioso": m.nome_religioso,
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

# --- OPÇÃO 2: CADASTRAR ---
elif menu == "Cadastrar Novo":
    st.subheader("➕ Cadastrar Novo Membro")
    with st.form("form_cadastro"):
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
            comunidade = st.text_input("Comunidade")
            regional = st.selectbox("Regional", [
                "1 - Regional São João da Cruz",
                "2 - Regional Santa Teresinha do Menino Jesus e da Santa Face"
            ])

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
                novo_membro = Membro(
                    nome=nome, nome_religioso=nome_religioso, data_nascimento=data_nascimento,
                    rg=rg, cpf=cpf, estado_civil=estado_civil, conjuge=conjuge,
                    endereco=endereco, bairro=bairro, cidade=cidade, comunidade=comunidade,
                    regional=regional, data_entrada=data_entrada, data_admissao=data_admissao,
                    quem_realizou_admissao=quem_realizou_admissao, data_promessas_temp=data_promessas_temp,
                    quem_realizou_promessas_temp=quem_realizou_promessas_temp,
                    data_promessas_def=data_promessas_def, quem_realizou_promessas_def=quem_realizou_promessas_def,
                    data_votos=data_votos, quem_realizou_votos=quem_realizou_votos, data_sanatio=data_sanatio
                )
                db.add(novo_membro)
                db.commit()
                st.success(f"Membro '{nome}' cadastrado com sucesso!")

# --- OPÇÃO 3: EDITAR / AFASTAMENTOS / EXCLUIR ---
elif menu == "Editar / Afastamentos / Excluir":
    st.subheader("✏️ Edição e Registro de Afastamentos")
    membros = db.query(Membro).all()
    if not membros:
        st.info("Nenhum membro cadastrado.")
    else:
        opcoes_membros = {f"{m.id} - {m.nome}": m.id for m in membros}
        selecionado = st.selectbox("Selecione o membro:", list(opcoes_membros.keys()))
        membro_id = opcoes_membros[selecionado]
        membro = db.query(Membro).filter(Membro.id == membro_id).first()

        if membro:
            tab1, tab2 = st.tabs(["Dados Cadastrais", "Afastamentos"])

            with tab1:
                with st.form("form_edicao"):
                    st.markdown("#### Dados Pessoais")
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
                        comunidade = st.text_input("Comunidade", value=membro.comunidade or "")
                        regional = st.selectbox("Regional", [
                            "1 - Regional São João da Cruz",
                            "2 - Regional Santa Teresinha do Menino Jesus e da Santa Face"
                        ], index=0 if "São João" in (membro.regional or "") else 1)

                    st.markdown("#### Caminhada OCDS")
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

                    btn_atualizar = st.form_submit_button("Atualizar Dados")

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
                    st.success("Dados do membro atualizados com sucesso!")
                    st.rerun()

                if st.button("🗑️ Excluir Membro", type="primary"):
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

# --- OPÇÃO 4: RELATÓRIOS ---
elif menu == "Relatórios":
    st.subheader("📊 Relatórios e Indicadores OCDS")
    
    tipo_relatorio = st.radio("Selecione o tipo de relatório:", [
        "Relatório Individual do Membro", 
        "Relatório Numérico/Estatístico (Comunidade e Geral)"
    ])

    membros = db.query(Membro).all()

    if tipo_relatorio == "Relatório Individual do Membro":
        if not membros:
            st.info("Sem membros cadastrados para gerar relatório.")
        else:
            opcoes = {f"{m.id} - {m.nome}": m.id for m in membros}
            m_id = opcoes[st.selectbox("Escolha o Membro:", list(opcoes.keys()))]
            m = db.query(Membro).filter(Membro.id == m_id).first()

            st.markdown("---")
            st.markdown(f"### 📄 Ficha Cadastral: {m.nome}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Nome Religioso:** {m.nome_religioso or '-'}")
                st.write(f"**Data de Nascimento:** {m.data_nascimento or '-'}")
                st.write(f"**CPF:** {m.cpf or '-'}")
                st.write(f"**RG:** {m.rg or '-'}")
                st.write(f"**Estado Civil:** {m.estado_civil or '-'}")
                st.write(f"**Cônjuge:** {m.conjuge or '-'}")
                st.write(f"**Endereço:** {m.endereco or '-'}, {m.bairro or '-'}, {m.cidade or '-'}")
            with c2:
                st.write(f"**Comunidade:** {m.comunidade or '-'}")
                st.write(f"**Regional:** {m.regional or '-'}")
                st.write(f"**Data de Entrada:** {m.data_entrada or '-'}")
                st.write(f"**Admissão:** {m.data_admissao or '-'} (Por: {m.quem_realizou_admissao or '-'})")
                st.write(f"**Promessas Temp.:** {m.data_promessas_temp or '-'} (Por: {m.quem_realizou_promessas_temp or '-'})")
                st.write(f"**Promessas Def.:** {m.data_promessas_def or '-'} (Por: {m.quem_realizou_promessas_def or '-'})")
                st.write(f"**Votos:** {m.data_votos or '-'} (Por: {m.quem_realizou_votos or '-'})")
                st.write(f"**Sanatio:** {m.data_sanatio or '-'}")

            st.markdown("#### Histórico de Afastamentos")
            if m.afastamentos:
                for af in m.afastamentos:
                    st.write(f"- **Afastamento:** {af.data_afastamento} | **Retorno:** {af.data_retorno or 'Atual'} | **Motivo:** {af.motivo}")
            else:
                st.write("Nenhum afastamento registrado.")

    else:
        st.markdown("### 📈 Resumo Estatístico da Caminhada")
        
        comunidades = list(set([m.comunidade for m in membros if m.comunidade]))
        comunidades.insert(0, "Todas (Geral)")
        filtro_com = st.selectbox("Filtrar por Comunidade:", comunidades)

        membros_filtrados = membros
        if filtro_com != "Todas (Geral)":
            membros_filtrados = [m for m in membros if m.comunidade == filtro_com]

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
        st.markdown("#### Lista de Membros no Filtro")
        dados_resumo = []
        for m in membros_filtrados:
            dados_resumo.append({
                "Nome": m.nome,
                "Comunidade": m.comunidade or "-",
                "Admissão": "Sim" if m.data_admissao else "Não",
                "Promessas Temp.": "Sim" if m.data_promessas_temp else "Não",
                "Promessas Def.": "Sim" if m.data_promessas_def else "Não",
                "Votos": "Sim" if m.data_votos else "Não"
            })
        st.dataframe(dados_resumo, use_container_width=True)

db.close()
