# 🌾 FarmNex

### AI-Powered Direct Agricultural Marketplace & Supply Chain Platform

> Built for Smart India Hackathon 2026  
> Problem Statement ID: 26033  
> Theme: Agriculture, FoodTech & Rural Development

> **Working on this repo with Claude Code?** Start with [`docs/HOW_TO_USE_CLAUDE_CODE.md`](docs/HOW_TO_USE_CLAUDE_CODE.md).
> Known issues and their order: [`docs/FIX_PLAN.md`](docs/FIX_PLAN.md) · Progress: [`docs/STATUS.md`](docs/STATUS.md) ·
> Plugging in components: [`docs/integration/`](docs/integration/README.md)

---

## Run locally

**Backend** (Python 3.11+; `.env` is never committed):

```bash
cd backend
pip install -r requirements.txt
python generate_jwt_keys.py          # creates secrets/jwt_*.pem (never commit)
cp .env.example .env                 # then fill in DATABASE_URL etc.
uvicorn app.main:app --reload        # http://localhost:8000/docs
python -m pytest -q
```

**Frontend** (needs Flutter):

```bash
cd frontend
flutter pub get
flutter analyze
flutter test
flutter run
```

The app talks to `https://farmnex-a.fastapicloud.dev` by default; see `frontend/README.md` to point it at a
local backend.

---

## 🚜 About FarmNex

FarmNex is an AI-powered agricultural marketplace designed to connect
farmers and Farmer Producer Organisations (FPOs) directly with bulk
buyers and customers.

The platform aims to reduce unnecessary intermediaries in the
agricultural value chain while improving price discovery, reducing
post-harvest losses, creating value from agricultural waste, and
optimizing logistics.

FarmNex brings the complete process together in one platform:

**Price Discovery → Buyer Matching → Pre-Bidding → Crop Rescue →
Waste-to-Wealth → AI Forecasting → Route Optimization → Delivery**

---

## 🎯 Problem

Traditional agricultural supply chains can involve multiple
intermediaries between farmers and consumers.

A typical chain may involve:

Farmer → Local Agent → Wholesaler → Retailer → Consumer

Each additional layer can increase the gap between the price received
by the farmer and the price paid by the consumer.

FarmNex addresses this challenge by enabling more direct and transparent
connections between farmers, FPOs, buyers and customers.

---

## 💡 Our Solution

FarmNex provides a unified digital platform where farmers can:

- List and manage their crops
- Connect directly with buyers
- Receive bids before harvest
- Find suitable buyers based on price and demand
- Rescue crops that are close to spoilage
- Sell agricultural waste for productive use
- Get AI-powered price and demand forecasts
- Receive crop planning recommendations
- Optimize delivery routes
- Aggregate produce through FPOs

---

# 🚀 Core Features

## 1. 🔨 Pre-Bidding

Farmers can list crops before harvest with expected quantity,
harvest date and expected price.

Verified buyers can place competitive bids.

The farmer can compare bids and select the most suitable offer.

---

## 2. 🤝 Direct Farmer-to-Buyer Marketplace

Farmers and FPOs can directly connect with:

- Bulk buyers
- Businesses
- Retailers
- Customers

The platform provides transparent crop information and buyer
discovery.

---

## 3. 🚨 Crop Rescue

Crops that are approaching spoilage can be marked as rescue
opportunities.

FarmNex helps identify potential buyers who may be able to purchase
the produce quickly.

This aims to reduce avoidable post-harvest losses.

---

## 4. ♻️ Waste to Wealth

Agricultural waste can become an additional source of income.

FarmNex enables farmers to list suitable agricultural waste for
potential applications such as:

- Compost
- Cattle feed
- Biogas
- Other agricultural/industrial uses

---

## 5. 🤖 AI Forecaster

FarmNex uses AI/ML capabilities to provide agricultural decision
support.

### Price Prediction

Estimate future crop prices using relevant historical and market
information.

### Demand Forecasting

Estimate where and when demand for a crop may increase.

### Crop Planning

Recommend potentially suitable crops based on demand and relevant
agricultural factors.

### Price Recommendation

Provide an AI-assisted reference price to support better price
discovery.

### Crop Disease Prediction

Planned AI capability for identifying potential crop diseases from
crop images and providing appropriate next-step guidance.

---

