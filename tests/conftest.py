import uuid
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from pytest_asyncio import is_async_test
from slowapi import Limiter
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from src.config import settings
from src.db.base import Base
from src.features.buyer.repository import BuyerRepository
from src.features.buyer.schema import (
    BrandCreateSchema,
    BrandType,
    BuyerContactCreateSchema,
    BuyerContactType,
    BuyerCreateSchema,
    BuyerType,
    SizeCreateSchema,
    SizeProfileCreateSchema,
)
from src.features.data_upload_suite.repository import S3UploadRepository
from src.features.device_management.models import (
    ConnectivityStatus,
    DeviceType,
    OperationalStatus,
    UserType,
)
from src.features.device_management.repository import DeviceRepository
from src.features.device_management.schema import DeviceCreateSchema
from src.features.factory.models import FactoryCategory, FactoryProcess
from src.features.factory.repository import FactoryRepository
from src.features.factory.schema import FactoryCreateSchema
from src.features.line.models import LineOperationalStatusEnum
from src.features.line.repository import LineRepository
from src.features.line.schema import LineCreateSchema
from src.features.machine.models import MachineCategory
from src.features.machine.repository import (
    FactoryMachineRepository,
    GenericMachineRepository,
)
from src.features.machine.schema import (
    FactoryMachineCreateSchema,
    GenericMachineCreateSchema,
)
from src.features.order.models import CostCategory, OrderStatus
from src.features.order.repository import OrderRepository
from src.features.order.schema import (
    CostingCreate,
    DestinationDueDateCreate,
    OrderDestinationCreate,
    OrderDestinationStyleCreate,
    OrderGarmentSizeCreate,
    OrderStyleCreate,
)
from src.features.qc_data_collection.schema import QcEventBatchSchema, QcEventSchema
from src.features.sector.models import SectorOperationalStatusEnum
from src.features.sector.repository import SectorRepository
from src.features.sector.schema import SectorCreateSchema
from src.features.shift.models import DaysOfWeek
from src.features.shift.repository import BreakRepository, ShiftRepository
from src.features.shift.schema import BreakCreateSchema, ShiftCreateSchema
from src.features.style.models import MaterialType
from src.features.style.repository import MaterialRepository, StyleRepository
from src.features.style.schema import MaterialDetailCreate, StyleCreate
from src.features.tenant.repository import TenantRepository
from src.features.tenant.schema import TenantProvisionSchema
from src.features.user.models import RoleType, User
from src.main import app
from src.middleware.rate_limit import get_identifier
from types import SimpleNamespace


DATABASE_URL = settings.DATABASE_URL

url = urlparse(DATABASE_URL)
db_host = url.hostname or "localhost"
db_port = url.port or 5432
db_user = url.username or "postgres"
db_password = url.password or ""


def pytest_collection_modifyitems(items):
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)


