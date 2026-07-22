{\rtf1\ansi\ansicpg1252\cocoartf2870
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import os\
from flask import Flask, render_template, request, redirect, url_for, flash\
from flask_sqlalchemy import SQLAlchemy\
\
app = Flask(__name__)\
\
# --- Configura\'e7\'f5es fornecidas ---\
class Config:\
    SQLALCHEMY_DATABASE_URI = os.environ.get(\
        "DATABASE_URL", "sqlite:///ocds_membros.db"\
    ).replace("postgres://", "postgresql://", 1)\
    SQLALCHEMY_TRACK_MODIFICATIONS = False\
    SECRET_KEY = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento")\
\
app.config.from_object(Config)\
db = SQLAlchemy(app)\
\
# --- Modelo Membro ---\
class Membro(db.Model):\
    __tablename__ = "membros"\
\
    id = db.Column(db.Integer, primary_key=True)\
    nome = db.Column(db.String(200), nullable=False)\
    nome_religioso = db.Column(db.String(200))\
    data_nascimento = db.Column(db.String(30))\
    rg = db.Column(db.String(30))\
    cpf = db.Column(db.String(40))\
    estado_civil = db.Column(db.String(50))\
    conjuge = db.Column(db.String(200))\
    endereco = db.Column(db.String(250))\
    bairro = db.Column(db.String(150))\
    cidade = db.Column(db.String(150))\
\
# Criar o banco de dados caso n\'e3o exista\
with app.app_context():\
    db.create_all()\
\
# --- Rotas da Aplica\'e7\'e3o ---\
\
@app.route("/")\
def index():\
    membros = Membro.query.all()\
    return render_template("index.html", membros=membros)\
\
@app.route("/novo", methods=["GET", "POST"])\
def novo():\
    if request.method == "POST":\
        membro = Membro(\
            nome=request.form.get("nome"),\
            nome_religioso=request.form.get("nome_religioso"),\
            data_nascimento=request.form.get("data_nascimento"),\
            rg=request.form.get("rg"),\
            cpf=request.form.get("cpf"),\
            estado_civil=request.form.get("estado_civil"),\
            conjuge=request.form.get("conjuge"),\
            endereco=request.form.get("endereco"),\
            bairro=request.form.get("bairro"),\
            cidade=request.form.get("cidade"),\
        )\
        db.session.add(membro)\
        db.session.commit()\
        return redirect(url_for("index"))\
    return render_template("form.html", membro=None)\
\
@app.route("/editar/<int:id>", methods=["GET", "POST"])\
def editar(id):\
    membro = Membro.query.get_or_404(id)\
    if request.method == "POST":\
        membro.nome = request.form.get("nome")\
        membro.nome_religioso = request.form.get("nome_religioso")\
        membro.data_nascimento = request.form.get("data_nascimento")\
        membro.rg = request.form.get("rg")\
        membro.cpf = request.form.get("cpf")\
        membro.estado_civil = request.form.get("estado_civil")\
        membro.conjuge = request.form.get("conjuge")\
        membro.endereco = request.form.get("endereco")\
        membro.bairro = request.form.get("bairro")\
        membro.cidade = request.form.get("cidade")\
        \
        db.session.commit()\
        return redirect(url_for("index"))\
    return render_template("form.html", membro=membro)\
\
@app.route("/deletar/<int:id>", methods=["POST"])\
def deletar(id):\
    membro = Membro.query.get_or_404(id)\
    db.session.delete(membro)\
    db.session.commit()\
    return redirect(url_for("index"))\
\
if __name__ == "__main__":\
    app.run(debug=True)}