## 6. 🎯 Smart Buyer Matching

FarmNex can rank potential buyers using factors such as:

- Offered price
- Demand
- Required quantity
- Location
- Delivery requirements
- Buyer history

---

## 7. 🚚 Route Optimization

FarmNex can optimize transportation by considering nearby farms,
buyers and delivery requirements.

The objective is to reduce:

- Transportation cost
- Travel time
- Empty vehicle capacity
- Unnecessary routes

---

## 8. 👨‍🌾 FPO Aggregation

Small farms can be aggregated through FPOs into larger lots.

This can help farmers meet bulk-buyer quantity requirements and
increase collective bargaining power.

---

# 👥 User Roles

## Farmer

- Register and manage profile
- Add crops
- List fresh produce
- Participate in pre-bidding
- Accept buyer bids
- Use AI forecasting
- List agricultural waste
- Request crop rescue
- Track transactions and deliveries

## FPO

- Manage multiple farmers
- Aggregate crops
- Create bulk lots
- Coordinate sales
- Connect with bulk buyers

## Buyer

- Browse available crops
- Search by crop, quantity and location
- Place bids
- Purchase directly from farmers/FPOs
- Manage orders
- Track deliveries

## Customer

- Discover available produce
- Purchase eligible crops
- View seller and product information
- Track orders

---

# 🧠 AI & Data Intelligence

FarmNex is designed around multiple agricultural intelligence
capabilities:

| AI Capability | Purpose |
|---|---|
| Price Prediction | Estimate future crop prices |
| Demand Forecasting | Predict upcoming crop demand |
| Price Recommendation | Support farmer price discovery |
| Crop Planning | Suggest potentially profitable crops |
| Crop Disease Detection | Identify possible crop diseases |
| Buyer Matching | Rank suitable buyers |
| Route Optimization | Reduce logistics cost and time |

---

# 🏗️ Technology Stack

### Frontend

- Flutter
- Dart

### Backend

- Python
- FastAPI
- REST APIs

### AI / Machine Learning

- Python
- Machine Learning models
- Data processing and forecasting

### Database

- PostgreSQL (Supabase)

### Maps & Logistics

- Google Maps API
- OR-Tools

### Cloud & Services

- FastAPI Cloud
- Firebase / AWS where required

---

# 🏛️ System Architecture

