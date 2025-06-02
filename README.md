# ⚡️💥 ClashGenius v19.8.13 — O Gênio das Guerras chegou! 💥⚡️

![Versão](https://img.shields.io/badge/versão-19.8.13-blueviolet?style=flat-square)
![Status](https://img.shields.io/badge/Projeto-Em%20Desenvolvimento-yellow?style=flat-square)
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
- 🛡️ **Lista Completa de Membros**: CV, liga, troféus, cargos e OBS personalizadas com cores (🟢 OK, 🟡 Atenção, 🔴 Crítico).
- 🏆 **Informações da CWL**: dados completos de todas as guerras e participantes.
- 📜 **Histórico de Guerras**: registro completo das guerras anteriores.
- 🎨 **Visual Temático** Clash of Clans e warreport.app.
- 🌐 **Acesso Rápido**: [https://SEU_DOMINIO.onrender.com/painel](https://SEU_DOMINIO.onrender.com/painel)
- ⚙️ **Servidor Web embutido** com `aiohttp`.

---

## 🔄 CHANGELOG

### v19.8.13 (01/06/2025)
- ✅ Correção: ataques durante "preparation" agora exibem corretamente.

### v19.8.12
- ✅ Correções de NameError e AttributeError relacionados à CWL e datas.
- ✅ Ajuste para `str(war.state).capitalize()`.

### v19.8.5 - v19.8.11
- 🐞 Depuração e ajustes para `coc.py==3.9.1`.
- 🛠️ Robustez no carregamento de `player_notes.json`.

### v19.8
- ✨ NOVO: Observações por jogador com cor e persistência em JSON.
- 🎨 NOVO: Tema web estilo warreport.app.
- 🔧 NOVO: Rotas de API para observações personalizadas.

### v18.0 (marco inicial)
- 🚀 Painel Web Interativo.
- ✅ Logs coloridos, sistema de alertas, modularização e comandos organizados.

---

## 🧠 FUNCIONALIDADES INTELIGENTES

### 👁️ EVENTOS MONITORADOS
- Entrada/saída de membros
- Doações e cargos
- Ataques, defesas, estrelas (guerra e CWL)

### ⚔️ RELATÓRIOS AUTOMÁTICOS (via Discord)
- Alerta de ataque perdido com menções
- Alerta de ataque de 1 estrela com cargo específico

### 🖥️ DASHBOARD INTERATIVO
- Acompanhe tudo em tempo real pelo navegador
- Edição de observações de membros diretamente pelo painel

---

## 📦 REQUISITOS

- Python 3.8+
- Conta Supercell ID para API
- Bot do Discord com token
- Canal para logs no Discord
- Ambiente como Render.com

---

## ⚙️ COMO INSTALAR

```bash
# Clone o repositório
git clone https://github.com/AkumaHalls/ClashGenius.git
cd clashgenius

# Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/macOS
.env\Scriptsctivate    # Windows

# Instale as dependências
pip install -r requirements.txt
```

Crie o arquivo `.env` com:

```env
DISCORD_TOKEN=seu_token_aqui
COC_EMAIL=seu_email_supercell
COC_PASSWORD=sua_senha_supercell
CLAN_TAG=#TAG_DO_CLA
CHANNEL_ID=ID_CANAL_DISCORD
ROLE_ID_1STAR_ALERT=ID_CARGO_1_ESTRELA
ROLE_ID_MISSED_ATTACK=ID_CARGO_ATQ_PERDIDO
TEST_GUILD_ID=ID_SERVIDOR_TESTE
```

A pasta `static/` com `painel.html`, `css/` e `js/` deve estar no mesmo diretório de `clash.py`.

---

## ▶️ RODANDO O BOT

```bash
python clash.py
```

---

## 🤝 CONTRIBUIÇÕES

Contribuições são muito bem-vindas!  
Abra uma issue, envie um PR ou compartilhe ideias!

---

## 📜 LICENÇA

Distribuído sob a licença MIT. Veja `LICENSE` para mais detalhes.
