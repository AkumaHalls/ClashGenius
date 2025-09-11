# ⚡️💥 ClashGenius v20.1.48 — O Gênio das Guerras está estável! 💥⚡️

![Versão](https://img.shields.io/badge/versão-20.1.48--WAR--PREDICTION-blueviolet?style=flat-square)
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
- 🧠 **Previsão de Guerra**: Análise tática em tempo real sobre as chances de vitória.
- 🎯 **Ataques Pendentes**: veja quem ainda não atacou, com um visual profissional e agrupado por guerra.
- 🛡️ **Lista Completa de Membros**: CV, liga, troféus, cargos e OBS personalizadas com cores, salvas em banco de dados.
- 🏆 **Informações da CWL**: dados completos de todas as guerras e participantes.
- 📜 **Histórico de Guerras**: registro completo das guerras anteriores.
- 🎨 **Visual Temático** Clash of Clans com fundo animado, música e favicon.
- 🔐 **Painel de Administrador**: Controle funções críticas do bot, como o modo manutenção, de forma segura.
- 🌐 **Acesso Rápido**: `https://SEU_DOMINIO.onrender.com/painel`
- ⚙️ **Servidor Web embutido** com `aiohttp`.

---

## 🔄 CHANGELOG

### v20.1.65 (11/09/2025)

-✨ NOVO RECURSO (IA v3.0): Implementada a arquitetura avançada de IA (WarPredictionSystemV3), refatorando toda a lógica de previsão.

  -🧠 Modularização: O código da IA foi movido para um arquivo dedicado (war_predictor.py), tornando o projeto mais limpo e organizado para futuras expansões.

  -🤖 Ensemble de Modelos: O sistema agora utiliza múltiplos modelos de Machine Learning (GradientBoostingRegressor e RandomForestRegressor) para criar uma previsão combinada, aumentando a precisão e robustez.

  -🎯 Engenharia de Features Avançada: A IA agora calcula métricas novas e sofisticadas para suas análises, como:

momentum_indicator: Analisa a tendência dos ataques mais recentes para ver qual clã está com "a mão quente".

clan_synergy_score: Mede a eficiência do clã em ataques de limpeza ("cleanup"), indicando o nível de coordenação.

pressure_index: Calcula um índice de pressão psicológica, que aumenta quando o clã está atrás no placar em estágios avançados da guerra.

  -📊 Relatórios Detalhados para o Discord: A análise enviada para o Discord foi completamente reformulada para incluir insights táticos, fatores de risco e as principais métricas que levaram à previsão.

  -🌐 Resumo Otimizado para o Painel: O painel web recebe uma versão resumida e direta da previsão, mantendo a interface limpa e de fácil leitura.

  -✅ Correção (Banco de Dados): Resolvido erro NotImplementedError que ocorria ao verificar a conexão com o banco de dados. A verificação foi atualizada para if self.db is None:, que é o padrão moderno da biblioteca pymongo.

  -✅ Correção (API): Resolvido AttributeError na aba "Clã" que ocorria quando a API do Clash of Clans não retornava algum dado (como localização ou liga da capital). A função fetch_clan_info_for_web agora usa getattr para acessar os dados de forma segura, prevenindo quebras no painel.

### v20.1.59 (11/09/2025)
- 🎨 MELHORIA DE INTERFACE: Aprimorada a visualização da previsão da IA no painel web.

  -✨ Tags de Dados: Os valores de "Probabilidade" e "Confiança" agora são exibidos em "badges" (etiquetas) modernas e informativas, com ícones e rótulos claros.

  -✨ Tooltips Explicativos: Adicionadas caixas de ajuda (tooltips) que aparecem ao passar o mouse sobre as novas badges, explicando o que cada métrica significa. Isso torna a interface mais intuitiva para todos os membros do clã.

### v20.1.48 (08/09/2025)
- ✨ **NOVO RECURSO:** Implementada a funcionalidade de **Previsão de Guerra** na aba "Guerra".
    - 🧠 **Análise Tática:** O sistema agora analisa estrelas, destruição e ataques restantes para gerar uma previsão textual do resultado da guerra em tempo real.
    - 🗣️ **Mensagens Dinâmicas:** Exibe diferentes cenários, como vitória garantida, chances de virada do oponente e o que é necessário para vencer, com mensagens claras e diretas.
    - 🎨 **Integração Visual:** A previsão aparece em um card destacado abaixo do cabeçalho da guerra para fácil e rápida visualização estratégica.

### v20.1.45 (07/09/2025)
- ✨ **NOVO RECURSO:** Adicionado um **Painel de Administrador** completo e seguro.
    - 🔐 **Acesso Restrito:** Implementada uma página de login com senha para proteger a área administrativa.
    - 🛠️ **Modo Manutenção:** Administradores podem ativar/desativar o modo de manutenção, que exibe uma página de aviso para os usuários e pausa os alertas do bot no Discord.
    - 💬 **Teste de Comunicação:** Adicionado um botão para enviar uma mensagem de teste ao canal do Discord, verificando a conexão e o status do bot.
    - ℹ️ **Informações do Sistema:** O painel agora exibe a versão atual do bot.

### v20.1.39 (07/09/2025)
- 🚀 **MELHORIA GERAL:** Reformulada completamente a aba **"Ataques Pendentes"** para uma ferramenta de administração profissional.
    - ✨ **Novo Layout:** Substituída a lista de texto por um sistema de cartões de alerta visuais.
    - ✨ **Agrupamento por Guerra:** As pendências agora são agrupadas por cada guerra, mostrando o oponente e a data.
    - ✨ **Destaque de "Última Guerra":** Um selo `💥 Última Guerra` é exibido no grupo da guerra mais recente para fácil identificação.
    - ✨ **Alerta por Gravidade:** Os cartões possuem bordas coloridas (amarela para 1 ataque, vermelha para 2) para sinalizar a urgência.
    - ✨ **Cópia de Tag:** Adicionada a tag do jogador e um botão "Copiar" em cada cartão para facilitar a administração no jogo.
- ✅ **Correção Definitiva:** Resolvido o problema na aba **"Destaques"** onde os "Heróis da Última Guerra" não eram exibidos.
    - 🔧 **Lógica Corrigida:** O sistema agora salva corretamente a tag de cada membro no histórico de guerra, garantindo que o filtro de melhores ataques funcione de forma precisa para as guerras futuras.
    - ✨ **Contexto Adicionado:** A data da guerra analisada agora é exibida no título da seção "Heróis da Última Guerra".

### v20.1.18 (15/08/2025)
- ✨ **NOVO:** Adicionado Favicon customizável, tornando o painel um PWA (Progressive Web App) instalável no celular.
- ✨ **NOVO:** Implementado música de fundo no painel web com botão para silenciar.
- ✨ **NOVO:** Adicionado monitoramento de doações e tropas recebidas com alertas no Discord.

### v20.1.15 (14/08/2025)
- ✅ **Correção Definitiva:** Resolvido erro `TypeError: Object of type WarState is not JSON serializable`, estabilizando completamente a aba "Guerra" do painel.
- ✅ **Conexão com MongoDB Reforçada:** Melhorada a verificação de conexão com o banco de dados para evitar falhas na aba "Membros".

### v20.1.4 - v20.1.12
- ✨ **Integração com MongoDB:** Adicionado suporte a MongoDB para salvar as notas dos jogadores de forma persistente.
- 🐞 **Correções no Painel Web:** Resolvidos múltiplos erros 500 e `NoneType` que afetavam as abas de Guerra, Histórico e Membros.
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
```
Crie o arquivo .env com:

```
DISCORD_TOKEN=seu_token_aqui
COC_EMAIL=seu_email_supercell
COC_PASSWORD=sua_senha_supercell
CLAN_TAG=#TAG_DO_SEU_CLA
CHANNEL_ID=ID_DO_CANAL_DE_LOGS
MONGO_DB_URL=sua_url_de_conexao_mongodb
ADMIN_PASSWORD=uma_senha_forte_para_o_painel
FERNET_KEY=execute_o_seguinte_script_para_gerar_uma_chave
```
Para gerar a FERNET_KEY, execute este pequeno script Python uma vez e copie o resultado:

```
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```
A pasta static/ com painel.html, css/ e js/ deve estar no mesmo diretório de clash.py.

▶️ RODANDO O BOT

```
python clash.py
```
🤝 CONTRIBUIÇÕES
Contribuições são muito bem-vindas!
Abra uma issue, envie um PR ou compartilhe ideias!

📜 LICENÇA
Distribuído sob a licença MIT. Veja LICENSE para mais detalhes.
