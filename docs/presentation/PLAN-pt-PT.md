# CentCompras — Plano da apresentação (pt-PT)

**Versão:** 2.6 · **Data:** 11 setembro 2026  
**URL:** `/presentation/pt/` (atalho: `/presentation/`) · **Inglês:** `/presentation/en/`  
**Idioma:** Português (pt-PT) · Plano EN: [`PLAN-en.md`](PLAN-en.md)  
**Público:** Armazém central, gestores e operadores de filial, direção

---

## Objetivo

Comunicar quatro mensagens centrais:

1. **Comece hoje** — chamada à acção por papel (slide 11); os dados acumulam-se com o uso diário.
2. **Os dados são o novo petróleo** — quanto mais cedo o pessoal usar o CentCompras, mais cedo haverá informação fiável para gráficos e decisões (slide 13).
3. **Circuito fechado** — do artigo ao stock, passando por aprovisionamento, autorização e expedição.
4. **Dois canais humanos** — **Conversas** de pedido são **conversas limitadas que fecham** (slide 9); a Voz da Empresa é um **feed contínuo** que nunca fecha (slide 12).

A apresentação é **informativa** (não expõe dados reais). Gráficos marcados como **visão futura** são ilustrativos. Uma imagem vale mil palavras: os slides 2–9 lideram com SVG; sem caminhos URL nem nomes de código nesses slides.

---

## Narrativa

| Acto | Slides | Mensagem |
|------|--------|----------|
| **I — Gancho + orientação** | 1–3 | Capa, vista de conjunto, circuito fechado (CEM-50) |
| **II — Operações (gráficos)** | 4–8 | Requisição, receção na filial, catálogo, aprovisionamento, stock central |
| **III — Falha + visão** | 9–10 | Conversa de artigo em falta, gráficos futuros |
| **IV — Chamada à acção + canal restante** | 11–12 | CTA por papel, Voz da Empresa |
| **V — Porquê + o que já se regista** | 13–15 | Metáfora dos dados, cenário, tabela de modelos |
| **VI — Controlos + demo** | 16–17 | Autorização, login demo |

---

## Mapa slide a slide

### Slide 1 — Capa
- **Título:** CentCompras — Logística centralizada com filiais
- **Subtítulo:** Dados, circuitos e circularidade

### Slide 2 — Um sistema, dois locais de trabalho
- SVG vista de conjunto: círculo grande do armazém (topo, teal) + círculo menor da filial (esquerda, mostarda)
- Seta âmbar **Precisamos disto**; arco verde **Aqui está**
- Título **Filial** mostarda (`#f59e0b`); armazém teal
- Rodapé: **A filial pede. O armazém entrega.**

### Slide 3 — Circuito fechado (diagrama)
- Título **Do artigo ao stock na filial**; rodapé inalterado (o circuito fecha quando a filial confirma)
- Linha secundária: *Exemplo: CEM-50 — Cimento 50 kg. Já está no catálogo; o circuito fecha na filial.*
- SVG em oval (armazém canto superior direito / filial canto inferior esquerdo): **Pede** (chip CEM-50) → **Stock**; desvio tracejado **Sem stock** **Encomenda → Receção** (legenda *encomenda vira receção*) de volta ao Stock → **Expedido** → **Confirma** (fecho)
- Sem caminhos URL; sem nó Aprovação; sem caixa Catálogo; setas a cores param em Confirma

### Slide 4 — Requisição interna
- *A filial pede; o armazém expede.*
- Filial (mostarda): Catálogo → Rascunho → Submete; Armazém (teal): Fila → Expede → **estado → expedido** (duas barras verticais entre Expede e estado, sem seta); seta **Aprovado**
- Sem caminhos URL

### Slide 5 — Receção na filial
- Expedido → Confirma qtd → Stock filial sobe; cinzentos Parcial / encerra e Ajuste admin
- Manter o rodapé do circuito fechado

### Slide 6 — Catálogo e preços
- *Só o armazém gere o catálogo.*
- Constelação: **Artigo** no centro; Família, Fornecedor, Preços, Genesis → Activo

### Slide 7 — Aprovisionamento
- *Do rascunho ao fechado.*
- Rascunho → Validado → Submetido → Aprovado → Recebido / Fechado
- Só rodapé (sem preço de fornecedor = sem linha)

### Slide 8 — Stock central
- *A quantidade nunca se escreve à mão.*
- Massa **Físico** com mordidela mostarda **Reservado**; **Disponível = físico − reservado**

### Slide 9 — Quando o artigo não existe
- Linha secundária: *Não é uma encomenda — uma conversa que fecha quando o artigo entra para o catálogo.*
- Nós: **Não está no catálogo!!** → **Nova conversa** (caixa exterior com **Filial** ↔ **Armazém** dentro) → **Entendimento** → **Inserido no catálogo** → **Fecha a conversa**
- Seta mostarda só de Não está no catálogo para Nova conversa; ida-e-volta dentro da caixa; cinzento abaixo para nas bordas

### Slide 10 — Visão futura: gráficos *(mock)*
- Gráficos ilustrativos; etiqueta **Visão futura — ilustrativo**

### Slide 11 — O que precisamos de si (CTA)
- Quatro acções por papel

### Slide 12 — Voz da Empresa (final)
- Texto + painel do feed; ainda **Voz da Empresa** no deck (Parle D40 não aplicado aqui)

### Slide 13 — Os dados são o novo petróleo
- Metáfora petróleo bruto vs refinado

### Slide 14 — O cenário de hoje
- Armazém central + filiais; lista de módulos

### Slide 15 — O que o sistema já regista
- Tabela de modelos; regra de ouro do stock

### Slide 16 — Autorização
- Limites PO + tetos filial
- Títulos: **Armazém** teal (`#14b8a6`); **Filial** mostarda (`#f59e0b`)

### Slide 17 — Experimente a aplicação (login demo)
- Aviso HTTP; `DEMO_LOGIN_URL`; palavra-passe `devpass123`
- Título **Armazém central** teal; **Filiais** e coluna **Filial** mostarda

---

## Recursos técnicos

| Componente | Localização |
|------------|-------------|
| Plano (este ficheiro) | `docs/presentation/PLAN-pt-PT.md` |
| Plano inglês | `docs/presentation/PLAN-en.md` |
| App Django | `presentation/` |
| Template PT | `presentation/templates/presentation/deck_pt.html` |
| Template EN | `presentation/templates/presentation/deck_en.html` |
| CSS / JS | `presentation/static/presentation/css/deck.css` (`?v=20`), `js/deck.js` |
| Rota PT | `/presentation/` ou `/presentation/pt/` |
| Rota EN | `/presentation/en/` |

### Sub-agente visual
Para gráficos de slides, lançar primeiro um consultor de design **generalPurpose** (slides 4–9: [Visual layout](0748cef2-9c52-4b6f-b63b-0403d19e6e3f) / [Visual layout](31643dbd-721a-469e-b694-8836bf6626d9)). Tokens: armazém teal `#14b8a6`, filial mostarda `#f59e0b`, cinzento `#94a3b8`; nós arredondados; sem colunas em caixa; sem URLs; palavras do dia a dia.

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
