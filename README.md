# RemPro Virtual Citizenship Application

RemPro is a robust Django REST Framework application built to facilitate seamless connections between remote freelancers and companies. It handles secure user authentication, profile verification (including NIN verification and physical location checks), job postings, contracts, split payment processing via Paystack, real-time messaging flags, and the generation of digital Virtual Citizenship ID cards.

## 🏗️ Architecture

The codebase has been refactored into a highly modular, decoupled **MVT (Model-View-Template)** architecture. Monolithic files have been broken down into domain-specific packages to promote maintainability, clean separation of concerns, and scalability.

```text
appone/
├── models/             # Domain-specific database models
│   ├── user.py         # Custom User model
│   ├── freelancer.py   # Freelancer profiles & verification
│   ├── company.py      # Company profiles
│   ├── otp.py          # OTP tracking
│   ├── job.py          # Job postings and applications
│   ├── contract.py     # Contracts and Payments
│   └── workspace.py    # Workspaces, Tasks, Messages
│
├── serializers/        # DRF Data serialization and validation
│   ├── auth.py         # Registration, Login, Logout serializers
│   ├── freelancer.py   # NIN, Portfolio, Banking, and Profile serializers
│   ├── company.py      # Company registration and meeting serializers
│   ├── job.py          # Hiring and Application status serializers
│   └── ...
│
├── views/              # ViewSets handling business logic
│   ├── auth.py         # Authentication endpoints
│   ├── freelancer_profile.py # Async CV uploads, ID card generation
│   ├── job_application.py    # Job application flow (Hire, Update)
│   ├── payment.py      # Tax calculations and Paystack integration
│   └── ...
│
├── tasks/              # Celery asynchronous and periodic tasks
│   ├── otp.py          # Sending SMS/Email OTPs
│   ├── freelancer.py   # Background image uploads to Cloudinary
│   └── payment.py      # Async payment processing
│
└── utils/              # Helper utilities and external integrations
    ├── cloudinary.py   # Image upload and signed URL logic
    ├── tax.py          # Dynamic platform tax split calculations
    └── verification.py # ipapi/Gov API verifications
```

## 🚀 Key Features

*   **Custom Authentication:** JWT-based login with a robust, custom user model tracking user types (Freelancer, Company, Admin).
*   **OTP & Verification Flow:** Highly secure verification processes including Nigerian phone verification, government NIN integration, and IP-based geolocation checks.
*   **Background Processing (Celery):** Offloads heavy tasks such as email delivery, SMS dispatch, Cloudinary asset uploads, and monthly payment report generation.
*   **Virtual Citizenship IDs:** Automatically generates dynamic digital ID cards for verified users, securely hosted and signed via Cloudinary.
*   **Contract & Split Payments:** Creates binding contracts with automatic, dynamic tax distributions to the platform, dwelling country, and work country via Paystack.
*   **API Documentation:** Fully documented with Swagger UI and ReDoc via `drf-spectacular`.

## 🛠️ Tech Stack

*   **Framework:** Django & Django REST Framework (DRF)
*   **Task Queue:** Celery with Redis (Broker)
*   **Media Storage:** Cloudinary
*   **Authentication:** SimpleJWT
*   **API Documentation:** drf-spectacular (Swagger / OpenAPI 3.0)
*   **Payments:** Paystack

---

## 💻 Getting Started

### 1. Prerequisites
*   Python 3.12+
*   Redis server (must be running for Celery tasks)

### 2. Installation
Clone the repository and install the dependencies:
```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory (where `manage.py` lives) with the following essential keys:
```env
DEBUG=True
SECRET_KEY=your_django_secret_key
DATABASE_URL=postgres://user:password@localhost:5432/db_name

# Cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Paystack
PAYSTACK_SECRET_KEY=your_paystack_secret
PAYSTACK_PUBLIC_KEY=your_paystack_public

# Email / Twilio SMS Keys
EMAIL_HOST_USER=your_email@domain.com
EMAIL_HOST_PASSWORD=your_email_password
```

### 4. Database Setup
Run the migrations to create the database schema:
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Running the Application

You will need to run three separate terminal instances to fully operate the application locally:

**Terminal 1 (Django Server):**
```bash
python manage.py runserver
```

**Terminal 2 (Celery Worker):**
```bash
# Processes background tasks like sending OTPs and uploading to Cloudinary
celery -A RemPro worker -l info --pool=solo
```

**Terminal 3 (Celery Beat - Optional):**
```bash
# Triggers scheduled periodic tasks
celery -A RemPro beat -l info
```

---

## 📚 API Documentation

Once the server is running, you can explore and test all API endpoints via the automated Swagger UI interface.

*   **Swagger UI:** [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
*   **ReDoc UI:** [http://127.0.0.1:8000/api/redoc/](http://127.0.0.1:8000/api/redoc/)
*   **Raw OpenAPI Schema:** [http://127.0.0.1:8000/api/schema/](http://127.0.0.1:8000/api/schema/)

Every endpoint validates strictly against the modular serializers located in `appone/serializers/`, preventing raw request data bugs and ensuring schema accuracy.
