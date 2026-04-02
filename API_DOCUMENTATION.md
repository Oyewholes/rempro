# RemPro API Documentation

This document outlines all the available REST API endpoints for the RemPro application.



> **Note:** All endpoints require a Bearer token in the `Authorization` header (`Authorization: Bearer <access_token>`) unless `[AllowAny]` is explicitly mentioned.

---

## 1. Authentication & JWT Tokens

| Method | Endpoint | Permissions | Description | Payload / Query Params |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/api/token/` | `[AllowAny]` | Obtain JWT access and refresh pair | `{ "email": "...", "password": "..." }` |
| **POST** | `/api/token/refresh/` | `[AllowAny]` | Refresh access token | `{ "refresh": "..." }` |
| **POST** | `/api/token/verify/` | `[AllowAny]` | Verify a token is valid | `{ "token": "..." }` |

---

## 2. Auth & Onboarding (`/api/auth/`)

| Method | Endpoint | Permissions | Description | Payload / Query Params |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/api/auth/register_freelancer/` | `[AllowAny]` | Register a new freelancer | `{ "email": "", "password": "", "password2": "", "user_type": "", "phone_number": "" }` |
| **POST** | `/api/auth/resend_freelancer_otp/` | `[IsAuthenticated]` | Resend phone OTP for freelancer | N/A |
| **POST** | `/api/auth/login/` | `[AllowAny]` | Login to the platform | `{ "email": "", "password": "" }` |
| **POST** | `/api/auth/logout/` | `[IsAuthenticated]` | Logout | `{ "refresh": "<refresh_token>" }` |
| **POST** | `/api/auth/register_company/` | `[AllowAny]` | Register a new company | `{ "email": "", "password": "", "password2": "", "user_type": "" }` |
| **POST** | `/api/auth/resend_company_otp/` | `[IsAuthenticated]` | Resend email OTP for company | N/A |

---

## 3. OTP & Verification (`/api/otp/`)

| Method | Endpoint | Permissions | Description | Payload |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/api/otp/send_phone_otp/` | `[IsAuthenticated]` | Send verification OTP to phone | `{ "phone_number": "+234XXXXXXXXXX" }` |
| **POST** | `/api/otp/verify_phone_otp/` | `[IsAuthenticated]` | Verify phone OTP | `{ "otp_code": "123456" }` |
| **POST** | `/api/otp/send_company_access_otp/` | `[IsAuthenticated]` | Send OTP to company email | N/A |
| **POST** | `/api/otp/verify_company_email_otp/` | `[IsAuthenticated]` | Verify company email OTP | `{ "otp_code": "123456" }` |

---

## 4. Freelancer Profiles (`/api/freelancers/`)
> **Important:** Unless otherwise stated, these endpoints require `[IsAuthenticated, IsFreelancer]`.

| Method | Endpoint | Permissions | Description | Payload |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/freelancers/me/` | `IsFreelancer` | Retrieve current freelancer profile | N/A |
| **PUT/PATCH** | `/api/freelancers/me/` | `IsFreelancer` | Update current freelancer profile | `FreelancerProfileUpdateSerializer` fields |
| **POST** | `/api/freelancers/verify_location/` | `IsFreelancer` | Verify Nigerian physical location | N/A |
| **POST** | `/api/freelancers/upload_cv/` | `IsFreelancer` | Upload CV document (PDF/Word, max 10MB) | Form-Data: `{ "cv_file": (File) }` |
| **POST** | `/api/freelancers/upload_live_photo/` | `IsFreelancer` | Upload live photo | Form-Data: `{ "live_photo": (Image) }` |
| **POST** | `/api/freelancers/add_nin/` | `IsFreelancer` | Add and verify 11-digit NIN | `{ "nin": "12345678901" }` |
| **POST** | `/api/freelancers/add_portfolio/` | `IsFreelancer` | Add portfolio item URL/Data | `{ "portfolio_item": "..." }` |
| **POST** | `/api/freelancers/add_banking_details/` | `IsFreelancer` | Add payment emails (Paystack/Payoneer) | `{ "paystack_email": "...", "payoneer_email": "..." }` |
| **GET** | `/api/freelancers/digital-id/{digital_id}/` | `[AllowAny]` | View freelancer public profile | URL parameter: `digital_id` |
| **POST** | `/api/freelancers/generate_id_card/` | `IsFreelancer` | Generate digital ID card (Async) | N/A |
| **GET** | `/api/freelancers/download_id_card/` | `IsFreelancer` | Get downloadable ID card URL | N/A |

