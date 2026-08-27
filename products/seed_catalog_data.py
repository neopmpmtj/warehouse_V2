"""Structured dev seed data for items, families, and suppliers (pt-PT demo)."""

FAMILIES = (
    {"name": "Cimento", "is_active": True},
    {"name": "Agregados", "is_active": True},
    {"name": "Tubos", "is_active": True},
    {"name": "Aço", "is_active": True},
    {"name": "Madeira", "is_active": True},
    {"name": "Ferramentas", "is_active": True},
    {"name": "Material elétrico", "is_active": True},
    {"name": "Canalização", "is_active": True},
    {"name": "Tintas", "is_active": True},
    {"name": "Segurança", "is_active": True},
    {"name": "Fixações", "is_active": True},
    {"name": "Diversos", "is_active": True},
    {"name": "Stock legado", "is_active": False},
)

# name, parent family (skip inactive families such as Stock legado)
SUB_FAMILIES = (
    {"name": "Sacos", "family": "Cimento"},
    {"name": "Granel", "family": "Cimento"},
    {"name": "Aço", "family": "Tubos"},
    {"name": "PVC", "family": "Tubos"},
    {"name": "Cabos", "family": "Material elétrico"},
    {"name": "EPI", "family": "Segurança"},
)

# internal_code, sub_family name, family name
ITEM_SUB_FAMILIES = (
    ("CEM-50", "Sacos", "Cimento"),
    ("PIPE-20", "Aço", "Tubos"),
    ("PIPE-50", "PVC", "Tubos"),
    ("CABLE-2.5", "Cabos", "Material elétrico"),
    ("GLOVES-L", "EPI", "Segurança"),
)

SUPPLIERS = (
    {
        "name": "ConstruSupply Lda",
        "phone": "+351 210 000 001",
        "contact_name": "Ana Ribeiro",
        "email": "sales@buildsupply.dev",
        "is_active": True,
    },
    {
        "name": "Materiais do Porto SA",
        "email": "sales@portomaterials.dev",
        "contact_name": "Carlos Mendes",
        "is_active": True,
    },
    {
        "name": "Cimentos Nacionais",
        "phone": "+351 220 000 002",
        "contact_name": "Balcão de armazém",
        "is_active": True,
    },
    {
        "name": "Comércio Ibérico de Aço",
        "phone": "+351 221 000 003",
        "contact_name": "João Silva",
        "is_active": True,
    },
    {
        "name": "Madeiras do Norte",
        "email": "orders@nortetimber.dev",
        "is_active": True,
    },
    {
        "name": "ElectroPorto",
        "phone": "+351 222 000 004",
        "contact_name": "Maria Costa",
        "is_active": True,
    },
    {
        "name": "AquaFlow Canalização",
        "email": "supply@aquaflow.dev",
        "is_active": True,
    },
    {
        "name": "ColorWorks Tintas",
        "phone": "+351 223 000 005",
        "is_active": True,
    },
    {
        "name": "SafeGuard Equipamentos",
        "contact_name": "Pedro Alves",
        "is_active": True,
    },
    {
        "name": "FixAll Fixações",
        "email": "bulk@fixall.dev",
        "is_active": True,
    },
    {
        "name": "Fornecedores Antigos Lda",
        "notes": "Inativo — não encomendar",
        "is_active": False,
    },
    {
        "name": "Negócios de Armazém Encerrados",
        "notes": "Empresa encerrada",
        "is_active": False,
    },
)

# supplier_name, internal_code, cost_price, primary (secondary rows only — primary at Genesis)
SUPPLIER_ITEM_PRICES = (
    ("ConstruSupply Lda", "CEM-50", "8.75", False),
    ("ConstruSupply Lda", "STEEL-8", "2.40", False),
    ("Materiais do Porto SA", "GRAVEL-10", "1.20", False),
    ("Comércio Ibérico de Aço", "STEEL-6", "1.85", False),
    ("Madeiras do Norte", "TIMBER-PLY", "12.50", False),
    ("ElectroPorto", "SOCKET", "1.40", False),
    ("AquaFlow Canalização", "TAP-CHROME", "18.90", False),
    ("ColorWorks Tintas", "PAINT-RED", "8.20", False),
    ("SafeGuard Equipamentos", "HELMET", "4.60", False),
    ("FixAll Fixações", "SCREW-50", "1.15", False),
)