```text
                    ┌───────────────────┐
                    │   Flutter App     │
                    │ Farmer / Buyer /  │
                    │ Customer / FPO    │
                    └─────────┬─────────┘
                              │
                              │ REST API
                              ▼
                    ┌───────────────────┐
                    │      FastAPI      │
                    │    Backend API    │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
        ┌──────────┐   ┌──────────────┐  ┌──────────────┐
        │ Postgres │   │   AI / ML    │  │ External APIs│
        │ Database │   │   Services   │  │ Maps/Weather │
        └──────────┘   └──────────────┘  └──────────────┘


backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── core/                                      # Global infrastructure
│   │   ├── __init__.py
│   │   ├── config.py                              # Environment/settings
│   │   ├── database.py                            # DB engine/session
│   │   ├── security.py                            # JWT/password hashing
│   │   ├── logging.py                             # Logging configuration
│   │   ├── exceptions.py                          # Global exceptions
│   │   ├── middleware.py                          # CORS/request middleware
│   │   └── constants.py                           # Global constants/enums
│   │
│   ├── api/                                       # HTTP/API layer
│   │   ├── __init__.py
│   │   ├── deps.py                                # Common dependencies
│   │   │
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                          # Registers all v1 endpoints
│   │   │   │
│   │   │   └── endpoints/                         # HTTP endpoint definitions
│   │   │       ├── __init__.py
│   │   │       ├── health.py
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── farmers.py
│   │   │       ├── buyers.py
│   │   │       ├── fpos.py
│   │   │       ├── verification.py
│   │   │       ├── locations.py
│   │   │       ├── farms.py
│   │   │       ├── crop_types.py
│   │   │       ├── crops.py
│   │   │       ├── crop_images.py
│   │   │       ├── inventory.py
│   │   │       ├── marketplace.py
│   │   │       ├── bids.py
│   │   │       ├── rescue.py
│   │   │       ├── waste.py
│   │   │       ├── orders.py
│   │   │       ├── payments.py
│   │   │       ├── deliveries.py
│   │   │       ├── routes.py
│   │   │       ├── forecasting.py
│   │   │       ├── prices.py
│   │   │       ├── ai.py
│   │   │       ├── matching.py
│   │   │       ├── notifications.py
│   │   │       ├── favorites.py
│   │   │       ├── reviews.py
│   │   │       ├── chat.py
│   │   │       ├── dashboards.py
│   │   │       ├── uploads.py
│   │   │       ├── market_data.py
│   │   │       ├── weather.py
│   │   │       ├── soil.py
│   │   │       ├── search.py
│   │   │       ├── recommendations.py
│   │   │       ├── analytics.py
│   │   │       ├── admin.py
│   │   │       └── webhooks.py
│   │   │
│   │   └── v2/                                   # Only for future breaking changes
│   │       ├── __init__.py
│   │       └── router.py
│   │
│   ├── modules/                                  # Business/domain layer
│   │   │
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   ├── exceptions.py
│   │   │   └── constants.py
│   │   │
│   │   ├── users/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── farmers/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   │
│   │   ├── buyers/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   │
│   │   ├── fpos/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   │
│   │   ├── crops/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── inventory/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   │
│   │   ├── bidding/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── rescue/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   │
│   │   ├── waste/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   │
│   │   ├── marketplace/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   │
│   │   ├── orders/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── payments/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── deliveries/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   │
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   │
│   │   ├── forecasting/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   │
│   │   ├── matching/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   │
│   │   ├── notifications/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   │
│   │   ├── reviews/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   │
│   │   ├── chat/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   │
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── disease.py
│   │   │   ├── demand.py
│   │   │   ├── price.py
│   │   │   └── crop_planning.py
│   │   │
│   │   ├── analytics/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   │
│   │   └── verification/
│   │       ├── __init__.py
│   │       ├── models.py
│   │       ├── schemas.py
│   │       ├── repository.py
│   │       └── service.py
│   │
│   ├── integrations/                              # External services
│   │   ├── __init__.py
│   │   ├── redis.py
│   │   ├── storage.py                             # S3/object storage
│   │   ├── email.py
│   │   ├── sms.py
│   │   ├── payment_gateway.py
│   │   ├── maps.py                                # Google Maps/etc.
│   │   ├── weather.py
│   │   ├── market_data.py
│   │   └── push_notifications.py
│   │
│   ├── workers/                                   # Background jobs
│   │   ├── __init__.py
│   │   ├── celery.py
│   │   └── tasks/
│   │       ├── __init__.py
│   │       ├── emails.py
│   │       ├── notifications.py
│   │       ├── market_sync.py
│   │       ├── weather_sync.py
│   │       ├── forecasts.py
│   │       └── cleanup.py
│   │
│   └── utils/                                     # Generic helpers
│       ├── __init__.py
│       ├── pagination.py
│       ├── datetime.py
│       ├── validators.py
│       ├── response.py
│       └── enums.py
│
├── models/                                        # Optional central model exports
│   └── __init__.py
│
├── schemas/                                       # Optional shared schemas
│   └── __init__.py
│
├── repositories/                                  # Optional shared repositories
│   └── __init__.py
│
├── db/
│   ├── __init__.py
│   └── seed/
│       └── README.md
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   │
│   ├── unit/
│   │   ├── auth/
│   │   ├── users/
│   │   ├── farmers/
│   │   ├── buyers/
│   │   ├── crops/
│   │   ├── bidding/
│   │   ├── orders/
│   │   ├── payments/
│   │   ├── forecasting/
│   │   └── matching/
│   │
│   ├── integration/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   └── v2/
│   │   └── database/
│   │
│   └── e2e/
│
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_create_users.py
│       ├── 002_create_farms.py
│       ├── 003_create_crops.py
│       ├── 004_create_bids.py
│       ├── 005_create_orders.py
│       └── ...
│
├── scripts/
│   ├── seed.py
│   ├── create_admin.py
│   ├── migrate.py
│   └── cleanup.py
│
├── deployment/
│   ├── docker/
│   │   └── Dockerfile
│   ├── nginx/
│   │   └── nginx.conf
│   └── k8s/
│       ├── deployment.yaml
│       ├── service.yaml
│       └── ingress.yaml
│
├── .github/
│   └── workflows/
│       ├── tests.yml
│       ├── lint.yml
│       └── deploy.yml
│
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── API_NOTES.md
├── README.md
└── Makefile



Building flow -
Yes. I checked the attached architecture and also verified the SIH 2026 material available online. The description you gave matches **SIH 2026 PS SIH260033**, whose stated issue is that multiple intermediaries reduce farmers' earnings and increase consumer prices. ([Lemon Eight][1])

For FarmNex, I would now move from the current **User + Address + Farm + Auth/Storage** foundation into a proper **agri-marketplace domain model**.

One important correction first: your attached diagram currently says **Java + Spring Boot + MySQL**, while the backend we have actually built is **FastAPI + PostgreSQL/Supabase**. For the final SIH architecture/presentation, those should be made consistent.

## 1. Don't make one giant marketplace table

The core flow should be:

```text
USER
 │
 ├── FARM
 │    └── CROP
 │         └── CROP BATCH
 │              └── LISTING
 │                   ├── DIRECT SALE
 │                   └── PRE-BIDDING
 │
 ├── BUYER
 │    └── CART
 │         └── ORDER
 │              └── ORDER ITEMS
 │                   └── DELIVERY
 │
 └── FARMER
      ├── FARM ACTIVITIES
      ├── CROP RECORDS
      ├── HARVESTS
      └── WASTE
             └── WASTE → HEALTH / OTHER USE
