from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from accounts.groups import (
    GROUP_ADMINS,
    WAREHOUSE_USERS,
    assign_warehouse_group,
    set_warehouse_grade,
)
from accounts.models import DEFAULT_USER_TIMEZONE
from branches.models import Branch, BranchMembership
from branches.services import assign_membership, create_branch
from products.models import (
    FamilyProduct,
    Item,
    SubFamily,
    Supplier,
    SupplierItemPrice,
    SupplierItemPriceChangeLog,
    VatRate,
)
from products.seed_catalog_data import (
    FAMILIES,
    ITEMS,
    ITEM_SUB_FAMILIES,
    SUB_FAMILIES,
    SUPPLIERS,
    SUPPLIER_ITEM_PRICES,
    genesis_primary_for_item,
)
from products.services import (
    create_and_activate_item,
    create_family,
    create_item,
    create_sub_family,
    create_supplier,
    create_supplier_item_price,
    update_family,
    update_item,
    update_supplier,
    update_supplier_item_price,
)
from procurement.services import ensure_default_approval_limits
from orders import services as order_services
from orders.models import InternalRequest
from orders.services import ensure_default_branch_approval_limits
from threads.services import create_thread as create_request_thread
from company_voice.services import add_comment as add_voice_comment
from company_voice.services import create_post as create_voice_post


DEFAULT_PASSWORD = "devpass123"

BRANCH_SEED = [
    (
        "Norte",
        [
            ("filial.operador.norte@centcompras.dev", BranchMembership.Role.OPERATOR),
            ("filial.gestor.norte@centcompras.dev", BranchMembership.Role.MANAGER),
            ("filial.admin.norte@centcompras.dev", BranchMembership.Role.ADMIN),
        ],
    ),
    (
        "Sul",
        [
            ("filial.operador.sul@centcompras.dev", BranchMembership.Role.OPERATOR),
            ("filial.gestor.sul@centcompras.dev", BranchMembership.Role.MANAGER),
        ],
    ),
]

DUAL_BRANCH_MEMBERSHIPS = [
    ("Norte", "filial.dual@centcompras.dev", BranchMembership.Role.OPERATOR),
    ("Sul", "filial.dual@centcompras.dev", BranchMembership.Role.OPERATOR),
]

COST_TRENDS_DEMO_CODE = "CEM-50"
COST_TRENDS_DEMO_COSTS = (
    Decimal("8.50"),
    Decimal("8.75"),
    Decimal("9.10"),
    Decimal("9.45"),
)
COST_TRENDS_DEMO_DAYS_AGO = (120, 90, 60, 30)


def _demo_selling_prices(internal_code):
    total = sum(ord(ch) for ch in internal_code)
    retail = Decimal(10) + (total % 91)
    wholesale = (retail * Decimal("0.80")).quantize(Decimal("0.01"))
    special = (retail * Decimal("0.65")).quantize(Decimal("0.01"))
    return retail, wholesale, special