# Default primary supplier per family for Genesis (active items)
FAMILY_PRIMARY_SUPPLIER = {
    "Cimento": "Cimentos Nacionais",
    "Agregados": "Materiais do Porto SA",
    "Tubos": "ConstruSupply Lda",
    "Aço": "Comércio Ibérico de Aço",
    "Madeira": "Madeiras do Norte",
    "Ferramentas": "ConstruSupply Lda",
    "Material elétrico": "ElectroPorto",
    "Canalização": "AquaFlow Canalização",
    "Tintas": "ColorWorks Tintas",
    "Segurança": "SafeGuard Equipamentos",
    "Fixações": "FixAll Fixações",
    "Diversos": "ConstruSupply Lda",
    "Stock legado": "ConstruSupply Lda",
}

# internal_code -> (supplier_name, cost_price) overrides for Genesis primary
ITEM_PRIMARY_SUPPLIER = {
    "CEM-50": ("Cimentos Nacionais", "8.50"),
    "PIPE-20": ("ConstruSupply Lda", "3.10"),
    "SAND-1KG": ("Materiais do Porto SA", "0.90"),
    "STEEL-10": ("Comércio Ibérico de Aço", "2.90"),
    "TIMBER-2X4": ("Madeiras do Norte", "2.15"),
    "CABLE-2.5": ("ElectroPorto", "28.00"),
    "VALVE-15": ("AquaFlow Canalização", "2.60"),
    "PAINT-WHITE": ("ColorWorks Tintas", "16.40"),
    "GLOVES-L": ("SafeGuard Equipamentos", "1.95"),
    "BOLT-M8": ("FixAll Fixações", "0.55"),
}