---

## 5. Company Profiles (`/api/companies/`)
> **Important:** Standard actions require `[IsAuthenticated, IsCompany]`.

| Method | Endpoint | Permissions | Description | Payload / Query Params |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/companies/me/` | `IsCompany` | Retrieve current company profile | N/A |
| **PUT/PATCH** | `/api/companies/me/` | `IsCompany` | Update current company profile | `CompanyProfileUpdateSerializer` fields |
| **POST** | `/api/companies/propose-meeting-dates/` | `IsCompany` | Submit 3 proposed dates for verification | `{ "proposed_dates": ["2026-04-10T09:00:00Z", ... ] }` |
| **POST** | `/api/companies/schedule_verification_meeting/` | `IsCompany` | Schedule verification meeting with admin | `{ "meeting_date": "...", "meeting_link": "..." }` |
| **POST** | `/api/companies/verify_company_registration/` | `[IsAdmin]` | Admin verifies company structure with Govt | `{ "company_id": 1 }` |

---

## 6. Job Postings (`/api/jobs/`)

| Method | Endpoint | Permissions | Description | Payload / Query Params |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/jobs/` | `[IsAuthenticated]` | List active jobs | N/A |
| **GET** | `/api/jobs/{id}/` | `[IsAuthenticated]` | Retrieve specific job details | N/A |
| **GET** | `/api/jobs/search/` | `[IsAuthenticated]` | Search active jobs | QueryParams: `q=...`, `job_type=...`, `country=...` |
| **POST** | `/api/jobs/` | `IsVerifiedCompany` | Create a new job posting | `JobPostingSerializer` fields |
| **PUT/PATCH** | `/api/jobs/{id}/` | `IsCompany Owner` | Update a job | `JobPostingSerializer` fields |
| **DELETE** | `/api/jobs/{id}/` | `IsCompany Owner` | Delete a job | N/A |
| **POST** | `/api/jobs/{id}/publish/` | `IsCompany Owner` | Mark a job as active | N/A |
| **POST** | `/api/jobs/{id}/close/` | `IsCompany Owner` | Mark a job as closed | N/A |
| **GET** | `/api/jobs/{id}/applications/` | `IsCompany Owner` | Get applications for a specific job | N/A |
| **POST** | `/api/jobs/{id}/apply/` | `IsVerifiedFreelancer` | Apply to a job | `JobApplicationSerializer` fields |

---

## 7. Job Applications (`/api/applications/`)

| Method | Endpoint | Permissions | Description | Payload |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/applications/` | `[IsAuthenticated]` | List applications (Company/Freelancer scoped) | N/A |
| **GET** | `/api/applications/{id}/` | `[IsAuthenticated]` | Get specific application details | N/A |
| **POST** | `/api/applications/{id}/update_status/` | `IsCompany Owner` | Update app status (e.g. accepted/rejected) | `{ "status": "..." }` |
| **POST** | `/api/applications/{id}/hire/` | `IsCompany Owner` | Hire freelancer & create contract/workspace | `{ "start_date": "...", "monthly_rate": "...", "currency": "USD" }` |
| **DELETE** | `/api/applications/{id}/` | `IsAuthenticated` | Withdraw an application | N/A |

---

## 8. Contracts (`/api/contracts/`)

| Method | Endpoint | Permissions | Description | Payload |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/contracts/` | `[IsAuthenticated]` | List contracts | N/A |
| **GET** | `/api/contracts/{id}/` | `[IsAuthenticated]` | View specific contract | N/A |
| **POST** | `/api/contracts/{id}/activate/` | `[IsAuthenticated]` | Activate an existing contract | N/A |
| **POST** | `/api/contracts/{id}/complete/` | `[IsAuthenticated]` | Mark a contract as completed | N/A |
| **POST** | `/api/contracts/{id}/terminate/` | `[IsAuthenticated]` | Terminate an existing contract | N/A |

