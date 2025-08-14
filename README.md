# ⚡️💥 ClashGenius v20.1.15 — O Gênio das Guerras está estável! 💥⚡️

![Versão](https://img.shields.io/badge/versão-20.1.15--FINAL--STABLE-blueviolet?style=flat-square)
![Status](https://img.shields.io/badge/Projeto-Estável-brightgreen?style=flat-square)
![Linguagem](https://img.shields.io/badge/python-3.8+-blue?logo=python&style=flat-square)
![Licença](https://img.shields.io/github/license/AkumaHalls/ClashGenius?style=flat-square)
![Hospedagem](https://img.shields.io/badge/hospedagem-render.com-informational?style=flat-square&logo=render)
![Contribuições](https://img.shields.io/badge/contribuições-bem%20vindas-brightgreen?style=flat-square)

> 🎉 OPA, CHEFE! Preparado para dominar os campos de batalha do Clash of Clans como nunca antes?!  
> O **ClashGenius** é seu bot + painel de guerra definitivo, com monitoramento em tempo real, alertas automáticos e um **painel web interativo** que parece ter saído direto de um livro de guerra épico! 🏰🔥

---

## 🌟 DESTAQUES DO PAINEL WEB

🎯 **Interatividade Total** para você e seu clã:

- 📊 **Visão Geral do Clã**: nome, tag, nível, descrição, membros, pontos, capital.
- ⚔️ **Status da Guerra Detalhado**: Normal ou CWL, com placar, tempo, estado e ataques.
- 🎯 **Ataques Pendentes**: veja quem ainda não atacou (fase de preparação e batalha).
- 🛡️ **Lista Completa de Membros**: CV, liga, troféus, cargos e OBS personalizadas com cores, salvas em banco de dados.
- 🏆 **Informações da CWL**: dados completos de todas as guerras e participantes.
- 📜 **Histórico de Guerras**: registro completo das guerras anteriores.
- 🎨 **Visual Temático** Clash of Clans com fundo animado.
- 🌐 **Acesso Rápido**: `https://SEU_DOMINIO.onrender.com/painel`
- ⚙️ **Servidor Web embutido** com `aiohttp`.

---

## 🔄 CHANGELOG

### v20.1.15 (14/08/2025)
- ✅ **Correção Definitiva:** Resolvido erro `TypeError: Object of type WarState is not JSON serializable`, estabilizando completamente a aba "Guerra" do painel.
- ✅ **Conexão com MongoDB Reforçada:** Melhorada a verificação de conexão com o banco de dados para evitar falhas na aba "Membros".

### v20.1.4 - v20.1.12
- ✨ **Integração com MongoDB:** Adicionado suporte a MongoDB para salvar as notas dos jogadores de forma persistente.
- 🐞 **Correções no Painel Web:** Resolvidos múltiplos erros 500 e `NoneType` que afetavam as abas de Guerra, Histórico e Membros, garantindo que o painel permaneça funcional mesmo com dados incompletos da API.
- 🔧 **Estabilização de Eventos:** Restaurada a lógica de registro de eventos do Discord, garantindo que todos os alertas (entrada/saída, ataques, etc.) funcionem como esperado.

---

## 🧠 FUNCIONALIDADES INTELIGENTES

### 👁️ EVENTOS MONITORADOS
- Entrada/saída de membros
- Doações e tropas recebidas
- Mudanças de cargo, liga e troféus
- Ataques em Guerras e CWL

### 🖥️ DASHBOARD INTERATIVO
- Acompanhe tudo em tempo real pelo navegador.
- Edite observações e prioridades de membros diretamente pelo painel, com salvamento automático no banco de dados.

---

## 📦 REQUISITOS

- Python 3.8+
- Conta Supercell ID para API
- Bot do Discord com token
- Canal para logs no Discord
- URL de conexão com um banco de dados MongoDB (opcional, para salvar notas)
- Ambiente como Render.com

---

## ⚙️ COMO INSTALAR

```bash
# Clone o repositório
git clone [https://github.com/AkumaHalls/ClashGenius.git](https://github.com/AkumaHalls/ClashGenius.git)
cd ClashGenius

# Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/macOS
. venv\Scripts\activate    # Windows

# Instale as dependências
pip install -r requirements.txt
Crie o arquivo .env com:DISCORD_TOKEN=seu_token_aqui
COC_EMAIL=seu_email_supercell
COC_PASSWORD=sua_senha_supercell
CLAN_TAG=#TAG_DO_SEU_CLA
CHANNEL_ID=ID_DO_CANAL_DE_LOGS
MONGO_DB_URL=sua_url_de_conexao_mongodb
A pasta static/ com painel.html, css/ e js/ deve estar no mesmo diretório de clash.py.▶️ RODANDO O BOTpython clash.py
🤝 CONTRIBUIÇÕESContribuições são muito bem-vindas!Abra uma issue, envie um PR ou compartilhe ideias!📜 LIC