```

That separation will make FarmNex much easier to scale.

---

# 2. Tables I recommend

### Already existing

You already have:

```text
users
roles
addresses
farms
otp_verifications
user_sessions
auth_events
```

Keep these.

Then add the following domains.

---

# 3. Crop master

## `crop_types`

This is the master catalog, **not a farmer's crop**.

```text
crop_types
------------
id
public_id
name
scientific_name
category
description
unit_of_measure
is_perishable
typical_shelf_life_days
is_active
created_at
updated_at
```

Examples:

```text
Tomato
Potato
Onion
Wheat
Rice
Mango
Cotton
```

Don't store `"Tomato"` repeatedly in every crop record.

---

# 4. Farmer crop management

## `farm_crops`

This represents:

> "Farmer X is growing tomatoes in Farm Y."

```text
farm_crops
----------
id
public_id
farm_id
crop_type_id

season
sowing_date
expected_harvest_date
actual_harvest_date

area
area_unit

expected_quantity
expected_quantity_unit

status

notes
created_at
updated_at
```

Possible status:

```text
PLANNED
SOWN
GROWING
READY_FOR_HARVEST
HARVESTED
COMPLETED
CANCELLED
```

This is the table behind:

> **Farmers crops maintaining**

---

# 5. Crop batches / harvest lots

This is extremely important for a marketplace.

A farmer may harvest:

```text
Tomato
500 kg
Batch A
```

and sell it to different customers.

So create:

## `crop_batches`

```text
crop_batches
------------
id
public_id

farm_crop_id
crop_type_id
farm_id
farmer_id

batch_number

harvest_date
available_quantity
quantity_unit

quality_grade
quality_status

minimum_price
currency

status

created_at
updated_at
```

Example:

```text
Farm: Green Valley
Crop: Tomato
Harvest: 500 kg

Batch:
TOM-2026-0001
```

This becomes the traceability anchor for the marketplace.

---

# 6. Marketplace listings

Do **not** directly sell `farm_crops`.

Create:

## `product_listings`

```text
product_listings
----------------
id
public_id

farmer_id
farm_id
crop_batch_id
crop_type_id

title
description

listing_type
sale_status

available_quantity
unit

price_per_unit
currency

minimum_order_quantity

quality_grade

available_from
available_until

created_at
updated_at
```

`listing_type`:

```text
DIRECT_SALE
PRE_BID
```

`sale_status`:

```text
DRAFT
ACTIVE
PAUSED
SOLD_OUT
EXPIRED
CANCELLED
COMPLETED
```

This gives you the clean separation:

```text
Crop
 ↓
Harvest Batch
 ↓
Marketplace Listing
```

---

# 7. Product images

You already have Supabase Storage.

Your DB should store metadata.

## `product_images`

```text
product_images
--------------
id
public_id

listing_id

storage_path
content_type

display_order
is_primary