@pytest.fixture(scope="session")
async def test_database():
    test_db_name = f"test_db_{uuid.uuid4().hex[:8]}"

    postgres_db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/postgres"

    conn = await asyncpg.connect(postgres_db_url)

    try:
        await conn.execute(f"CREATE DATABASE {test_db_name}")

        test_db_url = (
            f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{test_db_name}"
        )

        yield test_db_url

    finally:
        await conn.execute(
            f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{test_db_name}'
            AND pid <> pg_backend_pid()
        """
        )
        await conn.execute(f"DROP DATABASE IF EXISTS {test_db_name}")
        await conn.close()


@pytest.fixture()
async def test_engine(test_database):
    engine = create_async_engine(test_database, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine):
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession, monkeypatch):
    """
    Create an async test client with proper database session sharing.

    This fixture stores the test db_session in app.state so the middleware
    can access it instead of creating its own session.
    """
    limiter = Limiter(
        key_func=get_identifier,
        default_limits=["1000/hour"],
    )

    app.state.limiter = limiter

    app.state.test_db_session = db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    if hasattr(app.state, "test_db_session"):
        delattr(app.state, "test_db_session")


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer mock_token_for_testing"}


@pytest.fixture
def mock_verify_jwt(monkeypatch, tenant, api_user):
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_testpool")

    def mock_verify(token: str):
        return {
            "sub": "test-user-id",
            "email": "test@example.com",
            "cognito:username": "testuser",
            "custom:tenant_id": str(tenant.id),
        }

    monkeypatch.setattr("src.middleware.user_context.verify_cognito_jwt", mock_verify)
    monkeypatch.setattr("src.auth.cognito.verify_cognito_jwt", mock_verify)


# ==================== BUYER FIXTURES ====================
@pytest.fixture
def buyer_repository(db_session):
    repo = BuyerRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def sample_buyer(tenant, factory):
    return BuyerCreateSchema(
        name="Test Buyer",
        code="TB-001",
        type=BuyerType.BRAND,
        tier=1,
        address_line_1="456 Buyer Street",
        city="Buyer City",
        state="Buyer State",
        country="Buyer Country",
        postal_code="12345",
        tenant_id=tenant.id,
        factory_id=factory.id,
    )


@pytest.fixture
def sample_buyer2(tenant, factory):
    return BuyerCreateSchema(
        name="Test Buyer2",
        code="TB-003",
        type=BuyerType.BRAND,
        tier=1,
        address_line_1="456 Buyer Street",
        city="Buyer City",
        state="Buyer State",
        country="Buyer Country",
        postal_code="12345",
        tenant_id=tenant.id,
        factory_id=factory.id,
    )


@pytest.fixture
async def buyer(sample_buyer2, buyer_repository):
    created_buyer = await buyer_repository.create(sample_buyer2)
    return created_buyer


# ==================== BUYER CONTACT FIXTURES ====================
@pytest.fixture
def sample_buyer_contact(buyer):
    return BuyerContactCreateSchema(
        contact_name="John Contact",
        contact_email="john@buyer.com",
        contact_phone="+1234567890",
        country_code="+1",
        type=BuyerContactType.PRIMARY,
        job_title="Procurement Manager",
        buyer_id=buyer.id,
    )


@pytest.fixture
async def buyer_contact(sample_buyer_contact, buyer_repository):
    created_contact = await buyer_repository.create_contact(sample_buyer_contact)
    return created_contact


# ==================== BRAND FIXTURES ====================
@pytest.fixture
def sample_brand(tenant, factory, buyer):
    return BrandCreateSchema(
        name="Test Brand",
        code="TB-BRAND-001",
        type=BrandType.DIRECT,
        tenant_id=tenant.id,
        factory_id=factory.id,
        buyer_id=buyer.id,
    )


@pytest.fixture
async def brand(sample_brand, buyer_repository):
    created_brand = await buyer_repository.create_brand(sample_brand)
    return created_brand


# ==================== SIZE PROFILE FIXTURES ====================
@pytest.fixture
def sample_size_profile(buyer, tenant):
    return SizeProfileCreateSchema(name="Standard Sizes", buyer_id=buyer.id, tenant_id=tenant.id)


@pytest.fixture
async def size_profile(sample_size_profile, buyer_repository):
    created_profile = await buyer_repository.create_size_profile(sample_size_profile)
    return created_profile


# ==================== SIZE FIXTURES ====================
@pytest.fixture
def sample_size(size_profile, tenant):
    return SizeCreateSchema(name="Medium", profile_id=size_profile.id, tenant_id=tenant.id)


@pytest.fixture
async def size(sample_size, buyer_repository):
    created_size = await buyer_repository.create_size(sample_size)
    return created_size


@pytest.fixture
def tenant_repository(db_session):
    repo = TenantRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def sample_tenant():
    return TenantProvisionSchema(
        name="Test Tenant Corp",
        description="A test tenant for testing",
        address="123 Test Street",
        city="Test City",
        state="Test State",
        country="Test Country",
        postal_code="12345",
        phone_number="+1234567890",
        country_code="+1",
        is_active=True,
    )


@pytest.fixture
async def tenant(sample_tenant, tenant_repository):
    tenant = await tenant_repository.create(sample_tenant)
    return tenant


@pytest.fixture
def factory_repository(db_session):
    repo = FactoryRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def factory_machine_repository(db_session):
    repo = FactoryMachineRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def generic_machine_repository(db_session):
    repo = GenericMachineRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def sample_factory(tenant):
    return FactoryCreateSchema(
        name="Test Factory",
        categories=[FactoryCategory.APPAREL],
        address="456 Industrial Ave",
        city="Factory City",
        state="Factory State",
        country="Factory Country",
        postal_code="54321",
        contact_name="John Doe",
        contact_phone_number="+1987654321",
        contact_email="contact@testfactory.com",
        country_code="+1",
        tenant_id=tenant.id,
    )


@pytest.fixture
async def factory(sample_factory, factory_repository):
    created_factory = await factory_repository.create(sample_factory)
    return created_factory


@pytest.fixture
def sample_generic_machine():
    return GenericMachineCreateSchema(
        name="Test Generic Machine",
        machine_code="TGM-001",
        min_rpm=1000,
        max_rpm=5000,
        min_spi=2.0,
        max_spi=6.0,
        category=MachineCategory.LOCKSTITCH_MACHINE,
    )


@pytest.fixture
async def generic_machine(sample_generic_machine, generic_machine_repository):
    return await generic_machine_repository.create(sample_generic_machine)


@pytest.fixture
def sample_factory_machine(tenant, factory, generic_machine):
    return FactoryMachineCreateSchema(
        name="Test Factory Machine",
        machine_code="TFM-001",
        factory_rpm=3000,
        factory_spi=4.5,
        base_machine_id=generic_machine.id,
        tenant_id=tenant.id,
        factory_id=factory.id,
    )


@pytest.fixture
async def factory_machine(factory_machine_repository, sample_factory_machine):
    return await factory_machine_repository.create(sample_factory_machine)


@pytest.fixture
async def operation(db_session, generic_machine):
    from src.features.style.models import Operation, OperationType

    op = Operation(
        name="Test Operation",
        type=OperationType.MAIN,
        code="OP-TEST-001",
        machine_id=generic_machine.id,
    )
    db_session.add(op)
    await db_session.commit()
    await db_session.refresh(op)
    return op


@pytest.fixture
async def line_layout(db_session, tenant, factory):
    from src.features.style.models import LineLayout

    layout = LineLayout(
        name="Summary Test Layout",
        factory_id=factory.id,
        total_operation_count=1,
        total_operator_count=1,
        machine_operator_count=1,
        helper_operator_count=0,
        man_level=1.0,
        sam=1.2,
        sam_efficiency_level=0.8,
        sam_hourly_production_target=60,
        tenant_id=tenant.id,
        machine_smv_sum=1.2,
        helper_smv_sum=0,
        total_stations=1,
    )
    db_session.add(layout)
    await db_session.commit()
    await db_session.refresh(layout)
    return layout


@pytest.fixture
async def station(db_session, tenant, factory, factory_machine, line_layout):
    from src.features.style.models import Station, StationType

    st = Station(
        name="Station 1",
        code="ST-01",
        description="First Station",
        sequence=1,
        total_target_smv=1.2,
        type=StationType.MACHINE_STATION,
        line_layout_id=line_layout.id,
        tenant_id=tenant.id,
        machine_id=factory_machine.id,
    )
    db_session.add(st)
    await db_session.commit()
    await db_session.refresh(st)
    return st


@pytest.fixture
async def station_operation(db_session, tenant, station, operation):
    from src.features.style.models import StationOperation

    st_op = StationOperation(
        station_id=station.id,
        operation_id=operation.id,
        smv_estimate=1.5,
        target_smv=1.2,
        tenant_id=tenant.id,
    )
    db_session.add(st_op)
    await db_session.commit()
    await db_session.refresh(st_op)
    return st_op


@pytest.fixture
def sector_repository(db_session):
    repo = SectorRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def sample_sector(tenant, factory, sector_processes):
    return SectorCreateSchema(
        name="Test Sector",
        description="A test sector for testing",
        sector_code="TEST-001",
        effective_start_date=datetime.now(),
        effective_end_date=datetime.now() + timedelta(days=365),
        floor_level=1,
        operational_status=SectorOperationalStatusEnum.ACTIVE,
        factory_id=factory.id,
        tenant_id=tenant.id,
        process_ids=[p.id for p in sector_processes],
    )


@pytest.fixture
async def sector(sample_sector, sector_repository):
    created_sector = await sector_repository.create(sample_sector)
    return created_sector


@pytest.fixture
async def sector_processes(db_session):
    from src.features.sector.models import SectorProcess

    processes = []
    for i in range(3):
        process = SectorProcess(name=f"Process {i}", description=f"Description for Process {i}")
        db_session.add(process)
        processes.append(process)

    await db_session.commit()
    return processes


@pytest.fixture
def line_repository(db_session):
    repo = LineRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def sample_line(tenant, factory, sector):
    return LineCreateSchema(
        name="Test Line",
        sequence_order=1,
        effective_start_date=datetime.now(timezone.utc),
        effective_end_date=datetime.now(timezone.utc) + timedelta(days=365),
        operational_status=LineOperationalStatusEnum.ACTIVE,
        sector_id=sector.id,
        factory_id=factory.id,
        tenant_id=tenant.id,
    )


@pytest.fixture
async def line(sample_line, line_repository):
    created_line = await line_repository.create(sample_line)
    return created_line


@pytest.fixture
async def process(db_session):
    process = FactoryProcess(
        name="Test Process",
        description="A test process for testing",
    )
    db_session.add(process)
    await db_session.commit()
    await db_session.refresh(process)
    return process


@pytest.fixture
def shift_repository(db_session):
    repo = ShiftRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def break_repository(db_session):
    repo = BreakRepository()
    repo.db = db_session
    return repo


@pytest.fixture
async def days_of_week(db_session):
    days = []
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for day_name in day_names:
        day = DaysOfWeek(name=day_name)
        db_session.add(day)
        days.append(day)

    await db_session.commit()

    for day in days:
        await db_session.refresh(day)

    return days


@pytest.fixture
def sample_shift(tenant, factory):
    return ShiftCreateSchema(
        name="Morning Shift",
        description="Standard morning shift",
        start_time=time(8, 0),
        end_time=time(16, 0),
        total_hours=8,
        factory_id=factory.id,
        tenant_id=tenant.id,
        days=[],
    )


@pytest.fixture
def sample_shift_with_days(tenant, factory, days_of_week):
    return ShiftCreateSchema(
        name="Weekday Shift",
        description="Monday and Tuesday shift",
        start_time=time(8, 0),
        end_time=time(16, 0),
        total_hours=8,
        factory_id=factory.id,
        tenant_id=tenant.id,
        days=["Monday", "Tuesday"],
    )


@pytest.fixture
async def shift(sample_shift, shift_repository):
    created_shift = await shift_repository.create(sample_shift)
    return created_shift


@pytest.fixture
def sample_break(shift, tenant, factory):
    return BreakCreateSchema(
        name="Lunch Break",
        description="30 minute lunch break",
        start_time=time(12, 0),
        end_time=time(12, 30),
        shift_id=shift.id,
        tenant_id=tenant.id,
    )


@pytest.fixture
async def api_user(db_session, tenant, factory):
    """Create a user directly in the database for API tests"""
    user = User(
        first_name="API",
        last_name="User",
        email="api.user@example.com",
        cognito_sub="test-user-id",
        tenant_id=tenant.id,
        factory_id=factory.id,
        country_code="+1",
        phone_number="5551234567",
        is_active=True,
    )

    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    return user


@pytest.fixture
def sample_role_data(api_user, tenant, factory):
    """Sample role data dict for API tests"""
    return {
        "title": "API Manager",
        "role": RoleType.OPERATIONS_MANAGER.value,
        "user_id": str(api_user.id),
        "tenant_id": str(tenant.id),
        "factory_id": str(factory.id),
        "line_ids": [],
        "sector_ids": [],
    }


@pytest.fixture
async def api_user_role(client, sample_role_data, mock_verify_jwt, auth_headers):
    """Create and return a user role via API"""
    response = await client.post("/api/v1/user-roles", json=sample_role_data, headers=auth_headers)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def style_repository(db_session):
    repo = StyleRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def material_repository(db_session):
    repo = MaterialRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def sample_style(tenant, factory, buyer, brand, size_profile):
    return StyleCreate(
        style_name="Test Style",
        buyer_id=buyer.id,
        brand_id=brand.id,
        size_profile_id=size_profile.id,
        factory_id=factory.id,
        tenant_id=tenant.id,
        garment_type="T-Shirt",
        garment_color="Blue",
        thread_color="White",
        process_cost=10.5,
        material_details=[
            MaterialDetailCreate(
                reference="MAT-001",
                supplier="Test Supplier",
                consumption_per_unit=1.5,
                unit_price=2.0,
                type=MaterialType.FABRIC,
            )
        ],
    )


@pytest.fixture
async def style(sample_style, style_repository):
    return await style_repository.create(sample_style)


# ==================== ORDER REPOSITORY FIXTURES ====================
@pytest.fixture
def order_repository(db_session):
    repo = OrderRepository()
    repo.db = db_session
    return repo


# ==================== STYLE FIXTURES ====================
@pytest.fixture
async def factory_style(db_session, tenant, factory, buyer, brand, size_profile):
    """Create a factory style for testing"""
    from src.features.style.models import FactoryStyle

    style = FactoryStyle(
        style_code="STYLE-001",
        style_name="Test Style",  # Note: it's 'style_name', not 'name'
        style_description="Test style for orders",
        garment_type="T-Shirt",
        garment_color="Blue",
        tenant_id=tenant.id,
        factory_id=factory.id,
        buyer_id=buyer.id,
        brand_id=brand.id,
        size_profile_id=size_profile.id,
    )
    db_session.add(style)
    await db_session.commit()
    await db_session.refresh(style)
    return style


# ==================== ORDER DESTINATION FIXTURES ====================
@pytest.fixture
def sample_order_destination():
    return OrderDestinationCreate(
        code="DEST-US-001",
        delivery_city="New York",
        delivery_state_province="NY",
        delivery_country="USA",
        delivery_zip="11011",
    )


@pytest.fixture
async def order_destination(db_session, tenant, sample_order_destination):
    """Create an order destination for testing"""
    from src.features.order.models import OrderDestination

    destination = OrderDestination(**sample_order_destination.model_dump(), tenant_id=tenant.id)
    db_session.add(destination)
    await db_session.commit()
    await db_session.refresh(destination)
    return destination


# ==================== ORDER SCHEMA FIXTURES ====================
@pytest.fixture
def sample_order_garment_size():
    return OrderGarmentSizeCreate(size="M", ratio=5)


@pytest.fixture
def sample_destination_due_date():
    return DestinationDueDateCreate(
        quantity=500, due_date=date.today() + timedelta(days=30), is_active=True
    )


@pytest.fixture
def sample_costing():
    return CostingCreate(
        name="Cotton Fabric",
        category=CostCategory.FABRIC,
        ref="FAB-001",
        origin="India",
        consumption_per_unit=2.5,
        quantity_used=1250.0,
        unit_price=5.50,
        total_amount=6875.00,
    )


@pytest.fixture
def sample_order_destination_style(
    order_destination, sample_destination_due_date, sample_order_garment_size
):
    return OrderDestinationStyleCreate(
        order_destination_id=order_destination.id,
        destination_code=order_destination.code,
        total_quantity=500,
        ratio_total=10,
        due_dates=[sample_destination_due_date],
        sizes=[sample_order_garment_size],
    )


@pytest.fixture
def sample_order_style(factory_style, sample_order_destination_style, sample_costing):
    return OrderStyleCreate(
        style_id=factory_style.id,
        destinations=[sample_order_destination_style],
        costings=[sample_costing],
    )


@pytest.fixture
def sample_order(tenant, factory, buyer, brand, sample_order_style, sample_order_destination):
    from src.features.order.schema import OrderCreateSchemaInternal

    return OrderCreateSchemaInternal(
        code="ORD-2024-001",
        name="Spring Collection Order",
        description="Spring 2024 collection",
        status=OrderStatus.INQUIRY,
        total_order_quantity=1000,
        total_order_value=50000.00,
        currency="USD",
        number_of_styles=1,
        factory_id=factory.id,
        buyer_id=buyer.id,
        brand_id=brand.id,
        order_styles=[sample_order_style],
        destinations=[sample_order_destination],
    )


@pytest.fixture
async def order(sample_order, order_repository, tenant):
    """Create a complete order for testing"""
    created_order = await order_repository.create(sample_order, tenant.id)
    return created_order


@pytest.fixture
def device_repository(db_session):
    repo = DeviceRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def sample_device(factory, sector, line):
    """Sample device data for testing"""
    return DeviceCreateSchema(
        device_name="Test Tablet Device",
        device_type=DeviceType.TABLET,
        user_type=UserType.OPERATOR,
        factory_id=factory.id,
        sector_id=sector.id,
        line_ids=[line.id],
        operational_status=OperationalStatus.ACTIVE,
        connectivity_status=ConnectivityStatus.OFFLINE,
    )


@pytest.fixture
def sample_device_tv(factory, sector, line):
    """Sample TV display device for testing"""
    return DeviceCreateSchema(
        device_name="Test TV Display",
        device_type=DeviceType.TV_DISPLAY,
        user_type=UserType.DISPLAY,
        factory_id=factory.id,
        sector_id=sector.id,
        line_ids=[line.id],
        operational_status=OperationalStatus.ACTIVE,
        connectivity_status=ConnectivityStatus.OFFLINE,
    )


@pytest.fixture
async def device(sample_device, device_repository, tenant):
    """Create a device for testing"""
    created_device = await device_repository.create(sample_device, tenant.id)
    return created_device


@pytest.fixture
async def device_tv(sample_device_tv, device_repository, tenant):
    """Create a TV display device for testing"""
    created_device = await device_repository.create(sample_device_tv, tenant.id)
    return created_device


@pytest.fixture
async def multiple_devices(sample_device, device_repository, tenant):
    """Create multiple devices for testing list operations"""
    devices = []
    for i in range(3):
        device_data = DeviceCreateSchema(
            device_name=f"Test Device {i+1}",
            device_type=DeviceType.TABLET if i % 2 == 0 else DeviceType.TV_DISPLAY,
            user_type=UserType.OPERATOR,
            factory_id=sample_device.factory_id,
            sector_id=sample_device.sector_id,
            line_ids=sample_device.line_ids,
            operational_status=OperationalStatus.ACTIVE,
            connectivity_status=ConnectivityStatus.OFFLINE,
        )
        device = await device_repository.create(device_data, tenant.id)
        devices.append(device)
    return devices


@pytest.fixture
def s3_upload_repository(db_session):
    repo = S3UploadRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def sample_qc_event(factory):
    """Sample QC event with all required fields"""
    return QcEventSchema(
        event_id=uuid.uuid4(),
        factory_id=factory.id,
        device_metadata={
            "device_id": "device_001",
            "device_type": "inspection_camera",
            "location": "line_1",
        },
        qc_event_timestamp=datetime.now(timezone.utc),
        raw_payload={
            "defect_type": "stitch_defect",
            "severity": "high",
            "image_url": "s3://bucket/image.jpg",
        },
        execution_context={"operator_id": "op_123", "shift": "morning", "line_speed": 100},
        processing_duration_ms=150,
        processing_status="PENDING",
        validation_triggered=False,
        processing_results=None,
        has_errors=False,
        validation_error_count=0,
        retry_count=0,
        processed_at=None,
    )


@pytest.fixture
def sample_qc_event_batch(factory):
    """Sample QC event batch with 5 events"""
    events = []
    base_time = datetime.now(timezone.utc)

    for i in range(5):
        event = QcEventSchema(
            event_id=uuid.uuid4(),
            factory_id=factory.id,
            device_metadata={"device_id": f"device_{i:03d}", "device_type": "inspection_camera"},
            qc_event_timestamp=base_time - timedelta(minutes=i),
            raw_payload={"defect_type": f"defect_type_{i}", "severity": "medium"},
            execution_context={"operator_id": f"op_{i}", "shift": "morning"},
            processing_duration_ms=100 + i * 10,
            processing_status="PENDING",
            validation_triggered=False,
            processing_results=None,
            has_errors=False,
            validation_error_count=0,
            retry_count=0,
            processed_at=None,
        )
        events.append(event)

    return QcEventBatchSchema(events=events)


@pytest.fixture
def sample_qc_event_future_timestamp(factory):
    """Sample QC event with future timestamp (for validation testing)"""
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)

    return QcEventSchema(
        event_id=uuid.uuid4(),
        factory_id=factory.id,
        device_metadata={"device_id": "device_001"},
        qc_event_timestamp=future_time,
        raw_payload={"test": "data"},
        execution_context={},
        processing_status="PENDING",
        validation_triggered=False,
        has_errors=False,
        validation_error_count=0,
        retry_count=0,
    )


# ==================== QC DEFECTS REPOSITORY FIXTURES ====================
@pytest.fixture
def qc_defect_repository(db_session):
    """QC Defect repository fixture"""
    from src.features.qc_defects_collection.repository import QcDefectRepository

    repo = QcDefectRepository()
    repo.db = db_session
    return repo


# ==================== QC DEFECT FIXTURES ====================
@pytest.fixture
async def qc_defect(qc_defect_repository, tenant, factory):
    """Create a single QC defect for testing"""
    defect_data = {
        "defect_event_id": uuid.uuid4(),
        "parent_qc_event_id": uuid.uuid4(),
        "factory_id": factory.id,
        "defect_payload": {
            "defect_type": "stitch_defect",
            "severity": "high",
            "description": "Thread break detected",
        },
        "defect_coordinates": {"x": 100, "y": 200, "width": 50, "height": 50},
        "event_timestamp": datetime.now(timezone.utc),
        "received_at_timestamp": datetime.now(timezone.utc),
        "processing_status": "PENDING",
        "processing_duration_ms": 150,
        "validation_triggered": False,
        "processing_results": None,
        "has_errors": False,
        "validation_error_count": 0,
        "retry_count": 0,
        "batch_id": uuid.uuid4(),
        "correlation_id": "test-correlation-1",
    }

    await qc_defect_repository.bulk_create([defect_data], tenant.id)

    defect = await qc_defect_repository.get_by_id(
        defect_event_id=defect_data["defect_event_id"], factory_id=factory.id
    )

    return defect


@pytest.fixture
async def qc_defect_batch(qc_defect_repository, tenant, factory):
    """Create a batch of 5 QC defects for testing"""
    batch_id = uuid.uuid4()
    base_time = datetime.now(timezone.utc)
    defects_data = []

    for i in range(5):
        defects_data.append(
            {
                "defect_event_id": uuid.uuid4(),
                "parent_qc_event_id": uuid.uuid4(),
                "factory_id": factory.id,
                "defect_payload": {
                    "defect_type": f"defect_type_{i}",
                    "severity": "medium",
                    "index": i,
                },
                "defect_coordinates": {"x": i * 10, "y": i * 20},
                "event_timestamp": base_time - timedelta(minutes=i),
                "received_at_timestamp": datetime.now(timezone.utc),
                "processing_status": "PENDING",
                "processing_duration_ms": 100 + i * 10,
                "validation_triggered": False,
                "processing_results": None,
                "has_errors": False,
                "validation_error_count": 0,
                "retry_count": 0,
                "batch_id": batch_id,
                "correlation_id": f"test-correlation-{i}",
            }
        )

    await qc_defect_repository.bulk_create(defects_data, tenant.id)

    # Retrieve all defects in the batch
    defects = await qc_defect_repository.get_by_batch_id(batch_id=batch_id, factory_id=factory.id)

    return defects


@pytest.fixture
async def qc_defects_with_parent(qc_defect_repository, tenant, factory):
    """Create multiple defects with the same parent QC event"""
    parent_qc_event_id = uuid.uuid4()
    defects_data = []

    for i in range(3):
        defects_data.append(
            {
                "defect_event_id": uuid.uuid4(),
                "parent_qc_event_id": parent_qc_event_id,
                "factory_id": factory.id,
                "defect_payload": {"defect_type": f"related_defect_{i}", "severity": "low"},
                "event_timestamp": datetime.now(timezone.utc) - timedelta(seconds=i),
                "received_at_timestamp": datetime.now(timezone.utc),
                "processing_status": "PENDING",
                "validation_triggered": False,
                "has_errors": False,
                "validation_error_count": 0,
                "retry_count": 0,
                "batch_id": uuid.uuid4(),
            }
        )

    await qc_defect_repository.bulk_create(defects_data, tenant.id)

    # Retrieve all defects for the parent event
    defects = await qc_defect_repository.get_by_parent_event(
        parent_qc_event_id=parent_qc_event_id, factory_id=factory.id
    )

    return defects


@pytest.fixture
async def qc_defect_with_errors(qc_defect_repository, tenant, factory):
    """Create a QC defect with error flags set"""
    defect_data = {
        "defect_event_id": uuid.uuid4(),
        "factory_id": factory.id,
        "defect_payload": {"defect_type": "validation_failed", "severity": "critical"},
        "event_timestamp": datetime.now(timezone.utc),
        "received_at_timestamp": datetime.now(timezone.utc),
        "processing_status": "FAILED",
        "processing_duration_ms": 500,
        "validation_triggered": True,
        "processing_results": {
            "error": "validation_error",
            "message": "Invalid defect coordinates",
        },
        "has_errors": True,
        "validation_error_count": 2,
        "retry_count": 1,
        "batch_id": uuid.uuid4(),
        "correlation_id": "error-correlation-1",
    }

    await qc_defect_repository.bulk_create([defect_data], tenant.id)

    defect = await qc_defect_repository.get_by_id(
        defect_event_id=defect_data["defect_event_id"], factory_id=factory.id
    )

    return defect


@pytest.fixture
async def qc_defect_other_factory(qc_defect_repository, tenant, db_session):
    """Create a QC defect for a different factory"""
    from src.features.factory.models import Factory, FactoryCategory

    # Create a different factory
    other_factory = Factory(
        name="Other Factory",
        categories=[FactoryCategory.APPAREL],
        address="789 Other Street",
        city="Other City",
        state="Other State",
        country="Other Country",
        postal_code="99999",
        contact_name="Other Contact",
        contact_phone_number="+1999999999",
        contact_email="other@factory.com",
        country_code="+1",
        tenant_id=tenant.id,
    )

    db_session.add(other_factory)
    await db_session.commit()
    await db_session.refresh(other_factory)

    defect_data = {
        "defect_event_id": uuid.uuid4(),
        "factory_id": other_factory.id,
        "defect_payload": {"defect_type": "other_factory_defect"},
        "event_timestamp": datetime.now(timezone.utc),
        "received_at_timestamp": datetime.now(timezone.utc),
        "processing_status": "PENDING",
        "validation_triggered": False,
        "has_errors": False,
        "validation_error_count": 0,
        "retry_count": 0,
        "batch_id": uuid.uuid4(),
    }

    await qc_defect_repository.bulk_create([defect_data], tenant.id)

    defect = await qc_defect_repository.get_by_id(
        defect_event_id=defect_data["defect_event_id"], factory_id=other_factory.id
    )

    return defect


@pytest.fixture
def sample_qc_defect_event(factory):
    """Sample QC defect event schema for testing"""
    from src.features.qc_defects_collection.schema import QcDefectEventSchema

    return QcDefectEventSchema(
        defect_event_id=uuid.uuid4(),
        parent_qc_event_id=uuid.uuid4(),
        factory_id=factory.id,
        defect_payload={"defect_type": "sample_defect", "severity": "medium"},
        defect_coordinates={"x": 100, "y": 200},
        event_timestamp=datetime.now(timezone.utc),
        processing_duration_ms=150,
        processing_status="PENDING",
        validation_triggered=False,
        has_errors=False,
        validation_error_count=0,
        retry_count=0,
    )


@pytest.fixture
def sample_qc_defect_batch_schema(factory):
    """Sample QC defect batch schema for testing"""
    from src.features.qc_defects_collection.schema import (
        QcDefectBatchSchema,
        QcDefectEventSchema,
    )

    events = []
    base_time = datetime.now(timezone.utc)

    for i in range(5):
        events.append(
            QcDefectEventSchema(
                defect_event_id=uuid.uuid4(),
                factory_id=factory.id,
                defect_payload={"defect_type": f"defect_{i}"},
                event_timestamp=base_time - timedelta(minutes=i),
                processing_status="PENDING",
                validation_triggered=False,
                has_errors=False,
                validation_error_count=0,
                retry_count=0,
            )
        )

    return QcDefectBatchSchema(events=events)


@pytest.fixture
def sample_qc_defect_with_json_strings(factory):
    """Sample QC defect event with JSON fields as strings"""
    from src.features.qc_defects_collection.schema import QcDefectEventSchema

    return QcDefectEventSchema(
        defect_event_id=uuid.uuid4(),
        factory_id=factory.id,
        defect_payload='{"defect_type": "string_payload", "severity": "high"}',
        defect_coordinates='{"x": 150, "y": 250, "width": 75}',
        event_timestamp=datetime.now(timezone.utc),
        processing_status="PENDING",
        validation_triggered=False,
        has_errors=False,
        validation_error_count=0,
        retry_count=0,
    )


@pytest.fixture
async def qc_defects_various_statuses(qc_defect_repository, tenant, factory):
    """Create defects with various processing statuses"""
    statuses = ["PENDING", "PROCESSING", "COMPLETED", "FAILED", "RETRYING"]
    defects_data = []

    for i, status in enumerate(statuses):
        defects_data.append(
            {
                "defect_event_id": uuid.uuid4(),
                "factory_id": factory.id,
                "defect_payload": {"status_test": status},
                "event_timestamp": datetime.now(timezone.utc) - timedelta(minutes=i),
                "received_at_timestamp": datetime.now(timezone.utc),
                "processing_status": status,
                "validation_triggered": False,
                "has_errors": status == "FAILED",
                "validation_error_count": 1 if status == "FAILED" else 0,
                "retry_count": 1 if status == "RETRYING" else 0,
                "batch_id": uuid.uuid4(),
            }
        )

    await qc_defect_repository.bulk_create(defects_data, tenant.id)

    defects = []
    for defect_data in defects_data:
        defect = await qc_defect_repository.get_by_id(
            defect_event_id=defect_data["defect_event_id"], factory_id=factory.id
        )
        defects.append(defect)

    return defects


@pytest.fixture
async def qc_defects_date_range(qc_defect_repository, tenant, factory):
    """Create defects across a date range for date filtering tests"""
    base_time = datetime.now(timezone.utc)
    defects_data = []

    # Create defects at different time intervals
    time_offsets = [
        timedelta(days=-3),
        timedelta(days=-2),
        timedelta(days=-1),
        timedelta(hours=-12),
        timedelta(hours=-1),
    ]

    for i, offset in enumerate(time_offsets):
        defects_data.append(
            {
                "defect_event_id": uuid.uuid4(),
                "factory_id": factory.id,
                "defect_payload": {"time_index": i},
                "event_timestamp": base_time + offset,
                "received_at_timestamp": datetime.now(timezone.utc),
                "processing_status": "PENDING",
                "validation_triggered": False,
                "has_errors": False,
                "validation_error_count": 0,
                "retry_count": 0,
                "batch_id": uuid.uuid4(),
            }
        )

    await qc_defect_repository.bulk_create(defects_data, tenant.id)

    defects = []
    for defect_data in defects_data:
        defect = await qc_defect_repository.get_by_id(
            defect_event_id=defect_data["defect_event_id"], factory_id=factory.id
        )
        defects.append(defect)

    return defects

@pytest.fixture
async def production_plan(client, auth_headers, production_plan_payload, mock_verify_jwt):
    response = await client.post(
        "/api/v1/production-plans", json=production_plan_payload, headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    # Wrap the dict so tests can use production_plan.id instead of production_plan["id"]
    return SimpleNamespace(**data)

@pytest.fixture
def production_plan_payload(tenant, factory, factory_style, order, line, api_user):
    from src.features.production_plan.models import (
        ProductionPlanStatus,
        ProductionPlanVisibility,
    )

    plan_start = date.today()
    plan_end = date.today() + timedelta(days=5)

    return {
        "name": "Test Production Plan",
        "style_id": str(factory_style.id),
        "factory_id": str(factory.id),
        "tenant_id": str(tenant.id),
        "line_id": str(line.id),
        "plan_start_date": plan_start.isoformat(),
        "plan_end_date": plan_end.isoformat(),
        "visibility": ProductionPlanVisibility.PRIVATE.value,
        "status": ProductionPlanStatus.DRAFT.value,
        "owner_user_id": str(api_user.id),
        "sam_efficiency_target": 75.0,
        "smv_target": 12.5,
        "dhu_target": 5,
        "allocations": [{"order_id": str(order.id), "quantity": 100}],
        "daily_targets": [
            {
                "start_date": plan_start.isoformat(),
                "end_date": plan_start.isoformat(),
                "daily_target": 20,
                "target_units": 20,
                "hourly_target": 2.5,
                "sam_efficiency": 75.0,
                "total_units": 20,
            }
        ],
    }


@pytest.fixture
async def draft_production_plan(client, auth_headers, production_plan_payload, mock_verify_jwt):
    response = await client.post(
        "/api/v1/production-plans", json=production_plan_payload, headers=auth_headers
    )
    assert response.status_code == 201
    return response.json()



# ==================== QC EVENTS FIXTURES ====================
@pytest.fixture
def qc_event_repository(db_session):
    from src.features.qc_data_collection.repository import QcUnitEventsRepository
    repo = QcUnitEventsRepository()
    repo.db = db_session
    return repo


@pytest.fixture
def qc_defect_repository(db_session):
    from src.features.qc_defects_collection.repository import QcDefectRepository
    repo = QcDefectRepository()
    repo.db = db_session
    return repo