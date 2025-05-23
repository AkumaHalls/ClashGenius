
# 🎉 ClashGenius - Seu Gênio Assistente de Clash of Clans para Discord! (v17.5 Event-Driven) 🎉

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Badge"/>
  <img src="https://img.shields.io/badge/discord.py-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord.py Badge"/>
  <img src="https://img.shields.io/badge/coc.py-FFD700?style=for-the-badge" alt="coc.py Badge"/>
</p>

E aí, Chefe! 🏰  
Com o **ClashGenius v17.5**, você leva seu clã para o **próximo nível** com um bot inteligente, escrito em Python, que monitora seu clã **em tempo real** com base em **eventos oficiais da API do Clash of Clans**, e envia relatórios organizados diretamente no seu servidor Discord. 🔥

---

## 🔍 O que há de novo no v17.5?

* ✅ **Sistema event-driven completo com cache e tratamento de erros.**
* ✅ **Relatórios automáticos de ataques perdidos (Guerra e CWL).**
* ✅ **Alertas com menções para ataques de 1 estrela e membros que não atacaram.**
* ✅ **Logs coloridos e profissionais, com datas localizadas para o Brasil.**
* ✅ **Sistema de comandos por grupos: `/admin`, `/guerra`, `/info`, `/buscar`, `/rank`.**
* ✅ **Exibição separada para Guerras Normais e Ligas (CWL).**
* ✅ **Sistema modular de funções e handlers com divisão por responsabilidades.**
* ✅ **Mensagens de erro amigáveis e embutidas para cada tipo de falha.**

---

## 🧠 O que o ClashGenius faz?

### 👁️ Monitoramento por Eventos:
* Entrada e saída de membros.
* Doações e recebimentos.
* Mudanças de cargo, troféus e liga.
* Ataques e defesas em **guerras normais** e **ligas de clãs (CWL)**.

### ⚔️ Relatórios Automáticos:
* Quando uma guerra termina, o bot verifica e avisa quem **não usou todos os ataques**.
* Se alguém ataca com apenas **1 estrela**, o bot envia um alerta mencionando um cargo específico (opcional).

---

## 📦 Requisitos

* Python 3.8+
* Conta Supercell ID para gerar API Keys
* Token do Discord Bot
* Canal no Discord para logs

---

## ⚙️ Como Instalar

1. **Clone ou baixe o repositório**:
```bash
git clone https://github.com/AkumaHalls/clashgenius.git
cd clashgenius
```

2. **Crie um ambiente virtual (recomendado)**:
```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
.env\Scriptsctivate    # Windows
```

3. **Instale as dependências**:
```bash
pip install -r requirements.txt
```

4. **Crie o arquivo `.env` com as configurações**:
```env
DISCORD_TOKEN=seu_token_aqui
COC_EMAIL=seu_email_supercell
COC_PASSWORD=sua_senha_supercell
CLAN_TAG=#TAG_DO_CLA
CHANNEL_ID=123456789012345678
ROLE_ID_1STAR_ALERT=123456789012345678
ROLE_ID_MISSED_ATTACK=123456789012345678
```

---

## ▶️ Rodando o bot

Com o ambiente ativado e `.env` configurado, rode:

```bash
python clash.py
```

O bot ficará online e começará a monitorar os eventos do seu clã imediatamente! 🧞‍♂️

---

## 📋 Comandos disponíveis (`/`)

### 🔧 Admin
* `/admin ping` - Mostra a latência do bot.

### ⚔️ Guerra
* `/guerra ataques` - Lista quem ainda não atacou na guerra atual.
* `/guerra status` - Mostra o status completo da guerra (em preparação, em guerra ou encerrada).

---

## 💡 Funcionalidades automáticas

O bot avisa automaticamente no canal definido via `.env` sobre:

- 👋 Membros que entram e saem do clã.
- 🎁 Doações e 📥 recebimentos.
- 🏆 Mudanças de troféus e 🥇 ligas.
- ⚔️ Ataques feitos em tempo real.
- 🛡️ Defesas recebidas.
- ❌ Membros que não atacaram (após fim da guerra).
- ⚠️ Alerta de ataque fraco (1 estrela).

---

## 📌 Observações

* Este bot **não armazena senhas**. As credenciais do Supercell ID são usadas apenas para **gerar dinamicamente as API Keys**, e não são expostas.
* Os comandos slash são organizados em grupos e sincronizados automaticamente.
* Use `ROLE_ID_1STAR_ALERT` e `ROLE_ID_MISSED_ATTACK` para ativar menções em alertas.

---

## 🤝 Contribuições

* Achou um bug? Sugestão de melhoria?
* Abra uma **issue** ou envie um **pull request** no repositório!

---

## ✨ Autor

Feito com 💙 e muitas guerras por [Akuma](https://github.com/AkumaHalls)

---

**Divirta-se usando o ClashGenius para levar seu clã e servidor Discord a um novo nível! 💪**