created_at
```

Storage:

```text
storage-bucket/
└── product-images/
    └── <uuid>.webp
```

Exactly consistent with your existing StorageService.

---

# 8. Pre-bidding

This should be its own domain.

## `bid_events`

```text
bid_events
----------
id
public_id

listing_id

title
description

starting_price
minimum_bid_increment

quantity
quantity_unit

starts_at
ends_at

status

created_at
updated_at
```

Status:

```text
DRAFT
SCHEDULED
LIVE
CLOSED
CANCELLED
```

Then:

## `bids`

```text
bids
----
id
public_id

bid_event_id
buyer_id

bid_amount
quantity
quantity_unit

status

placed_at
updated_at
```

Status:

```text
ACTIVE
OUTBID
WINNING
WON
REJECTED
CANCELLED
```

This allows:

```text
Farmer
 ↓
Pre-bidding event
 ↓
Multiple buyers
 ↓
Bids
 ↓
Winning buyer
 ↓
Order
```

---

# 9. Buyer demand

Your diagram specifically includes:

> Demand forecasting

For a prototype, don't mix AI predictions with actual transactions.

Create:

## `buyer_demand_requests`

```text
buyer_demand_requests
---------------------
id
public_id

buyer_id
crop_type_id

quantity
quantity_unit

target_price

required_from
required_until

delivery_address_id

status

created_at
updated_at
```

This allows:

> "I need 50 kg tomatoes between 20–25 September."

Then your AI system can use these records as demand signals.

---

# 10. Orders

Now the actual transaction.

## `orders`

```text
orders
------
id
public_id

buyer_id

delivery_address_id

subtotal
delivery_fee
discount
tax
total_amount

currency

payment_status
order_status

placed_at
confirmed_at
completed_at
cancelled_at

created_at
updated_at
```

Order status:

```text
PENDING
CONFIRMED
PROCESSING
READY_FOR_PICKUP
OUT_FOR_DELIVERY
DELIVERED
CANCELLED
FAILED
```

---

# 11. Order items

Never put products directly inside `orders`.

## `order_items`

```text
order_items
-----------
id
public_id

order_id
listing_id
crop_batch_id

quantity
quantity_unit

unit_price
subtotal

created_at
```

This also gives you historical pricing.

If farmer changes:

```text
₹40/kg → ₹50/kg
```

old orders still remain ₹40/kg.

---

# 12. Payments

For a serious architecture:

## `payments`

```text
payments
--------
id
public_id

order_id
buyer_id

provider
provider_payment_id

amount
currency

payment_method
payment_status

paid_at
failed_at

created_at
updated_at
```

Possible:

```text
PENDING
AUTHORIZED
PAID
FAILED
REFUNDED
PARTIALLY_REFUNDED
```

---

# 13. Delivery

Your diagram has:

> Route Optimization → Delivery

So create:

## `deliveries`

```text
deliveries
----------
id
public_id

order_id

agent_id

pickup_address_id
delivery_address_id

status

scheduled_pickup_at
picked_up_at

estimated_delivery_at
delivered_at

distance_km

created_at
updated_at
```

Status:

```text
ASSIGNED
PICKUP_PENDING
PICKED_UP
IN_TRANSIT
DELIVERED
FAILED
CANCELLED
```

---

# 14. Delivery tracking

Don't keep GPS history inside `deliveries`.

Create:

## `delivery_tracking_events`

```text
delivery_tracking_events
------------------------
id
delivery_id

latitude
longitude

event_type

recorded_at
```

Example:

```text
PICKED_UP
LOCATION_UPDATE
ARRIVED_NEAR_DESTINATION
DELIVERED
```

This can later feed route optimization.

---

# 15. Delivery proof

You already have:

```text
delivery-proof/
```

So:

## `delivery_proofs`

```text
delivery_proofs
---------------
id
public_id

delivery_id

storage_path
content_type

proof_type

captured_at

created_at
```

Examples:

```text
PHOTO
SIGNATURE
OTP
```

---

# 16. Farmer activity tracking

For crop management, add:

## `farm_crop_activities`

```text
farm_crop_activities
--------------------
id
public_id

farm_crop_id

activity_type
activity_date

description

quantity
quantity_unit

cost_amount
currency