# internal_code, description, family, unit, reorder_level, is_active, vat_rate_code
ITEMS = (
    ("CEM-50", "Cimento 50 kg", "Cimento", "kg", "20", True, "VAT16"),
    ("CEM-25", "Cimento 25 kg", "Cimento", "kg", "15", True, "VAT16"),
    ("CEM-40", "Cimento 40 kg rápido", "Cimento", "kg", "25", True, "VAT16"),
    ("CEM-WHITE", "Cimento branco 25 kg", "Cimento", "kg", "10", True, "VAT16"),
    ("CEM-OLD", "Saco de cimento descontinuado", "Cimento", "kg", "0", False, "VAT16"),
    ("SAND-1KG", "Areia 1 kg", "Agregados", "kg", "50", True, "VAT16"),
    ("GRAVEL-10", "Brita 10 mm a granel", "Agregados", "kg", "30", True, "VAT16"),
    ("GRAVEL-20", "Brita 20 mm a granel", "Agregados", "kg", "40", True, "VAT16"),
    ("SAND-FINE", "Areia fina saco 25 kg", "Agregados", "kg", "0", True, "VAT16"),
    ("SAND-OLD", "Stock antigo de areia", "Agregados", "kg", "0", False, "VAT16"),
    ("PIPE-20", "Tubo de aço 20 mm", "Tubos", "m", "20", True, "VAT16"),
    ("PIPE-32", "Tubo de aço 32 mm", "Tubos", "m", "15", True, "VAT16"),
    ("PIPE-50", "Tubo PVC 50 mm", "Tubos", "m", "25", True, "VAT16"),
    ("PIPE-OLD", "Tubo obsoleto 15 mm", "Tubos", "m", "0", False, "VAT16"),
    ("STEEL-6", "Varão de aço 6 mm", "Aço", "m", "50", True, "VAT16"),
    ("STEEL-8", "Varão de aço 8 mm", "Aço", "m", "40", True, "VAT16"),
    ("STEEL-10", "Varão de aço 10 mm", "Aço", "m", "30", True, "VAT16"),
    ("STEEL-PLATE", "Chapa de aço 2 mm", "Aço", "m2", "10", True, "VAT16"),
    ("STEEL-OLD", "Varão de aço 12 mm enferrujado", "Aço", "m", "0", False, "VAT16"),
    ("TIMBER-2X4", "Madeira 2x4 3 m", "Madeira", "m", "15", True, "VAT16"),
    ("TIMBER-2X6", "Madeira 2x6 3 m", "Madeira", "m", "10", True, "VAT16"),
    ("TIMBER-PLY", "Folha de contraplacado 12 mm", "Madeira", "m2", "8", True, "VAT16"),
    ("TIMBER-OLD", "Feixe de madeira danificada", "Madeira", "m", "0", False, "VAT16"),
    ("HAMMER", "Martelo de unha 500 g", "Ferramentas", "piece", "5", True, "VAT16"),
    ("DRILL-18", "Conjunto de brocas 18 peças", "Ferramentas", "piece", "3", True, "VAT16"),
    ("SAW-CIRC", "Disco de serra circular 190 mm", "Ferramentas", "piece", "8", True, "VAT16"),
    ("LEVEL-60", "Nível de bolha 60 cm", "Ferramentas", "piece", "0", True, "VAT16"),
    ("TOOL-OLD", "Conjunto de cinzéis partidos", "Ferramentas", "piece", "0", False, "VAT16"),
    ("CABLE-2.5", "Cabo 2,5 mm 100 m", "Material elétrico", "m", "20", True, "VAT16"),
    ("CABLE-1.5", "Cabo 1,5 mm 100 m", "Material elétrico", "m", "15", True, "VAT16"),
    ("SOCKET", "Tomada dupla branca", "Material elétrico", "piece", "20", True, "VAT16"),
    ("SWITCH-1G", "Interruptor 1 tecla", "Material elétrico", "piece", "0", True, "VAT16"),
    ("ELEC-OLD", "Quadro elétrico antigo", "Material elétrico", "piece", "0", False, "VAT16"),
    ("VALVE-15", "Válvula de esfera 15 mm", "Canalização", "piece", "10", True, "VAT16"),
    ("TAP-CHROME", "Torneira misturadora cromada", "Canalização", "piece", "12", True, "VAT16"),
    ("FIT-90", "Joelho 90° 20 mm", "Canalização", "piece", "50", True, "VAT16"),
    ("PIPE-PEX", "Tubo PEX 16 mm", "Canalização", "m", "0", True, "VAT16"),
    ("PLUMB-OLD", "Stock de torneiras com fugas", "Canalização", "piece", "0", False, "VAT16"),
    ("PAINT-WHITE", "Tinta interior branca 10 L", "Tintas", "l", "8", True, "VAT16"),
    ("PAINT-GRAY", "Tinta exterior cinzenta 10 L", "Tintas", "l", "6", True, "VAT16"),
    ("PAINT-RED", "Tinta para metal vermelha 2,5 L", "Tintas", "l", "10", True, "VAT16"),
    ("PAINT-PRIMER", "Primário para madeira 5 L", "Tintas", "l", "0", True, "VAT16"),
    ("PAINT-OLD", "Balde de tinta expirada", "Tintas", "l", "0", False, "VAT16"),
    ("GLOVES-L", "Luvas de trabalho tamanho L", "Segurança", "piece", "30", True, "VAT16"),
    ("HELMET", "Capacete de segurança amarelo", "Segurança", "piece", "10", True, "VAT16"),
    ("GOGGLES", "Óculos de proteção transparentes", "Segurança", "piece", "15", True, "VAT16"),
    ("VEST-HIVIS", "Colete refletor laranja", "Segurança", "piece", "0", True, "VAT16"),
    ("SAFE-OLD", "Lote de luvas rasgadas", "Segurança", "piece", "0", False, "VAT16"),
    ("BOLT-M8", "Parafuso M8 x 50 embalagem 100", "Fixações", "piece", "20", True, "VAT16"),
    ("NUT-M8", "Porca M8 embalagem 100", "Fixações", "piece", "25", True, "VAT16"),
    ("SCREW-50", "Parafusos para madeira 50 mm caixa", "Fixações", "piece", "30", True, "VAT16"),
    ("WASHER-M8", "Anilha M8 embalagem 100", "Fixações", "g", "0", True, "VAT16"),
    ("FAST-OLD", "Mistura de parafusos enferrujados", "Fixações", "piece", "0", False, "VAT16"),
    ("TAPE-DUCT", "Fita adesiva 50 m", "Diversos", "piece", "10", True, "VAT16"),
    ("GLUE-EPOXY", "Cola epóxi bicomponente", "Diversos", "piece", "0", True, "VAT16"),
    ("ROPE-10", "Corda de polipropileno 10 mm 50 m", "Diversos", "m", "5", True, "VAT16"),
    ("CEMENT-MIX", "Betão pronto 25 kg", "Diversos", "kg", "20", True, "VAT16"),
    ("MISC-OLD", "Lote de ferragens desconhecidas", "Diversos", "piece", "0", False, "VAT16"),
    ("LEG-001", "Artigo legado A", "Stock legado", "piece", "0", True, "VAT_EXEMPT"),
    ("LEG-002", "Artigo legado B", "Stock legado", "piece", "0", True, "VAT_EXEMPT"),
    ("LEG-003", "Artigo legado C", "Stock legado", "kg", "0", True, "VAT_EXEMPT"),
)


def genesis_primary_for_item(internal_code, family_name):
    """Return (supplier_name, cost_price str) for active item Genesis seeding."""
    from decimal import Decimal

    key = (internal_code or "").upper()
    override = ITEM_PRIMARY_SUPPLIER.get(key)
    if override is not None:
        return override
    supplier = FAMILY_PRIMARY_SUPPLIER[family_name]
    total = sum(ord(ch) for ch in internal_code)
    cost = (Decimal("1") + Decimal(total % 499) / Decimal("100")).quantize(
        Decimal("0.01")
    )
    return supplier, str(cost)