---

## 9. Payments (`/api/payments/`)

| Method | Endpoint | Permissions | Description | Payload |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/payments/` | `[IsAuthenticated]` | List payments related to user | N/A |
| **GET** | `/api/payments/{id}/` | `[IsAuthenticated]` | Retrieve specific payment details | N/A |
| **POST** | `/api/payments/` | `IsCompany` | Initiate a payment | `{ "contract": 1, "amount": 1000.00 }` |
| **POST** | `/api/payments/{id}/process/` | `IsCompany` | Process/finalize an initiated payment | N/A |

---

## 10. Workspaces (`/api/workspaces/`)

| Method | Endpoint | Permissions | Description | Payload |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/workspaces/` | `[IsAuthenticated]` | List internal workspaces | N/A |
| **GET** | `/api/workspaces/{id}/` | `[IsAuthenticated]` | Retrieve a specific workspace | N/A |
| **PUT/PATCH** | `/api/workspaces/{id}/` | `[IsAuthenticated]` | Update a workspace metadata | `{ "name": "...", "description": "..." }` |

---

## 11. Tasks (`/api/tasks/`)

| Method | Endpoint | Permissions | Description | Payload |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/tasks/` | `[IsAuthenticated]` | List tasks scoped to user/company | N/A |
| **POST** | `/api/tasks/` | `[IsAuthenticated]` | Create a task | `TaskSerializer` fields |
| **GET** | `/api/tasks/{id}/` | `[IsAuthenticated]` | Retrieve a specific task | N/A |
| **PUT/PATCH** | `/api/tasks/{id}/` | `[IsAuthenticated]` | Update a task | `TaskSerializer` fields |
| **POST** | `/api/tasks/{id}/update_status/` | `[IsAuthenticated]` | Update task completion status | `{ "status": "completed" }` |
| **DELETE** | `/api/tasks/{id}/` | `[IsAuthenticated]` | Delete a task | N/A |

---

## 12. Messages (`/api/messages/`)

| Method | Endpoint | Permissions | Description | Payload |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/messages/` | `[IsAuthenticated]` | List messages | N/A |
| **POST** | `/api/messages/` | `[IsAuthenticated]` | Send a new message | `{ "workspace": 1, "content": "..." }` |
| **GET** | `/api/messages/{id}/` | `[IsAuthenticated]` | Get specific message details | N/A |
| **GET** | `/api/messages/workspace_messages/`| `[IsAuthenticated]` | List messages for a workspace | QueryParams: `workspace_id=...` |

---

## 13. Admin Verification (`/api/admin/`)
> **Warning:** All endpoints in this category require `[IsAuthenticated, IsAdmin]` privileges.

| Method | Endpoint | Description | Payload |
| :--- | :--- | :--- | :--- |
| **POST** | `/api/admin/verify_freelancer/` | Verify a freelancer profile | `{ "freelancer_id": 1, "verification_status": "verified" }` |
| **GET** | `/api/admin/pending_verifications/`| List freelancers pending verification | N/A |
| **GET** | `/api/admin/pending_companies/` | List companies pending verification | N/A |
| **GET** | `/api/admin/company-proposed-dates/`| List companies with proposed meeting dates | N/A |
| **POST** | `/api/admin/confirm-meeting/` | Admin selects one of the 3 proposed dates | `{ "company": 1, "selected_date": "...", "meeting_link": "..." }` |
| **POST** | `/api/admin/verify-company/` | Admin marks company as verified/rejected | `{ "company_id": 1, "verification_status": "verified" }` |

---

## 14. WebSockets (Real-time Messaging)
> **Note:** The WebSocket connection requires authentication. Ensure you establish the connection using the authenticated user's token or standard Django session if cookies are maintained.

| Protocol | Endpoint | Description | Expected Payload Format (JSON block via WS) |
| :--- | :--- | :--- | :--- |
| **WS** | `ws://<host>/ws/workspace/<workspace_id>/` | Connect to workspace chat channel. | To send a message: `{ "message": "Your message here..." }` |