class Command(BaseCommand):
    help = (
        "Seed local dev data: warehouse users (grades + groups), families, "
        "suppliers, and ~50 items (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for seeded warehouse users (default: {DEFAULT_PASSWORD})",
        )
        parser.add_argument(
            "--skip-items",
            action="store_true",
            help="Only seed the warehouse users.",
        )
        parser.add_argument(
            "--skip-products",
            action="store_true",
            dest="skip_items",
            help="Deprecated alias for --skip-items.",
        )
        parser.add_argument(
            "--skip-warehouse",
            action="store_true",
            help="Do not create warehouse users.",
        )
        parser.add_argument(
            "--skip-branches",
            action="store_true",
            help="Do not create branches or branch users.",
        )

    def _seed_branch_user(self, user_model, branch, email, role, password):
        user, created = user_model.objects.get_or_create(
            email=email,
            defaults={
                "is_staff": False,
                "is_superuser": False,
                "timezone": DEFAULT_USER_TIMEZONE,
            },
        )
        changed_fields = []
        if user.is_staff or user.is_superuser:
            user.is_staff = False
            user.is_superuser = False
            changed_fields.extend(["is_staff", "is_superuser"])
        if not user.timezone:
            user.timezone = DEFAULT_USER_TIMEZONE
            changed_fields.append("timezone")
        if created or not user.check_password(password):
            user.set_password(password)
            changed_fields.append("password")
        if changed_fields:
            user.save(update_fields=changed_fields)
        assign_membership(user, branch, role)
        self.stdout.write(
            self.style.SUCCESS(
                f"Branch user: {user.email} ({branch.name}, {role})"
            )
        )
        return user

    def _ensure_genesis_primary(
        self,
        warehouse_user,
        item,
        internal_code,
        family_name,
        suppliers_by_name,
    ):
        if SupplierItemPrice.objects.filter(item=item, primary=True).exists():
            return
        supplier_name, cost_price = genesis_primary_for_item(
            internal_code,
            family_name,
        )
        supplier = suppliers_by_name.get(supplier_name.casefold())
        if supplier is None:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipping primary for {internal_code}: supplier "
                    f"'{supplier_name}' not found"
                )
            )
            return
        existing = SupplierItemPrice.objects.filter(
            supplier=supplier,
            item=item,
        ).first()
        if existing:
            update_supplier_item_price(
                existing,
                user=warehouse_user,
                cost_price=cost_price,
                primary=True,
            )
            return
        create_supplier_item_price(
            supplier=supplier,
            item=item,
            cost_price=cost_price,
            primary=True,
            user=warehouse_user,
        )

    def _cost_logs_for_sip(self, sip):
        logs = []
        for log in sip.change_logs.order_by("created_at", "id"):
            if log.action == SupplierItemPriceChangeLog.Action.CREATED:
                logs.append(log)
            elif log.changes.get("cost_price"):
                logs.append(log)
        return logs

    def _backdate_cost_trends_logs(self, logs):
        now = timezone.now()
        for log, days in zip(logs, COST_TRENDS_DEMO_DAYS_AGO):
            SupplierItemPriceChangeLog.objects.filter(pk=log.pk).update(
                created_at=now - timedelta(days=days)
            )

    def _seed_cost_trends_demo(self, warehouse_user, items_by_code):
        """Backdated primary cost steps on CEM-50 for the cost-trends demo chart."""
        item = items_by_code.get(COST_TRENDS_DEMO_CODE.casefold())
        if item is None:
            return
        sip = (
            SupplierItemPrice.objects.filter(item=item, primary=True)
            .select_related("supplier")
            .first()
        )
        if sip is None:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipping cost trends demo: no primary price for {COST_TRENDS_DEMO_CODE}"
                )
            )
            return

        target_final = COST_TRENDS_DEMO_COSTS[-1]
        cost_logs = self._cost_logs_for_sip(sip)
        if len(cost_logs) >= len(COST_TRENDS_DEMO_COSTS) and sip.cost_price == target_final:
            self._backdate_cost_trends_logs(cost_logs[-len(COST_TRENDS_DEMO_COSTS) :])
            self.stdout.write(
                f"Cost trends demo: backdated {COST_TRENDS_DEMO_CODE} price history"
            )
            return

        try:
            start_idx = COST_TRENDS_DEMO_COSTS.index(sip.cost_price)
        except ValueError:
            start_idx = -1
        for cost in COST_TRENDS_DEMO_COSTS[start_idx + 1 :]:
            update_supplier_item_price(
                sip,
                user=warehouse_user,
                cost_price=cost,
            )
            sip.refresh_from_db()

        cost_logs = self._cost_logs_for_sip(sip)
        if len(cost_logs) < len(COST_TRENDS_DEMO_COSTS):
            self.stdout.write(
                self.style.WARNING(
                    f"Cost trends demo: expected {len(COST_TRENDS_DEMO_COSTS)} "
                    f"cost logs on {COST_TRENDS_DEMO_CODE}, found {len(cost_logs)}"
                )
            )
            return
        self._backdate_cost_trends_logs(cost_logs[-len(COST_TRENDS_DEMO_COSTS) :])
        self.stdout.write(
            f"Cost trends demo: seeded {COST_TRENDS_DEMO_CODE} price history"
        )

    def _seed_sample_requests(self, user_model):
        """Idempotently seed one draft + one approved requisição for fulfilment practice."""
        branch = Branch.objects.filter(name__iexact="Norte").first()
        if branch is None:
            return
        item = Item.objects.filter(
            is_active=True, family__is_active=True, wholesale_price__gt=0
        ).first()
        if item is None:
            return
        operator = user_model.objects.filter(
            email="filial.operador.norte@centcompras.dev"
        ).first()
        manager = user_model.objects.filter(
            email="filial.gestor.norte@centcompras.dev"
        ).first()
        if operator is None or manager is None:
            return

        if not InternalRequest.objects.filter(branch=branch, status="draft").exists():
            req = order_services.create_internal_request(branch, operator, notes="Requisição rascunho de exemplo")
            order_services.add_line(req, item, "2", operator)
            self.stdout.write(self.style.SUCCESS(f"Sample draft requisição: #{req.id}"))

        if not InternalRequest.objects.filter(branch=branch, status="approved").exists():
            req = order_services.create_internal_request(branch, operator, notes="Requisição aprovada de exemplo")
            order_services.add_line(req, item, "5", operator)
            req = order_services.submit(req, operator)
            order_services.approve(req, manager)
            self.stdout.write(self.style.SUCCESS(f"Sample approved requisição: #{req.id}"))

    def _seed_sample_threads(self, user_model):
        """Idempotently seed one open request thread (catalogue-gap request)."""
        branch = Branch.objects.filter(name__iexact="Norte").first()
        if branch is None:
            return
        operator = user_model.objects.filter(
            email="filial.operador.norte@centcompras.dev"
        ).first()
        if operator is None:
            return
        subject = "Exemplo: válvula de latão 25 mm (não está no catálogo)"
        from threads.models import ItemRequestThread

        if not ItemRequestThread.objects.filter(branch=branch, subject=subject).exists():
            thread = create_request_thread(
                branch,
                operator,
                subject,
                "Precisamos de uma válvula de latão de 25 mm para a nova linha de rega. "
                "Ainda não está no catálogo — confirme se conseguem fornecer.",
            )
            self.stdout.write(self.style.SUCCESS(f"Sample request thread: #{thread.id}"))

    def _seed_company_voice(self, user_model):
        """Idempotently seed sample Company Voice posts."""
        from company_voice.models import VoicePost

        manager = user_model.objects.filter(
            email="armazem.gestor@centcompras.dev"
        ).first()
        branch_manager = user_model.objects.filter(
            email="filial.gestor.norte@centcompras.dev"
        ).first()
        if manager is None or branch_manager is None:
            return

        praise_body = (
            "Exemplo: o novo fluxo de reservas facilita muito ver o que está retido para as filiais."
        )
        if not VoicePost.objects.filter(body=praise_body).exists():
            post = create_voice_post(
                manager,
                praise_body,
                tag="praise",
                is_anonymous=False,
            )
            add_voice_comment(
                branch_manager,
                post,
                "Concordo — a indicação de stock disponível no catálogo da filial também ajuda.",
            )
            self.stdout.write(self.style.SUCCESS(f"Sample Company Voice post: #{post.id}"))

        concern_body = "Exemplo de preocupação anónima (seed) — continuem a melhorar a UX de receção na filial."
        if not VoicePost.objects.filter(body=concern_body).exists():
            anon_post = create_voice_post(
                branch_manager,
                concern_body,
                tag="concern",
                is_anonymous=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Sample anonymous Company Voice post: #{anon_post.id}"))

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        user_model = get_user_model()

        warehouse_user = None
        if not options["skip_warehouse"]:
            for email, group_name, grade in WAREHOUSE_USERS:
                user, created = user_model.objects.get_or_create(
                    email=email,
                    defaults={
                        "is_staff": False,
                        "is_superuser": False,
                        "timezone": DEFAULT_USER_TIMEZONE,
                    },
                )
                changed_fields = []
                if user.is_staff or user.is_superuser:
                    user.is_staff = False
                    user.is_superuser = False
                    changed_fields.extend(["is_staff", "is_superuser"])
                if not user.timezone:
                    user.timezone = DEFAULT_USER_TIMEZONE
                    changed_fields.append("timezone")
                if created or not user.check_password(password):
                    user.set_password(password)
                    changed_fields.append("password")
                if changed_fields:
                    user.save(update_fields=changed_fields)
                assign_warehouse_group(user, group_name)
                set_warehouse_grade(user, grade)
                if group_name == GROUP_ADMINS:
                    warehouse_user = user
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Warehouse user: {user.email} (group {group_name}, grade {grade})"
                    )
                )

        if not options["skip_branches"]:
            branches_by_name = {}
            for branch_name, _members in BRANCH_SEED:
                branch = Branch.objects.filter(name__iexact=branch_name).first()
                if branch is None:
                    branch = create_branch(branch_name, is_active=True)
                    self.stdout.write(
                        self.style.SUCCESS(f"Created branch: {branch.name}")
                    )
                else:
                    self.stdout.write(f"Exists branch: {branch.name}")
                branches_by_name[branch_name.casefold()] = branch

            for branch_name, members in BRANCH_SEED:
                branch = branches_by_name[branch_name.casefold()]
                for email, role in members:
                    self._seed_branch_user(user_model, branch, email, role, password)

            for branch_name, email, role in DUAL_BRANCH_MEMBERSHIPS:
                branch = branches_by_name[branch_name.casefold()]
                self._seed_branch_user(user_model, branch, email, role, password)

        if not options["skip_items"]:
            families_by_name = {}
            for family_data in FAMILIES:
                existing = FamilyProduct.objects.filter(
                    name__iexact=family_data["name"]
                ).first()
                if existing:
                    family = existing
                    # Keep active while seeding items under this family.
                    if not family.is_active:
                        family = update_family(family, is_active=True)
                    families_by_name[family_data["name"].casefold()] = family
                    self.stdout.write(f"Exists family: {family.name}")
                    continue

                # Create active first so items can be assigned; apply target
                # is_active after the item loop.
                family = create_family(family_data["name"], is_active=True)
                families_by_name[family_data["name"].casefold()] = family
                self.stdout.write(f"Created family: {family.name}")

            sub_families_by_key = {}
            for sub_family_data in SUB_FAMILIES:
                family = families_by_name[sub_family_data["family"].casefold()]
                existing = SubFamily.objects.filter(
                    family=family,
                    name__iexact=sub_family_data["name"],
                ).first()
                key = (
                    sub_family_data["family"].casefold(),
                    sub_family_data["name"].casefold(),
                )
                if existing:
                    sub_families_by_key[key] = existing
                    self.stdout.write(
                        f"Exists sub-family: {family.name} / {existing.name}"
                    )
                    continue

                sub_family = create_sub_family(
                    sub_family_data["name"],
                    family,
                    user=warehouse_user,
                )
                sub_families_by_key[key] = sub_family
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created sub-family: {family.name} / {sub_family.name}"
                    )
                )

            item_sub_family_by_code = {}
            for internal_code, sub_name, family_name in ITEM_SUB_FAMILIES:
                key = (family_name.casefold(), sub_name.casefold())
                sub_family = sub_families_by_key.get(key)
                if sub_family is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping sub-family assignment for {internal_code}: "
                            f"{family_name} / {sub_name} not found"
                        )
                    )
                    continue
                item_sub_family_by_code[internal_code.casefold()] = sub_family

            for supplier_data in SUPPLIERS:
                existing = Supplier.objects.filter(
                    name__iexact=supplier_data["name"]
                ).first()
                if existing:
                    supplier = existing
                    if supplier.is_active != supplier_data["is_active"]:
                        update_supplier(
                            supplier,
                            is_active=supplier_data["is_active"],
                        )
                    self.stdout.write(f"Exists supplier: {supplier.name}")
                    continue

                supplier = create_supplier(
                    name=supplier_data["name"],
                    contact_name=supplier_data.get("contact_name", ""),
                    email=supplier_data.get("email", ""),
                    phone=supplier_data.get("phone", ""),
                    notes=supplier_data.get("notes", ""),
                    is_active=supplier_data["is_active"],
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created supplier: {supplier.name}")
                )

            suppliers_by_name = {
                supplier.name.casefold(): supplier
                for supplier in Supplier.objects.all()
            }

            for row in ITEMS:
                (
                    internal_code,
                    description,
                    family_name,
                    unit,
                    reorder_level,
                    is_active,
                    vat_rate_code,
                ) = row
                family = families_by_name[family_name.casefold()]
                vat_rate = VatRate.objects.filter(code=vat_rate_code).first()
                if vat_rate is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping {internal_code}: VAT rate {vat_rate_code} not found"
                        )
                    )
                    continue

                retail, wholesale, special = _demo_selling_prices(internal_code)
                sub_family = item_sub_family_by_code.get(internal_code.casefold())
                existing = Item.objects.filter(internal_code__iexact=internal_code).first()
                if existing:
                    update_fields = {
                        "retail_price": retail,
                        "wholesale_price": wholesale,
                        "special_price": special,
                        "reason": "seed_dev_data",
                    }
                    if sub_family is not None:
                        update_fields["sub_family"] = sub_family
                    update_item(
                        warehouse_user,
                        existing,
                        **update_fields,
                    )
                    if is_active:
                        self._ensure_genesis_primary(
                            warehouse_user,
                            existing,
                            internal_code,
                            family_name,
                            suppliers_by_name,
                        )
                    self.stdout.write(
                        f"Exists item: {existing.internal_code} — {existing.description}"
                    )
                    continue

                if is_active:
                    supplier_name, cost_price = genesis_primary_for_item(
                        internal_code,
                        family_name,
                    )
                    supplier = suppliers_by_name.get(supplier_name.casefold())
                    if supplier is None:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping {internal_code}: supplier "
                                f"'{supplier_name}' not found"
                            )
                        )
                        continue
                    item = create_and_activate_item(
                        warehouse_user,
                        family=family,
                        description=description,
                        unit_of_measure=unit,
                        vat_rate=vat_rate,
                        supplier=supplier,
                        cost_price=cost_price,
                        internal_code=internal_code,
                        reorder_level=reorder_level,
                        retail_price=retail,
                        wholesale_price=wholesale,
                        special_price=special,
                        sub_family=sub_family,
                        reason="Genesis",
                    )
                else:
                    item = create_item(
                        user=warehouse_user,
                        family=family,
                        description=description,
                        unit_of_measure=unit,
                        vat_rate=vat_rate,
                        internal_code=internal_code,
                        reorder_level=reorder_level,
                        retail_price=retail,
                        wholesale_price=wholesale,
                        special_price=special,
                        sub_family=sub_family,
                        reason="seed_dev_data",
                    )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created item: {item.internal_code} — {item.description}"
                    )
                )

            for family_data in FAMILIES:
                family = families_by_name[family_data["name"].casefold()]
                family.refresh_from_db()
                if family.is_active != family_data["is_active"]:
                    update_family(family, is_active=family_data["is_active"])
                    self.stdout.write(
                        f"Family activity: {family.name} -> {family_data['is_active']}"
                    )

            items_by_code = {
                item.internal_code.casefold(): item
                for item in Item.objects.all()
            }

            for supplier_name, internal_code, cost_price, primary in SUPPLIER_ITEM_PRICES:
                supplier = suppliers_by_name.get(supplier_name.casefold())
                item = items_by_code.get(internal_code.casefold())
                if supplier is None or item is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping supplier price {supplier_name}/{internal_code}: not found"
                        )
                    )
                    continue

                existing_sip = SupplierItemPrice.objects.filter(
                    supplier=supplier, item=item
                ).first()
                if existing_sip:
                    update_fields = {"cost_price": cost_price}
                    if primary or not existing_sip.primary:
                        update_fields["primary"] = primary
                    update_supplier_item_price(
                        existing_sip,
                        user=warehouse_user,
                        **update_fields,
                    )
                else:
                    create_supplier_item_price(
                        supplier=supplier,
                        item=item,
                        cost_price=cost_price,
                        primary=primary,
                        user=warehouse_user,
                    )
                self.stdout.write(
                    f"Supplier price: {supplier.name} -> {item.internal_code} @ {cost_price}"
                )

            self._seed_cost_trends_demo(warehouse_user, items_by_code)

        ensure_default_approval_limits()
        ensure_default_branch_approval_limits()

        if not options["skip_branches"] and not options["skip_items"]:
            self._seed_sample_requests(user_model)
            self._seed_sample_threads(user_model)

        self._seed_company_voice(user_model)

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Dev login credentials:"))
        self.stdout.write(f"  Password: {password}")
        self.stdout.write("")
        self.stdout.write("Warehouse website (/ and /manage/items/) — not /admin/:")
        for email, group_name, grade in WAREHOUSE_USERS:
            self.stdout.write(f"  {email}  ({group_name}, grade {grade})")
        self.stdout.write("")
        self.stdout.write("Branch website (/branch/):")
        for branch_name, members in BRANCH_SEED:
            for email, role in members:
                self.stdout.write(f"  {email}  ({branch_name}, {role})")
        for branch_name, email, role in DUAL_BRANCH_MEMBERSHIPS:
            self.stdout.write(f"  {email}  ({branch_name}, {role})")
        self.stdout.write("")
        self.stdout.write(
            "Operators grade 1 are view-only; operator 2 and managers mutate the "
            "closed circuit. Managers grade 2+ can approve (caps on /manage/approval-limits/). "
            "Admins can approve anything, delete, and adjust stock."
        )