created_at
updated_at
```

Activity types:

```text
SEEDING
IRRIGATION
FERTILIZER
PEST_CONTROL
WEEDING
SPRAYING
HARVESTING
OTHER
```

This gives you an actual farming history.

---

# 17. Agricultural waste

This is important because your diagram explicitly has:

> Crop Waste → Waste to Health

Create:

## `waste_records`

```text
waste_records
-------------
id
public_id

farmer_id
farm_id
farm_crop_id
crop_batch_id

waste_type

quantity
quantity_unit

reason

available_from
status

description

created_at
updated_at
```

Example:

```text
Tomato
100 kg
Overripe
```

---

# 18. Waste utilization

Don't hard-code "health" directly into waste.

Create:

## `waste_utilization_listings`

```text
waste_utilization_listings
--------------------------
id
public_id

waste_record_id
provider_id

utilization_type

title
description

quantity
quantity_unit

price
currency

status

created_at
updated_at
```

Possible utilization:

```text
HEALTH_PRODUCT
ANIMAL_FEED
COMPOST
BIOGAS
BIOFERTILIZER
PROCESSING
OTHER
```

This makes your **Waste → Health** concept extensible.

---

# 19. AI forecasting

This is where I strongly recommend **not** putting AI values into the crop/listing tables.

Create:

## `ai_predictions`

```text
ai_predictions
--------------
id
public_id

prediction_type

crop_type_id
farm_id
region

prediction_date
target_date

predicted_value
unit

confidence_score

model_name
model_version

input_reference

created_at
```

Prediction types:

```text
PRICE
DEMAND
YIELD
WASTE
```

For example:

```text
prediction_type = PRICE
crop = Tomato
target_date = 2026-10-01
predicted_value = 47
confidence_score = 0.82
model_version = price-v3
```

This gives you proper ML traceability.

---

# 20. AI recommendations

Then:

## `ai_recommendations`

```text
ai_recommendations
------------------
id
public_id

user_id

recommendation_type

crop_type_id
listing_id

title
message

score

model_name
model_version

expires_at

created_at
```

Examples:

```text
BEST_PRICE
CROP_TO_GROW
BUY_RECOMMENDATION
SELL_RECOMMENDATION
DEMAND_OPPORTUNITY
```

---

# 21. Notifications

You'll definitely need this.

## `notifications`

```text
notifications
-------------
id
public_id

user_id

notification_type

title
message

reference_type
reference_id

is_read
read_at

created_at
```

Examples:

```text
NEW_BID
OUTBID
BID_WON
ORDER_PLACED
ORDER_CONFIRMED
DELIVERY_UPDATE
PRICE_ALERT
AI_RECOMMENDATION
```

---

# 22. Reviews

For marketplace trust:

## `reviews`

```text
reviews
-------
id
public_id

order_id
buyer_id
farmer_id
listing_id

rating
comment

created_at
updated_at
```

You can later add:

```text
product_rating
farmer_rating
delivery_rating
```

but don't overcomplicate the prototype initially.

---

# 23. Disputes

For a production-oriented marketplace:

## `order_disputes`

```text
order_disputes
--------------
id
public_id

order_id
raised_by_user_id

reason
description

status

resolution
resolved_by
resolved_at

created_at
updated_at
```

---

# 24. Audit log

You already have `auth_events`, but marketplace actions also need auditability.

## `audit_logs`

```text
audit_logs
----------
id

user_id

action
entity_type
entity_id

old_data
new_data

ip_address
user_agent

created_at
```

For example:

```text
USER 123
UPDATE
LISTING
456

old price = ₹40
new price = ₹45
```

For PostgreSQL, `old_data` and `new_data` can be `JSONB`.

---

# 25. Final database architecture

So I would structure FarmNex approximately like this:

```text
AUTH
────────────────────
users
roles
otp_verifications
user_sessions
auth_events


LOCATION
────────────────────
addresses


FARM MANAGEMENT
────────────────────
farms
crop_types
farm_crops
farm_crop_activities
crop_batches


MARKETPLACE
────────────────────
product_listings
product_images
buyer_demand_requests


PRE-BIDDING
────────────────────
bid_events
bids


ORDERS
────────────────────
orders
order_items
payments


LOGISTICS
────────────────────
deliveries
delivery_tracking_events
delivery_proofs


WASTE
────────────────────
waste_records
waste_utilization_listings


