# CentCompras — Plano da apresentação (pt-PT)

**Versão:** 2.3 · **Data:** 11 setembro 2026  
**URL:** `/presentation/pt/` (atalho: `/presentation/`) · **Inglês:** `/presentation/en/`  
**Idioma:** Português (pt-PT) · Plano EN: [`PLAN-en.md`](PLAN-en.md)  
**Público:** Armazém central, gestores e operadores de filial, direção

---

## Objetivo

Comunicar quatro mensagens centrais:

1. **Comece hoje** — chamada à acção por papel (slide 14, antes da despedida); os dados acumulam-se com o uso diário.
2. **Os dados são o novo petróleo** — quanto mais cedo o pessoal usar o CentCompras, mais cedo haverá informação fiável para gráficos e decisões.
3. **Circuito fechado** — do artigo ao stock, passando por aprovisionamento, autorização e expedição.
4. **Dois canais humanos** — **Conversas** de pedido são **conversas limitadas que fecham**; a Voz da Empresa é um **feed contínuo** que nunca fecha.

A apresentação é **informativa** (não expõe dados reais). Gráficos marcados como **visão futura** são ilustrativos.

---

## Narrativa (6 actos)

| Acto | Slides | Mensagem |
|------|--------|----------|
| **I — Gancho + porquê** | 1–4 | Capa, metáfora dos dados, cenário, registo |
| **II — Fluxo filial primeiro** | 5–6 | Requisição interna + receção na filial |
| **III — Passos armazém** | 7–10 | Catálogo até stock central |
| **IV — Arquitectura + visão** | 11–13 | Diagrama circuito fechado, vista de conjunto (slide 12), gráficos futuros |
| **V — Chamada à acção** | 14 | CTA por papel (adiada) |
| **VI — Canais humanos + mãos à obra** | 15–17 | Conversas (artigo em falta), Voz da Empresa, login demo |

---

## Mapa slide a slide

### Slide 1 — Capa
- **Título:** CentCompras — Logística centralizada com filiais
- **Subtítulo:** Dados, circuitos e circularidade
- **Notas:** Plataforma única (PostgreSQL = fonte de verdade).

### Slide 2 — Os dados são o novo petróleo
- Metáfora petróleo bruto vs refinado
- **Notas:** Não é preciso esperar por gráficos.

### Slide 3 — O cenário de hoje
- Armazém central + filiais; lista simples de módulos (sem grelha de cartões)
- **Notas:** Fases 0–6 concluídas.

### Slide 4 — O que o sistema já regista
- Tabela de modelos; regra de ouro do stock
- **Notas:** Zero digitação directa de quantidades.

### Slide 5 — Requisição interna
- Filial + armazém; offline PWA
- **Notas:** Aprovar nunca falha por falta de stock.

### Slide 6 — Receção na filial
- Fecha o circuito operacional do lado da filial
- **Notas:** Cada passo fica registado.

### Slide 7 — Catálogo e preços
- `/manage/items/` — Genesis, auditoria

### Slide 8 — Aprovisionamento
- `/manage/purchase-orders/`

### Slide 9 — Autorização
- Limites PO + tetos filial

### Slide 10 — Stock central
- `/manage/goods-receipts/`; reserva FIFO (D32)

### Slide 11 — Circuito fechado (diagrama)
- SVG do fluxo operacional completo
- **Notas:** Vista de pássaro depois dos slides de passos.

### Slide 12 — Um sistema, dois locais de trabalho
- Sobretítulo: **Vista de conjunto**; título: **Um sistema, dois locais de trabalho**
- Descrição: armazém central + filial **(filiais)** — a mesma aplicação, dois locais de trabalho
- SVG vista de conjunto: círculo grande do armazém (topo) + círculo menor da filial (esquerda)
- Seta âmbar + etiqueta **Precisamos disto** (filial → armazém); arco verde + etiqueta **Aqui está** (armazém → filial); bordas finas âmbar/verde nas etiquetas
- Bullets por unidade (sem papéis, sem URLs)
- Rodapé: **A filial pede. O armazém entrega.**
- **Notas:** Mapa para quem não conhece a app; circuitos de permissão vêm depois.

### Slide 13 — Visão futura: gráficos *(mock)*
- Gráficos ilustrativos; etiqueta **Visão futura — ilustrativo**

### Slide 14 — O que precisamos de si (CTA)
- Quatro acções por papel: armazém, filiais, gestão, todos
- **Notas:** Sem rodapé de manuais/Fase 7 aqui; antecipa Voz da Empresa (ponto 4).

### Slide 15 — Quando o artigo não existe
- **Título:** Quando o artigo não existe no catálogo
- **Linha secundária (menor):** *Não é uma encomenda — uma conversa que fecha quando o artigo entra para o catálogo.*
- Fluxo aberto em 5 passos (vertical)
- Nós: **Não está no catálogo!!** ↔ **Nova conversa** → **Entendimento** → **Inserido no catálogo** → **Fecha a conversa**
- Setas amarela/verde: só no par inicial (filial ↔ nova conversa); resto do fluxo — setas cinzentas
- Caixas cinzentas: Nova conversa + Entendimento; **Inserido no catálogo** — borda verde (armazém)
- Abaixo do fecho (sem seta): **Expressar satisfação** + estrelas 1–5 (1★ por defeito — igual ao diálogo de fecho nas Conversas)
- **Notas:** O artigo entra para o catálogo pelo fluxo normal, não dentro do chat — não é Voz da Empresa.

### Slide 16 — Voz da Empresa (final)
- Texto (esquerda) + painel do feed contínuo (direita)
- **Continue a falar**; despedida com participação activa
- Rodapé: manuais · Fase 7
- **Notas:** O feed nunca fecha.

### Slide 17 — Experimente a aplicação (login demo)
- **Experimente agora**; aviso HTTP; URL de `presentation/views.py` (`DEMO_LOGIN_URL`)
- Palavra-passe `devpass123` para todas as contas seed
- Tabelas armazém + filiais
- **Notas:** Último slide — login imediato após a apresentação.

---

## Recursos técnicos

| Componente | Localização |
|------------|-------------|
| Plano (este ficheiro) | `docs/presentation/PLAN-pt-PT.md` |
| Plano inglês | `docs/presentation/PLAN-en.md` |
| App Django | `presentation/` |
| Template PT | `presentation/templates/presentation/deck_pt.html` |
| Template EN | `presentation/templates/presentation/deck_en.html` |
| CSS / JS | `presentation/static/presentation/css/deck.css` (`?v=13`), `js/deck.js` |
| Rota PT | `/presentation/` ou `/presentation/pt/` |
| Rota EN | `/presentation/en/` |

### Navegação do deck
- Setas ← →, Espaço, Page Up/Down
- Barra de progresso; contador de slides
- `F` ecrã inteiro; `?` ajuda
- Responsivo (projector + tablet)

---

## Referências no código

| Conceito | App / ficheiro |
|----------|----------------|
| Catálogo | `products/services.py`, `/manage/items/` |
| Encomendas de compra | `procurement/`, `/manage/purchase-orders/` |
| Stock | `inventory/services.py`, `StockMovement` |
| Requisição | `orders/`, `/branch/requests/` |
| Conversas | `threads/`, `/branch/threads/` |
| Voz da Empresa | `company_voice/`, `/company-voice/` |
| Filiais | `branches/`, `ActiveBranchMiddleware` |
| Manuais pt-PT | `docs/user-manuals/pt/` |
