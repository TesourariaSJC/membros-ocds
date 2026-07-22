import os
import streamlit as st
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# --- Configuração do App e Banco de Dados ---
app = Flask(__name__)
db_url = os.environ.get("DATABASE_URL", "sqlite:///ocds_membros.db").replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- Modelo Membro ---
class Membro(db.Model):
    __tablename__ = "membros"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    nome_religioso = db.Column(db.String(200))
    data_nascimento = db.Column(db.String(30))
    rg = db.Column(db.String(30))
    cpf = db.Column(db.String(40))
    estado_civil = db.Column(db.String(50))
    conjuge = db.Column(db.String(200))
    endereco = db.Column(db.String(250))
    bairro = db.Column(db.String(150))
    cidade = db.Column(db.String(150))

with app.app_context():
    db.create_all()

# --- Interface Streamlit ---
st.set_page_config(page_title="Gestão de Membros", layout="wide")
st.title("📋 Cadastro e Gestão de Membros")

# Menu Lateral
menu = st.sidebar.selectbox("Navegação", ["Listar Membros", "Cadastrar Novo", "Editar / Excluir"])

with app.app_context():
    # --- OPÇÃO 1: LISTAR ---
    if menu == "Listar Membros":
        st.subheader("Membros Cadastrados")
        membros = Membro.query.all()
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
                    db.session.add(novo_membro)
                    db.session.commit()
                    st.success(f"Membro '{nome}' cadastrado com sucesso!")

    # --- OPÇÃO 3: EDITAR / EXCLUIR ---
    elif menu == "Editar / Excluir":
        st.subheader("Editar ou Excluir Membro")
        membros = Membro.query.all()
        if not membros:
            st.info("Nenhum membro cadastrado para editar.")
        else:
            opcoes_membros = {f"{m.id} - {m.nome}": m.id for m in membros}
            selecionado = st.selectbox("Selecione o membro:", list(opcoes_membros.keys()))
            membro_id = opcoes_membros[selecionado]
            membro = Membro.query.get(membro_id)

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

                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
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
                    db.session.commit()
                    st.success("Dados atualizados com sucesso!")
                    st.rerun()

                # Botão fora do form para exclusão
                if st.button("🗑️ Excluir Membro", type="primary"):
                    db.session.delete(membro)
                    db.session.commit()
                    st.warning("Membro excluído!")
                    st.rerun()
