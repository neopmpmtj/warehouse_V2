# CentCompras — Plano da apresentação (pt-PT)

**Versão:** 2.1 · **Data:** 28 agosto 2026  
**URL:** `/presentation/pt/` (atalho: `/presentation/`) · **Inglês:** `/presentation/en/`  
**Idioma:** Português (pt-PT) · Plano EN: [`PLAN-en.md`](PLAN-en.md)  
**Público:** Armazém central, gestores e operadores de filial, direção

---

## Objetivo

Comunicar quatro mensagens centrais:

1. **Comece hoje** — chamada à acção por papel no início; os dados acumulam-se com o uso diário.
2. **Os dados são o novo petróleo** — quanto mais cedo o pessoal usar o CentCompras, mais cedo haverá informação fiável para gráficos e decisões.
3. **Circuito fechado** — do artigo ao stock, passando por aprovisionamento, autorização e expedição.
4. **Dois canais humanos** — fios de pedido são **conversas limitadas que fecham**; a Voz da Empresa é um **feed contínuo** que nunca fecha.

A apresentação é **informativa** (não expõe dados reais). Gráficos marcados como **visão futura** são ilustrativos.

---

## Narrativa (6 actos)

| Acto | Slides | Mensagem |
|------|--------|----------|
| **I — Gancho** | 1–2 | Capa + chamada à acção |
| **II — Porquê** | 3–6 | Cenário, metáfora dos dados, registo, visão futura |
| **III — Circuito fechado** | 7–14 | Arquitectura + fluxo operacional |
| **IV — Circularidade** | 15 | Circuito do fio (fecha) |
| **V — Despedida** | 16 | Voz da Empresa (texto + feed) |
| **VI — Mãos à obra** | 17 | URL de demo, aviso HTTP, contas seed |

---

## Mapa slide a slide

### Slide 1 — Capa
- **Título:** CentCompras — Logística centralizada com filiais
- **Subtítulo:** Dados, circuitos e circularidade
- **Notas:** Plataforma única (PostgreSQL = fonte de verdade).

### Slide 2 — O que precisamos de si (CTA)
- Quatro acções por papel: armazém, filiais, gestão, todos
- **Notas:** Sem rodapé de manuais/Fase 7 aqui; antecipa Voz da Empresa (ponto 4).

### Slide 3 — O cenário de hoje
- Armazém central + filiais; lista simples de módulos (sem grelha de cartões)
- **Notas:** Fases 0–6 concluídas (548 testes).

### Slide 4 — Os dados são o novo petróleo
- Metáfora petróleo bruto vs refinado
- **Notas:** Não é preciso esperar por gráficos.

### Slide 5 — O que o sistema já regista
- Tabela de modelos; regra de ouro do stock
- **Notas:** Zero digitação directa de quantidades.

### Slide 6 — Visão futura: gráficos *(mock)*
- Gráficos ilustrativos; etiqueta **Visão futura — ilustrativo**

### Slide 7 — Dois mundos, um sistema
- Armazém vs filial; papéis independentes

### Slide 8 — Circuito fechado (diagrama)
- SVG do fluxo operacional completo

### Slide 9 — Catálogo e preços
- `/manage/items/` — Genesis, auditoria

### Slide 10 — Aprovisionamento
- `/manage/purchase-orders/`

### Slide 11 — Autorização
- Limites PO + tetos filial

### Slide 12 — Stock central
- `/manage/goods-receipts/`; reserva FIFO (D32)

### Slide 13 — Requisição interna
- Filial + armazém; offline PWA

### Slide 14 — Receção na filial
- Fecha o circuito operacional

### Slide 15 — Circularidade (só circuito do fio)
- Diagrama do fio a largura total (lacuna → abrir → diálogo → criar → ligar → requisição → fechar)
- Bullets + legenda em duas colunas
- **Notas:** Sem Voz da Empresa neste slide.

### Slide 16 — Voz da Empresa (final)
- Texto (esquerda) + painel do feed contínuo (direita)
- **Continue a falar**; despedida com participação activa
- Rodapé: manuais · Fase 7
- **Notas:** Visual do feed movido do slide 15.

### Slide 17 — Experimente a aplicação (login demo)
- **Experimente agora**; aviso HTTP; URL `http://168.58.240.120/accounts/login/`
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
| CSS / JS | `presentation/static/presentation/css/deck.css`, `js/deck.js` |
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
| Fios | `threads/`, `/branch/threads/` |
| Voz da Empresa | `company_voice/`, `/company-voice/` |
| Filiais | `branches/`, `ActiveBranchMiddleware` |
| Manuais pt-PT | `docs/user-manuals/pt/` |
