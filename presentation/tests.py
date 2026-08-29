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
        self.assertContains(response, "thread-circuit-diagram")
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
