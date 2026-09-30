from dotenv import load_dotenv

load_dotenv()  # before any other app / component import: components read os.environ directly

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.api.router import api_router
from app.core.database import (
    AsyncSessionLocal,
    check_database_connection,
    close_database,
    create_tables,
)
from app.core.exceptions import AppException
from app.models.crop_type import CropType
from app.modules.wiring import mount_components, start_components, stop_components
from app.repositories.role_repository import RoleRepository


logger = logging.getLogger(__name__)

DEFAULT_ROLES = {
    "SUPER_ADMIN": "Platform super administrator",
    "ADMIN": "Platform administrator",
    "MANAGER": "Platform manager",
    "STAFF": "Platform staff",
    "LOGISTICS_MANAGER": "Manages shipments and delivery partners",
    "DELIVERY_AGENT": "Delivers customer orders",
    "SUPPORT": "Customer support staff",
    "VENDOR": "Marketplace vendor",
    "BUYER": "FarmNex buyer",
    "FARMER": "FarmNex farmer",
}


DEFAULT_CROP_TYPES = [
    {
        "name": "Rice",
        "scientific_name": "Oryza sativa",
        "description": "A major cereal crop cultivated for food grain production.",
        "category": "Cereal",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Wheat",
        "scientific_name": "Triticum aestivum",
        "description": "A cereal crop cultivated for flour and food production.",
        "category": "Cereal",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Maize",
        "scientific_name": "Zea mays",
        "description": "A cereal crop used for food, animal feed, and industrial products.",
        "category": "Cereal",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Tomato",
        "scientific_name": "Solanum lycopersicum",
        "description": "A vegetable crop commonly used in cooking and food processing.",
        "category": "Vegetable",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Potato",
        "scientific_name": "Solanum tuberosum",
        "description": "A tuber crop cultivated for food consumption and processing.",
        "category": "Vegetable",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Onion",
        "scientific_name": "Allium cepa",
        "description": "A bulb vegetable crop commonly used as a food ingredient.",
        "category": "Vegetable",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Cotton",
        "scientific_name": "Gossypium hirsutum",
        "description": "A commercial fiber crop cultivated for textile production.",
        "category": "Fiber",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Sugarcane",
        "scientific_name": "Saccharum officinarum",
        "description": "A commercial crop primarily cultivated for sugar production.",
        "category": "Cash Crop",
        "default_unit": "ton",
        "is_active": True,
    },
    {
        "name": "Groundnut",
        "scientific_name": "Arachis hypogaea",
        "description": "An oilseed and food crop cultivated for edible seeds and oil.",
        "category": "Oilseed",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Mango",
        "scientific_name": "Mangifera indica",
        "description": "A tropical fruit crop cultivated for fresh fruit and processing.",
        "category": "Fruit",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Banana",
        "scientific_name": "Musa acuminata",
        "description": "A tropical fruit crop grown for fresh consumption and processing.",
        "category": "Fruit",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Carrot",
        "scientific_name": "Daucus carota",
        "description": "A root vegetable crop cultivated for its edible roots.",
        "category": "Vegetable",
        "default_unit": "kg",
        "is_active": True,
    },
    # Added so every Crop Rescue crop exists in crop_types (see app/modules/crops.py).
    {
        "name": "Spinach",
        "scientific_name": "Spinacia oleracea",
        "description": "A leafy green vegetable crop grown for fresh consumption.",
        "category": "Vegetable",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Okra",
        "scientific_name": "Abelmoschus esculentus",
        "description": "A warm-season vegetable crop grown for its edible green pods.",
        "category": "Vegetable",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Brinjal",
        "scientific_name": "Solanum melongena",
        "description": "A vegetable crop, also called eggplant, grown for its fruit.",
        "category": "Vegetable",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Cauliflower",
        "scientific_name": "Brassica oleracea var. botrytis",
        "description": "A vegetable crop grown for its edible flower head.",
        "category": "Vegetable",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Grapes",
        "scientific_name": "Vitis vinifera",
        "description": "A fruit crop grown for fresh consumption, raisins and juice.",
        "category": "Fruit",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Capsicum",
        "scientific_name": "Capsicum annuum",
        "description": "A vegetable crop, also called bell pepper, grown for its fruit.",
        "category": "Vegetable",
        "default_unit": "kg",
        "is_active": True,
    },
    {
        "name": "Cucumber",
        "scientific_name": "Cucumis sativus",
        "description": "A vine vegetable crop grown for fresh consumption.",
        "category": "Vegetable",
        "default_unit": "kg",
        "is_active": True,
    },
]


async def seed_default_roles() -> None:
    async with AsyncSessionLocal() as session:
        try:
            repository = RoleRepository(session)

            for name, description in DEFAULT_ROLES.items():
                if await repository.get_by_name(name) is None:
                    await repository.create(
                        name=name,
                        description=description,
                    )

            await session.commit()

        except Exception:
            await session.rollback()
            raise


async def seed_default_crop_types() -> None:
    async with AsyncSessionLocal() as session:
        try:
            inserted_count = 0
            skipped_count = 0

            for crop_data in DEFAULT_CROP_TYPES:
                result = await session.execute(
                    select(CropType).where(
                        func.lower(CropType.name)
                        == crop_data["name"].lower()
                    )
                )

                existing_crop = result.scalar_one_or_none()

                if existing_crop is not None:
                    skipped_count += 1
                    continue

                session.add(CropType(**crop_data))
                inserted_count += 1

            await session.commit()

            print(
                "Crop types seeded successfully. "
                f"Inserted: {inserted_count}, "
                f"Skipped: {skipped_count}"
            )

        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    await seed_default_roles()
    await seed_default_crop_types()
    start_components()

    yield

    stop_components()
    await close_database()


app = FastAPI(
    title="FarmNex API",
    description="Agricultural marketplace and AI platform",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    content = {"detail": exc.detail}

    if exc.code:
        content["code"] = exc.code

    if exc.data is not None:
        content["data"] = exc.data

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers,
    )


@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy"}


@app.get("/db", tags=["System"])
async def database_health_check():
    try:
        await check_database_connection()

        return {
            "status": "ok",
            "database": "connected",
        }

    except Exception:
        # Details (host, user, ...) go to the server log only, never to the caller.
        logger.exception("Database health check failed")

        return {
            "status": "error",
            "database": "disconnected",
        }


@app.get("/ready", tags=["System"])
async def readiness():
    return {"status": "ready"}


app.include_router(api_router, prefix="/api")

# Optional components (Crop Rescue, forecaster, routes, voice tools): each is mounted only if its
# ENABLE_* flag is "true", and a failure never stops the backend. See app/modules/wiring.py.
mount_components(app)
