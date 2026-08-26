from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from accounts.groups import GROUP_ADMINS, assign_warehouse_group
from products.models import FamilyProduct, Item, SubFamily, Supplier, SupplierItemPrice, VatRate

from .capabilities import (
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_OPERATOR,
    branch_role,
    is_branch_member,
)
from .middleware import ActiveBranchMiddleware
from .models import Branch, BranchMembership
from .services import (
    SESSION_KEY,
    DuplicateBranchNameError,
    InvalidBranchRoleError,
    assign_membership,
    create_branch,
    get_active_branch,
    get_active_memberships,
    get_memberships,
    post_login_landing,
    post_login_redirect,
    set_active_branch,
)


def _make_user(email):
    return get_user_model().objects.create_user(email=email, password="test-pass-123")


def _make_catalog_item(family, vat, description, quantity=0, reorder=0, code="", active=True):
    return Item.objects.create(
        family=family,
        vat_rate=vat,
        description=description,
        internal_code=code,
        unit_of_measure=Item.UnitOfMeasure.PIECE,
        quantity=quantity,
        reorder_level=reorder,
        is_active=active,
        retail_price=Decimal("10.00"),
        wholesale_price=Decimal("5.00"),
        special_price=Decimal("8.00"),
    )


class BranchModelTests(TestCase):
    def test_branch_name_is_case_insensitive_unique(self):
        create_branch("North")
        with self.assertRaises(DuplicateBranchNameError):
            create_branch("north")

    def test_membership_is_unique_per_user_branch(self):
        branch = create_branch("North")
        user = _make_user("member@example.com")
        assign_membership(user, branch, ROLE_OPERATOR)

        # A second row for the same user+branch is rejected at the DB level.
        with self.assertRaises(Exception):
            BranchMembership.objects.create(user=user, branch=branch, role=ROLE_MANAGER)

    def test_membership_defaults_to_operator(self):
        branch = create_branch("North")
        user = _make_user("op@example.com")
        membership = BranchMembership.objects.create(user=user, branch=branch)
        self.assertEqual(membership.role, ROLE_OPERATOR)

    def test_assign_membership_rejects_unknown_role(self):
        branch = create_branch("North")
        user = _make_user("bad@example.com")
        with self.assertRaises(InvalidBranchRoleError):
            assign_membership(user, branch, "owner")


class BranchServiceTests(TestCase):
    def setUp(self):
        self.branch = create_branch("North")
        self.other = create_branch("South")
        self.user = _make_user("svc@example.com")

    def test_assign_membership_upserts_role(self):
        assign_membership(self.user, self.branch, ROLE_OPERATOR)
        assign_membership(self.user, self.branch, ROLE_MANAGER)

        self.assertEqual(
            BranchMembership.objects.filter(user=self.user, branch=self.branch).count(),
            1,
        )
        self.assertEqual(branch_role(self.user, self.branch), ROLE_MANAGER)

    def test_get_memberships_returns_none_for_anonymous(self):
        self.assertFalse(get_memberships(get_user_model()()).exists())

    def test_get_active_memberships_excludes_inactive_branch(self):
        assign_membership(self.user, self.branch, ROLE_OPERATOR)
        assign_membership(self.user, self.other, ROLE_OPERATOR)
        self.assertEqual(get_active_memberships(self.user).count(), 2)

        self.branch.is_active = False
        self.branch.save(update_fields=["is_active"])
        self.assertEqual(
            list(get_active_memberships(self.user).values_list("branch_id", flat=True)),
            [self.other.id],
        )

    def test_create_branch_rejects_blank_name(self):
        with self.assertRaises(ValidationError):
            create_branch("   ")


