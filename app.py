import os
import streamlit as st
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# --- Configuração do App e Banco de Dados ---
app = Flask(__name__)

# Tenta pegar dos Secrets do Streamlit ou das Variáveis de Ambiente do sistema
raw_db_url = None

if "DATABASE_URL" in st.secrets:
    raw_db_url = st.secrets["DATABASE_URL"]
else:
    raw_db_url = os.environ.get("DATABASE_URL", "sqlite:///ocds_membros.db")

# Garante substituição do protocolo antigo do postgres caso exista
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = raw_db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
