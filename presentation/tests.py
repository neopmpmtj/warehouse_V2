from django.test import TestCase

from presentation.views import DEMO_LOGIN_URL, DEMO_PASSWORD, SLIDE_COUNT


class PresentationDeckTests(TestCase):
    def test_presentation_pt_default_loads(self):
        response = self.client.get("/presentation/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Os dados são o novo petróleo")
        self.assertContains(response, 'lang="pt-PT"')

    def test_presentation_pt_explicit_loads(self):
        response = self.client.get("/presentation/pt/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Os dados são o novo petróleo")

    def test_presentation_en_loads(self):
        response = self.client.get("/presentation/en/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Data is the new oil")
        self.assertContains(response, "What we need from you")
        self.assertContains(response, "Start today — data compounds")
        self.assertContains(response, "Company Voice — your ongoing channel")
        self.assertContains(response, "missing-item-loop")
        self.assertContains(response, "voice-feed-panel")
        self.assertNotContains(response, "circularity-zones")
        self.assertContains(response, 'lang="en"')

    def test_presentation_pt_cta_present(self):
        response = self.client.get("/presentation/pt/")
        self.assertContains(response, "O que precisamos de si")
        self.assertContains(response, "Comece hoje — os dados acumulam-se")
        self.assertContains(response, "Voz da Empresa — o seu canal permanente")

    def test_presentation_en_slide_order(self):
        response = self.client.get("/presentation/en/")
        content = response.content.decode()
        self.assertLess(
            content.index("Data is the new oil"),
            content.index("Today's scenario"),
        )
        self.assertLess(
            content.index("Internal request"),
            content.index("Catalogue and pricing"),
        )
        self.assertLess(
            content.index("Future vision: charts and decisions"),
            content.index("Start today — data compounds"),
        )

    def test_presentation_slide12_birds_eye(self):
        en = self.client.get("/presentation/en/")
        self.assertContains(en, "One system, two workplaces")
        self.assertContains(en, "worlds-diagram")
        self.assertContains(en, "We need this")
        self.assertContains(en, "Here it is")
        self.assertContains(
            en,
            "The branch asks. The warehouse answers.",
        )
        self.assertNotContains(en, "Everyone works in the same software")
        self.assertNotContains(en, "Two worlds, one system")
        pt = self.client.get("/presentation/pt/")
        self.assertContains(pt, "Um sistema, dois locais de trabalho")
        self.assertContains(pt, "worlds-diagram")
        self.assertContains(pt, "Precisamos disto")
        self.assertContains(pt, "Aqui está")
        self.assertContains(
            pt,
            "A filial pede. O armazém entrega.",
        )
        self.assertNotContains(pt, "Todos trabalham no mesmo software")
        self.assertNotContains(pt, "Dois mundos, um sistema")

    def test_presentation_slide15_missing_item_loop(self):
        en = self.client.get("/presentation/en/")
        self.assertContains(en, "When the item is not in the catalogue")
        self.assertContains(en, "missing-item-loop")
        self.assertContains(en, "New conversation")
        self.assertContains(en, "Understanding reached")
        self.assertContains(en, "Inserted in catalogue")
        self.assertContains(en, "Conversation closes")
        self.assertContains(en, "Express satisfaction")
        self.assertContains(en, "missing-item-star-on")
        self.assertContains(
            en,
            "Not an order — a conversation that closes once the item enters the catalogue.",
        )
        self.assertNotContains(en, "Talk it through")
        self.assertNotContains(en, "ThreadReadState")
        self.assertNotContains(en, "/branch/threads/")
        self.assertNotContains(en, "Order as usual")
        self.assertNotContains(en, "Next missing item")
        pt = self.client.get("/presentation/pt/")
        self.assertNotContains(en, "When something is missing")
        self.assertContains(pt, "Quando o artigo não existe no catálogo")
        self.assertContains(pt, "missing-item-loop")
        self.assertContains(pt, "Nova conversa")
        self.assertContains(pt, "Não está no catálogo!!")
        self.assertContains(pt, "Entendimento")
        self.assertContains(pt, "Inserido no catálogo")
        self.assertContains(pt, "Fecha a conversa")
        self.assertContains(pt, "Expressar satisfação")
        self.assertContains(pt, "missing-item-arrow-neutral")
        self.assertContains(pt, "missing-item-star-on")
        self.assertContains(
            pt,
            "Não é uma encomenda — uma conversa que fecha quando o artigo entra para o catálogo.",
        )
        self.assertNotContains(pt, "Não está na lista")
        self.assertNotContains(pt, ">Conversa</text>")
        self.assertNotContains(pt, "ThreadReadState")
        self.assertNotContains(pt, "/branch/threads/")
        self.assertNotContains(pt, "Pedido normal")
        self.assertNotContains(pt, "Quando falta algo")

    def test_language_switcher_links(self):
        pt = self.client.get("/presentation/pt/")
        self.assertContains(pt, 'href="/presentation/en/"')
        en = self.client.get("/presentation/en/")
        self.assertContains(en, 'href="/presentation/pt/"')

    def test_presentation_static_assets_referenced(self):
        response = self.client.get("/presentation/en/")
        self.assertContains(response, "presentation/css/deck.css")
        self.assertContains(response, "presentation/js/deck.js")

    def test_presentation_demo_login_slide(self):
        self.assertEqual(SLIDE_COUNT, 17)
        en = self.client.get("/presentation/en/")
        self.assertContains(en, 'data-slide="17"')
        self.assertContains(en, "Log in and explore")
        self.assertContains(en, "Browser warning expected")
        self.assertContains(en, DEMO_LOGIN_URL)
        self.assertContains(en, DEMO_PASSWORD)
        self.assertContains(en, "armazem.admin@centcompras.dev")
        self.assertContains(en, "filial.dual@centcompras.dev")
        pt = self.client.get("/presentation/pt/")
        self.assertContains(pt, "Experimente agora")
        self.assertContains(pt, "Aviso do browser esperado")
        self.assertContains(pt, DEMO_PASSWORD)