class PostLoginRedirectTests(TestCase):
    def setUp(self):
        self.north = create_branch("North")
        self.south = create_branch("South")

    def test_warehouse_user_goes_to_dashboard(self):
        user = _make_user("warehouse@example.com")
        assign_warehouse_group(user, GROUP_ADMINS)
        self.assertEqual(post_login_redirect(user), "/")

    def test_branch_only_single_membership_goes_to_dashboard(self):
        user = _make_user("single@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        self.assertEqual(post_login_redirect(user), "/branch/")

    def test_branch_only_multiple_memberships_goes_to_picker(self):
        user = _make_user("multi@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        assign_membership(user, self.south, ROLE_OPERATOR)
        self.assertEqual(post_login_redirect(user), "/branch/select/")

    def test_branch_only_zero_memberships_goes_to_picker(self):
        user = _make_user("none@example.com")
        self.assertEqual(post_login_redirect(user), "/branch/select/")

    def test_dual_warehouse_and_branch_goes_to_dashboard(self):
        user = _make_user("dual@example.com")
        assign_warehouse_group(user, GROUP_ADMINS)
        assign_membership(user, self.north, ROLE_OPERATOR)
        self.assertEqual(post_login_redirect(user), "/")

    def test_inactive_branch_not_counted_for_single_membership(self):
        user = _make_user("inactive-single@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        self.north.is_active = False
        self.north.save(update_fields=["is_active"])
        self.assertEqual(post_login_redirect(user), "/branch/select/")


class PostLoginLandingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.north = create_branch("North")
        self.south = create_branch("South")

    def _request(self, user):
        request = self.factory.get("/accounts/login/")
        request.user = user
        request.session = {}
        return request

    def test_single_membership_selects_branch(self):
        user = _make_user("landing-single@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        request = self._request(user)
        self.assertEqual(post_login_landing(request), "/branch/")
        self.assertEqual(request.session[SESSION_KEY], self.north.id)

    def test_multiple_memberships_do_not_select(self):
        user = _make_user("landing-multi@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        assign_membership(user, self.south, ROLE_OPERATOR)
        request = self._request(user)
        self.assertEqual(post_login_landing(request), "/branch/select/")
        self.assertNotIn(SESSION_KEY, request.session)

    def test_warehouse_user_does_not_select(self):
        user = _make_user("landing-warehouse@example.com")
        assign_warehouse_group(user, GROUP_ADMINS)
        request = self._request(user)
        self.assertEqual(post_login_landing(request), "/")
        self.assertNotIn(SESSION_KEY, request.session)


class CapabilityTests(TestCase):
    def setUp(self):
        self.branch = create_branch("North")
        self.user = _make_user("cap@example.com")

    def test_branch_role_none_without_membership(self):
        self.assertIsNone(branch_role(self.user, self.branch))
        self.assertFalse(is_branch_member(self.user))

    def test_branch_role_and_membership(self):
        assign_membership(self.user, self.branch, ROLE_ADMIN)
        self.assertEqual(branch_role(self.user, self.branch), ROLE_ADMIN)
        self.assertTrue(is_branch_member(self.user))

    def test_inactive_user_is_not_branch_member(self):
        assign_membership(self.user, self.branch, ROLE_OPERATOR)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertFalse(is_branch_member(self.user))


class ActiveBranchMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.branch = create_branch("North")
        self.user = _make_user("mw@example.com")
        assign_membership(self.user, self.branch, ROLE_OPERATOR)

    def _call(self, session):
        request = self.factory.get("/branch/catalog/")
        request.user = self.user
        request.session = session
        ActiveBranchMiddleware(lambda r: None)(request)
        return request

    def test_sets_active_branch_from_valid_session(self):
        request = self._call({SESSION_KEY: self.branch.id})
        self.assertEqual(request.active_branch, self.branch)

    def test_none_when_no_session_key(self):
        request = self._call({})
        self.assertIsNone(request.active_branch)

    def test_clears_session_when_membership_revoked(self):
        session = {SESSION_KEY: self.branch.id}
        BranchMembership.objects.filter(user=self.user).delete()
        request = self._call(session)
        self.assertIsNone(request.active_branch)
        self.assertNotIn(SESSION_KEY, session)

    def test_clears_session_when_branch_inactive(self):
        self.branch.is_active = False
        self.branch.save(update_fields=["is_active"])
        session = {SESSION_KEY: self.branch.id}
        request = self._call(session)
        self.assertIsNone(request.active_branch)
        self.assertNotIn(SESSION_KEY, session)


class ServiceWorkerTests(TestCase):
    def test_service_worker_served_at_root(self):
        response = self.client.get("/service-worker.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertContains(response, "centcompras-branch-v7")
        self.assertContains(response, "/api/")
        self.assertContains(response, "/manage/")
        self.assertContains(response, "CACHE_NAME")
        self.assertContains(response, "networkFirst")
        self.assertNotContains(response, "return cached || networkFetch")


class BranchViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.north = create_branch("North")
        self.south = create_branch("South")

    def _login(self, user):
        self.client.force_login(user)

    def test_picker_zero_memberships_shows_message(self):
        user = _make_user("zero@example.com")
        self._login(user)
        response = self.client.get(reverse("branch_select"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no active branch access")
        self.assertContains(response, 'id="settings-toggle"')

    def test_picker_single_membership_auto_selects(self):
        user = _make_user("single@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        self._login(user)
        response = self.client.get(reverse("branch_select"))
        self.assertRedirects(response, reverse("branch_dashboard"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], self.north.id)

    def test_picker_multiple_memberships_lists_branches(self):
        user = _make_user("multi@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        assign_membership(user, self.south, ROLE_MANAGER)
        self._login(user)
        response = self.client.get(reverse("branch_select"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.north.name)
        self.assertContains(response, self.south.name)
        self.assertContains(response, 'id="settings-toggle"')

    def test_picker_post_selects_branch(self):
        user = _make_user("post@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        assign_membership(user, self.south, ROLE_OPERATOR)
        self._login(user)
        response = self.client.post(
            reverse("branch_select"),
            {"branch_id": self.south.id},
        )
        self.assertRedirects(response, reverse("branch_dashboard"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], self.south.id)

    def test_picker_post_ignores_foreign_branch(self):
        foreign = create_branch("West")
        user = _make_user("foreign@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        assign_membership(user, self.south, ROLE_OPERATOR)
        self._login(user)
        response = self.client.post(reverse("branch_select"), {"branch_id": foreign.id})
        self.assertEqual(response.status_code, 200)  # re-renders picker, no crash

    def test_dashboard_requires_active_branch(self):
        user = _make_user("dash@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        self._login(user)
        response = self.client.get(reverse("branch_dashboard"))
        self.assertRedirects(response, reverse("branch_select"), fetch_redirect_response=False)

    def test_dashboard_renders_cards(self):
        user = _make_user("dash2@example.com")
        assign_membership(user, self.north, ROLE_MANAGER)
        self._login(user)
        session = self.client.session
        session[SESSION_KEY] = self.north.id
        session.save()
        response = self.client.get(reverse("branch_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.north.name)
        self.assertContains(response, 'href="/branch/catalog/"')
        self.assertContains(response, 'href="/branch/requests/"')
        self.assertContains(response, 'href="/branch/threads/"')
        self.assertContains(response, 'href="/branch/receipts/"')
        self.assertContains(response, 'href="/company-voice/"')
        self.assertContains(response, 'data-i18n="cardBranchCatalog"')
        self.assertNotContains(response, 'href="/branch/select/"')
        self.assertNotContains(response, "Switch branch")
        self.assertContains(response, "Manager")
        self.assertContains(response, "register_sw.js")
        self.assertContains(response, "branch_bootstrap.js")
        self.assertContains(response, 'data-branch-id="' + str(self.north.id) + '"')
        self.assertContains(response, 'data-user-id="' + str(user.id) + '"')

    def test_dashboard_shows_picker_for_multi_membership(self):
        user = _make_user("dash-multi@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        assign_membership(user, self.south, ROLE_OPERATOR)
        self._login(user)
        session = self.client.session
        session[SESSION_KEY] = self.north.id
        session.save()
        response = self.client.get(reverse("branch_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/branch/select/"')
        self.assertContains(response, "Switch branch")

    def test_catalog_requires_active_branch(self):
        user = _make_user("catalog@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        self._login(user)
        response = self.client.get(reverse("branch_catalog"))
        # No active branch in session -> redirect to picker
        self.assertRedirects(response, reverse("branch_select"), fetch_redirect_response=False)

    def test_catalog_renders_with_active_branch(self):
        user = _make_user("catalog2@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        self._login(user)
        session = self.client.session
        session[SESSION_KEY] = self.north.id
        session.save()
        response = self.client.get(reverse("branch_catalog"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.north.name)
        self.assertContains(response, 'id="settings-toggle"')
        self.assertNotContains(response, "Switch branch")
        self.assertContains(response, 'href="/branch/requests/"')
        self.assertContains(response, 'id="pref-language"')
        self.assertContains(response, 'id="pref-theme"')
        self.assertContains(response, "branch_catalog.js")
        self.assertContains(response, "register_sw.js")
        self.assertNotContains(response, 'id="language-select"')
        self.assertNotContains(response, 'id="theme-toggle"')

    def test_catalog_page_lists_price_columns(self):
        user = _make_user("catalog-page@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        self._login(user)
        session = self.client.session
        session[SESSION_KEY] = self.north.id
        session.save()
        response = self.client.get(reverse("branch_catalog"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wholesale")
        self.assertContains(response, "Sub-family")
        self.assertContains(response, "Availability")


class IsolationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = create_branch("North")

    def test_branch_user_cannot_open_warehouse_console(self):
        user = _make_user("branch-only@example.com")
        assign_membership(user, self.branch, ROLE_OPERATOR)
        self.client.force_login(user)
        response = self.client.get(reverse("item_console"))
        self.assertEqual(response.status_code, 403)

    def test_warehouse_user_cannot_open_branch_catalog(self):
        user = _make_user("warehouse-only@example.com")
        assign_warehouse_group(user, GROUP_ADMINS)
        self.client.force_login(user)
        response = self.client.get(reverse("branch_catalog"))
        self.assertEqual(response.status_code, 403)

    def test_branch_user_cannot_open_admin(self):
        user = _make_user("branch-admin@example.com")
        assign_membership(user, self.branch, ROLE_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse("admin:index"))
        self.assertIn(response.status_code, (302, 403))


class BranchCatalogApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = create_branch("North")
        self.user = _make_user("catalog-api@example.com")
        assign_membership(self.user, self.branch, ROLE_OPERATOR)
        self.vat = VatRate.objects.get(code="VAT16")
        self.family = FamilyProduct.objects.create(name="Branch Catalog", is_active=True)
        _make_catalog_item(self.family, self.vat, "None", quantity=0, reorder=0, code="NONE")
        _make_catalog_item(self.family, self.vat, "Low", quantity=3, reorder=5, code="LOW")
        ok_item = _make_catalog_item(self.family, self.vat, "OK", quantity=10, reorder=5, code="OK")
        _make_catalog_item(self.family, self.vat, "Inactive", quantity=10, reorder=0, code="OFF", active=False)
        supplier = Supplier.objects.create(name="Supplier A", is_active=True)
        SupplierItemPrice.objects.create(
            supplier=supplier, item=ok_item, cost_price=Decimal("3.00"), primary=True
        )

    def _select_branch(self):
        session = self.client.session
        session[SESSION_KEY] = self.branch.id
        session.save()

    def _login_and_select(self):
        self.client.force_login(self.user)
        self._select_branch()

    def test_returns_catalog_with_availability_hints(self):
        self._login_and_select()
        response = self.client.get(reverse("branch_catalog_list"))
        self.assertEqual(response.status_code, 200)
        rows = {r["internal_code"]: r for r in response.json()["catalog"]}
        self.assertEqual(rows["NONE"]["availability"], "none")
        self.assertEqual(rows["LOW"]["availability"], "low")
        self.assertEqual(rows["OK"]["availability"], "in stock")
        self.assertEqual(rows["NONE"]["sub_family"], "")
        self.assertEqual(rows["OK"]["sub_family"], "")

    def test_includes_sub_family_name_when_set(self):
        sub_family = SubFamily.objects.create(
            family=self.family,
            name="PPE",
            is_active=True,
        )
        ok_item = Item.objects.get(internal_code="OK")
        ok_item.sub_family = sub_family
        ok_item.save(update_fields=["sub_family"])
        self._login_and_select()

        rows = {
            r["internal_code"]: r
            for r in self.client.get(reverse("branch_catalog_list")).json()["catalog"]
        }

        self.assertEqual(rows["OK"]["sub_family"], "PPE")
        self.assertEqual(rows["NONE"]["sub_family"], "")

    def test_omits_cost_and_exact_stock(self):
        self._login_and_select()
        rows = self.client.get(reverse("branch_catalog_list")).json()["catalog"]
        for row in rows:
            self.assertNotIn("buying_price", row)
            self.assertNotIn("cost_price", row)
            self.assertNotIn("suppliers", row)
            self.assertNotIn("quantity", row)
            self.assertNotIn("reorder_level", row)

    def test_excludes_inactive_items(self):
        self._login_and_select()
        rows = self.client.get(reverse("branch_catalog_list")).json()["catalog"]
        codes = {r["internal_code"] for r in rows}
        self.assertIn("OK", codes)
        self.assertNotIn("OFF", codes)

    def test_warehouse_user_forbidden(self):
        wuser = _make_user("catalog-api-warehouse@example.com")
        assign_warehouse_group(wuser, GROUP_ADMINS)
        self.client.force_login(wuser)
        response = self.client.get(reverse("branch_catalog_list"))
        self.assertEqual(response.status_code, 403)

    def test_branch_user_without_active_branch_forbidden(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("branch_catalog_list"))
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_returns_401(self):
        response = self.client.get(reverse("branch_catalog_list"))
        self.assertEqual(response.status_code, 401)

    def test_fully_reserved_stock_shows_none(self):
        from orders import services as order_services

        ok_item = Item.objects.get(internal_code="OK")
        manager = _make_user("hint-mgr@example.com")
        assign_membership(manager, self.branch, ROLE_MANAGER)
        req = order_services.create_internal_request(self.branch, self.user)
        order_services.add_line(req, ok_item, "10", self.user)
        req = order_services.submit(req, self.user)
        order_services.approve(req, manager)

        self._login_and_select()
        rows = {r["internal_code"]: r for r in self.client.get(reverse("branch_catalog_list")).json()["catalog"]}
        self.assertEqual(rows["OK"]["availability"], "none")
        self.assertNotIn("quantity", rows["OK"])


class LoginRedirectTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.north = create_branch("North")
        self.south = create_branch("South")

    def _login(self, email, password="test-pass-123"):
        return self.client.post(
            reverse("login"),
            {"username": email, "password": password},
        )

    def test_branch_only_single_membership_redirects_to_dashboard(self):
        user = _make_user("login-single@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        response = self._login(user.email)
        self.assertRedirects(response, reverse("branch_dashboard"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], self.north.id)

    def test_branch_only_multiple_memberships_redirects_to_picker(self):
        user = _make_user("login-multi@example.com")
        assign_membership(user, self.north, ROLE_OPERATOR)
        assign_membership(user, self.south, ROLE_OPERATOR)
        response = self._login(user.email)
        self.assertRedirects(response, reverse("branch_select"), fetch_redirect_response=False)

    def test_warehouse_user_redirects_to_dashboard(self):
        user = _make_user("login-warehouse@example.com")
        assign_warehouse_group(user, GROUP_ADMINS)
        response = self._login(user.email)
        self.assertRedirects(response, "/", fetch_redirect_response=False)
