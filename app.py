import os
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

# Configuração da página
st.set_page_config(page_title="Gestão de Membros OCDS", layout="wide")

# 1. Recupera a URL do Banco de Dados
db_url = None
if "DATABASE_URL" in st.secrets:
    db_url = st.secrets["DATABASE_URL"]
else:
    db_url = os.environ.get("DATABASE_URL", "sqlite:///ocds_membros.db")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# 2. Conexão com o Banco de Dados (com Cache do Streamlit)
@st.cache_resource
def get_engine(url):
    return create_engine(url, pool_pre_ping=True)

try:
    engine = get_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

    # 3. Modelo Membro
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

    Base.metadata.create_all(bind=engine)

except Exception as e:
    st.error(f"Erro ao conectar com o banco de dados: {e}")
    st.stop()

# Helper para sessão do banco
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        pass

# --- Interface Gráfica ---
st.title("📋 Cadastro e Gestão de Membros")

menu = st.sidebar.selectbox("Navegação", ["Listar Membros", "Cadastrar Novo", "Editar / Excluir"])
db = get_db()

# --- OPÇÃO 1: LISTAR ---
if menu == "Listar Membros":
    st.subheader("Membros Cadastrados")
    membros = db.query(Membro).all()
    if membros:
        dados = []
        for m in membros:
            dados.append({
                "ID": m.id,
                "Nome": m.nome,
                "Nome Religioso": m.nome_religioso,
                "Data Nasc.": m.data_nascimento,
                "CPF": m.cpf,
                "Cidade": m.cidade
            })
        st.dataframe(dados, use_container_width=True)
    else:
        st.info("Nenhum membro cadastrado ainda.")

# --- OPÇÃO 2: CADASTRAR ---
elif menu == "Cadastrar Novo":
    st.subheader("Cadastrar Membro")
    with st.form("form_cadastro"):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome Completo *")
            nome_religioso = st.text_input("Nome Religioso")
            data_nascimento = st.text_input("Data de Nascimento")
            rg = st.text_input("RG")
            cpf = st.text_input("CPF")
        with col2:
            estado_civil = st.text_input("Estado Civil")
            conjuge = st.text_input("Cônjuge")
            endereco = st.text_input("Endereço")
            bairro = st.text_input("Bairro")
            cidade = st.text_input("Cidade")
        
        submetido = st.form_submit_button("Salvar Membro")
        if submetido:
            if not nome:
                st.error("O campo Nome é obrigatório!")
            else:
                novo_membro = Membro(
                    nome=nome, nome_religioso=nome_religioso, data_nascimento=data_nascimento,
                    rg=rg, cpf=cpf, estado_civil=estado_civil, conjuge=conjuge,
                    endereco=endereco, bairro=bairro, cidade=cidade
                )
                db.add(novo_membro)
                db.commit()
                st.success(f"Membro '{nome}' cadastrado com sucesso!")

# --- OPÇÃO 3: EDITAR / EXCLUIR ---
elif menu == "Editar / Excluir":
    st.subheader("Editar ou Excluir Membro")
    membros = db.query(Membro).all()
    if not membros:
        st.info("Nenhum membro cadastrado para editar.")
    else:
        opcoes_membros = {f"{m.id} - {m.nome}": m.id for m in membros}
        selecionado = st.selectbox("Selecione o membro:", list(opcoes_membros.keys()))
        membro_id = opcoes_membros[selecionado]
        membro = db.query(Membro).filter(Membro.id == membro_id).first()

        if membro:
            with st.form("form_edicao"):
                col1, col2 = st.columns(2)
                with col1:
                    nome = st.text_input("Nome Completo", value=membro.nome or "")
                    nome_religioso = st.text_input("Nome Religioso", value=membro.nome_religioso or "")
                    data_nascimento = st.text_input("Data de Nascimento", value=membro.data_nascimento or "")
                    rg = st.text_input("RG", value=membro.rg or "")
                    cpf = st.text_input("CPF", value=membro.cpf or "")
                with col2:
                    estado_civil = st.text_input("Estado Civil", value=membro.estado_civil or "")
                    conjuge = st.text_input("Cônjuge", value=membro.conjuge or "")
                    endereco = st.text_input("Endereço", value=membro.endereco or "")
                    bairro = st.text_input("Bairro", value=membro.bairro or "")
                    cidade = st.text_input("Cidade", value=membro.cidade or "")

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
                db.commit()
                st.success("Dados atualizados com sucesso!")
                st.rerun()

            if st.button("🗑️ Excluir Membro", type="primary"):
                db.delete(membro)
                db.commit()
                st.warning("Membro excluído!")
                st.rerun()

db.close()