AI / ML
────────────────────
ai_predictions
ai_recommendations


PLATFORM
────────────────────
notifications
reviews
order_disputes
audit_logs
```

## 26. The important relationships

The heart of your system becomes:

```text
                    ┌──────────────┐
                    │    USER      │
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
           FARMER                     BUYER
              │                         │
           FARM                       DEMAND
              │
          FARM_CROP
              │
         CROP_BATCH
              │
        PRODUCT_LISTING
          │           │
          │           └──────────────┐
          │                          │
     DIRECT SALE                 PRE-BID
          │                          │
          │                       BIDS
          │                          │
          └──────────┬───────────────┘
                     │
                   ORDER
                     │
                ORDER_ITEMS
                     │
                  PAYMENT
                     │
                 DELIVERY
                     │
              DELIVERY PROOF
```

And separately:

```text
FARM_CROP
    │
    ├── ACTIVITIES
    │
    ├── HARVEST
    │
    └── WASTE
           │
           └── WASTE UTILIZATION
                    │
          ┌─────────┼──────────┐
          │         │          │
       HEALTH     FEED      COMPOST
```

---

## 27. One architectural decision I strongly recommend

Don't build **all 20+ tables immediately**.

For your SIH prototype, build them in this order:

### Phase 1 — current foundation

Already working:

```text
users
roles
addresses
farms
auth
storage
```

### Phase 2 — core agricultural marketplace

```text
crop_types
farm_crops
crop_batches
product_listings
product_images
```

### Phase 3 — actual selling

```text
orders
order_items
payments
```

### Phase 4 — SIH differentiator

```text
bid_events
bids
buyer_demand_requests
```

### Phase 5 — logistics

```text
deliveries
delivery_tracking_events
delivery_proofs
```

### Phase 6 — waste

```text
waste_records
waste_utilization_listings
```

### Phase 7 — intelligence

```text
ai_predictions
ai_recommendations
notifications
```

### Phase 8 — trust/governance

```text
reviews
order_disputes
audit_logs
```

This gives you a strong schema without turning the prototype into an unmanageable project.

And importantly, **don't change your existing working User/Farm/Storage architecture just to accommodate these tables**. We should extend it around the stable foundation.

One more thing: the attached slide currently presents **MySQL / Java + Spring Boot**, while your implemented FarmNex backend is **PostgreSQL + FastAPI**. For the SIH presentation, I would update that slide before the final demo so the architecture shown to judges exactly matches what you actually built. The SIH material confirms PS SIH260033 is in the Agriculture, FoodTech & Rural Development theme and concerns reducing intermediary-driven farmer/consumer price inefficiency. ([Lemon Eight][1])

**Next step should be `crop_types → farm_crops → crop_batches → product_listings`**, because that establishes the central farmer-to-consumer flow on which pre-bidding, direct selling, orders, AI recommendations, and waste traceability can all build.

[1]: https://sih-lemon-eight.vercel.app/problem-statements?utm_source=chatgpt.com "Problem Statements | Smart India Hackathon 2026"




AUTH
users
roles
otp_verifications
user_sessions
auth_events

LOCATION
addresses

FARM
farms
crop_types
farm_crops
farm_crop_activities
crop_batches

MARKETPLACE
product_listings
product_images
buyer_demand_requests

BIDDING
bid_events
bids

ORDERS
orders
order_items
payments

LOGISTICS
deliveries
delivery_tracking_events
delivery_proofs

WASTE
waste_records
waste_utilization_listings

AI
ai_predictions
ai_recommendations

PLATFORM
notifications
reviews
order_disputes
audit_logs


User
 └── Farm
      └── FarmCrop
           ├── CropActivities
           └── CropBatch
                └── ProductListing
                     ├── ProductImages
                     └── BidEvent
                          └── Bids

BuyerDemandRequest
        │
        └── Bids

ProductListing
        │
        └── Order
             └── OrderItems
                  └── Payment
                  └── Delivery
                       ├── TrackingEvents
                       └── DeliveryProof

FarmCrop / CropBatch
        │
        └── WasteRecord
             └── WasteUtilizationListing

Farm / Crop / Batch / Listing
        │
        ├── AIPrediction
        └── AIRecommendation

User
 ├── Notifications
 ├── Reviews
 ├── OrderDisputes
 └── AuditLogs