# Delivero Backend — Django + DRF

Smart Autonomous Delivery Vehicle backend for the Flutter app.

---

## Project Structure

```
delivero_backend/
├── delivero/               ← Project config (settings, urls)
├── apps/
│   ├── authentication/     ← Register, Login, JWT
│   ├── customers/          ← Customer profile, Addresses
│   ├── products/           ← Products, Categories
│   ├── cart/               ← Cart & Cart Items
│   ├── orders/             ← Orders, QR Code, Tracking
│   ├── payments/           ← Simulated Payments
│   ├── robots/             ← Robot status, GPS, Telemetry
│   └── notifications/      ← In-app Notifications
├── manage.py
├── requirements.txt
└── .env
```

---

## Setup Instructions

### 1. Create and activate virtual environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Edit the `.env` file:
```
SECRET_KEY=your-very-secret-key-change-this
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Run database migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Create a superuser (admin)
```bash
python manage.py createsuperuser
```

### 6. Run the development server
```bash
python manage.py runserver
```

Your API is now live at: **http://127.0.0.1:8000/api/**
Django Admin: **http://127.0.0.1:8000/admin/**

---

## API Endpoints Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register new customer |
| POST | `/api/auth/login/` | Login (returns JWT) |
| POST | `/api/auth/logout/` | Logout (blacklists token) |
| POST | `/api/auth/token/refresh/` | Refresh JWT token |
| POST | `/api/auth/password-reset/` | Request password reset |
| POST | `/api/auth/change-password/` | Change password |

### Customers
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/customers/me/` | Get my profile |
| PUT | `/api/customers/me/` | Update my profile |
| GET | `/api/customers/addresses/` | List my addresses |
| POST | `/api/customers/addresses/` | Add address |
| PUT | `/api/customers/addresses/{id}/` | Update address |
| DELETE | `/api/customers/addresses/{id}/` | Delete address |

### Products
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/products/` | List all products (supports `?search=` and `?category=`) |
| GET | `/api/products/{id}/` | Get product detail |
| GET | `/api/products/categories/` | List all categories |

### Cart
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cart/` | View my cart |
| POST | `/api/cart/items/` | Add item to cart |
| PUT | `/api/cart/items/{id}/` | Update item quantity |
| DELETE | `/api/cart/items/{id}/` | Remove item |
| DELETE | `/api/cart/clear/` | Clear entire cart |

### Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/orders/` | My order history |
| POST | `/api/orders/` | Place new order from cart |
| GET | `/api/orders/{id}/` | Order details |
| PATCH | `/api/orders/{id}/cancel/` | Cancel order |
| GET | `/api/orders/{id}/track/` | Track delivery (robot location) |
| GET | `/api/orders/{id}/qr/` | Get QR code for pickup |
| POST | `/api/orders/{id}/verify-qr/` | Verify QR, unlock compartment |
| GET | `/api/orders/admin/` | Admin: view all orders |
| PATCH | `/api/orders/admin/{id}/assign/` | Admin: assign robot to order |

### Payments
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/payments/` | Process payment for order |
| GET | `/api/payments/{id}/` | Get payment details |

### Robots
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/robots/` | List all robots (admin) |
| GET | `/api/robots/{id}/` | Get robot details |
| PATCH | `/api/robots/{id}/location/` | Update GPS (from Raspberry Pi) |
| PATCH | `/api/robots/{id}/telemetry/` | Push full telemetry (from Raspberry Pi) |
| GET | `/api/robots/{id}/telemetry/history/` | View telemetry logs |

### Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications/` | Get my notifications |
| PATCH | `/api/notifications/{id}/read/` | Mark as read |
| PATCH | `/api/notifications/read-all/` | Mark all as read |

---

## How Flutter Uses the API

### 1. Register and save the token
```
POST /api/auth/register/
→ returns { tokens: { access, refresh }, user: {...} }
```
Save the `access` token in Flutter and send it with every request:
```
Authorization: Bearer <access_token>
```

### 2. Complete order flow
```
1. Browse:  GET /api/products/
2. Add:     POST /api/cart/items/
3. Order:   POST /api/orders/  (with address_id)
4. Pay:     POST /api/payments/
5. Track:   GET /api/orders/{id}/track/  (poll every few seconds)
6. Pickup:  GET /api/orders/{id}/qr/
7. Scan:    POST /api/orders/{id}/verify-qr/ (with code from QR)
```

### 3. Raspberry Pi telemetry
```
PATCH /api/robots/{id}/telemetry/
Body: { latitude, longitude, battery_level, speed, status }
```

---

## Testing with Postman

1. Import the endpoints above into Postman
2. Register a user → copy the `access` token
3. In Postman, set `Authorization: Bearer <token>` header
4. Test each endpoint in order: Auth → Products → Cart → Orders

---

## Notes

- Database: SQLite (file: `db.sqlite3`) — no setup needed
- QR code images saved to: `media/qr_codes/`
- Switch to PostgreSQL: just update `DATABASES` in `settings.py`
- Real-time tracking uses polling — Flutter calls `/track/` every few seconds
