# TeleExam AI - Admin Web Panel Development Guide

## 1. Project Context
While the user-facing side of TeleExam AI is a Telegram Bot, the **Superadmin and Admin Operations Portal** is a perfectly standard **Web-Based Application**. 

As a frontend developer building the Admin panel, you can use any modern web framework (React, Next.js, Vue, Svelte). Your web app will communicate with the exact same FastAPI backend as the Telegram bot, but via entirely different, highly secured endpoints located under the `/admin/*` router.

**CRITICAL RULE:** Unlike the Telegram Bot, you **DO NOT** need to send `X-Telegram-Id` or `X-Telegram-Secret` headers. The backend's middleware explicitly ignores the telegram security checks for the `/admin` web routes. Instead, you will use standard **JWT Bearer Tokens**.

---

## 2. Authentication & JWT Handshake (VERY IMPORTANT)

The authentication flow perfectly mimics a standard OAuth2 workflow to allow seamless integration with Swagger UI and modern frontends.

### A. Logging In
Because FastAPI strictly implements OAuth2 standard forms for login endpoints, your login request **MUST** be sent as Form Data (`application/x-www-form-urlencoded`), NOT as a JSON object! Additionally, the email field must be specifically named `username`.

**Endpoint:** `POST /admin/auth/login`
**Payload (Form Data):**
- `username` (The admin's email address)
- `password`

**Example (Axios):**
```javascript
import axios from 'axios';

const loginAdmin = async (email, password) => {
    const params = new URLSearchParams();
    params.append('username', email); // Must be 'username'
    params.append('password', password);

    const response = await axios.post('https://backend.com/admin/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    
    // Save to localStorage or Session
    localStorage.setItem('admin_token', response.data.access_token);
}
```

### B. Calling Secure Endpoints
Once you have the `access_token`, simply attach it as a Bearer token to all subsequent `/admin/*` requests.

**Example (Axios interceptor):**
```javascript
axios.interceptors.request.use(config => {
    const token = localStorage.getItem('admin_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});
```

---

## 3. The Superadmin vs Admin Hierarchy
The platform features fine-grained Role-Based Access Control (RBAC):

1. **Root Superadmin**: Defined strictly in the backend's hidden `.env`. Has absolutely all permissions permanently (`["*"]`). Only the superadmin can invite other admins.
2. **Invited Admins**: Stored in the database. When invited, they are explicitly given a restrictive list of permissions (e.g., `["view_users", "ban_user"]`).

---

## 4. Admin API Endpoints Breakdown

### Superadmin Operations

#### 1. Invite a Sub-Admin
**Endpoint:** `POST /admin/auth/invite`
**Description:** As the superadmin, you can invite new moderators and assign them passwords and permissions manually.
**Content-Type:** `multipart/form-data` or `application/x-www-form-urlencoded`
**Payload:**
- `email`: `str`
- `password`: `str` (You assign the password to give to them)
- `permissions`: `list[str]` (Must be exactly one of: `view_users`, `ban_user`, `view_stats`, `manage_content`).

#### 2. Update Admin Permissions
**Endpoint:** `PATCH /admin/auth/admins/{email}/permissions`
**Description:** Modify an existing admin's access.
**Content-Type:** `application/json`
**Payload:** `["view_users", "ban_user"]`

---

### Dashboard & Analytics Operations
*Requires the `view_stats` permission (or Superadmin).*

All of these endpoints return JSON arrays perfect for mapping into Chart.js or Recharts components.

- `GET /admin/stats/dau`: Returns Daily Active Users (`day`, `dau`) charted over a date range.
- `GET /admin/stats/exams`: Returns overall platform funnel (Total exams taken, Average scores platform-wide).
- `GET /admin/stats/referrals`: Leaderboard of the top inviters on the platform.
- `GET /admin/stats/questions`: Performance breakdown showing the `accuracy_rate` of specific exam questions to identify which questions are too hard.

---

### User Moderation Operations
*Requires the `view_users` or `ban_user` permission.*

#### 1. List All Telegram Users
**Endpoint:** `GET /admin/users/?limit=100&offset=0`
**Description:** Fetches all users who have triggered the Telegram Bot. Used to build a paginated data table.
**Response Fields:** `id`, `telegram_id`, `telegram_username`, `is_pro`, `is_banned`, `invite_count`.

#### 2. Ban a User
**Endpoint:** `POST /admin/users/{user_id}/ban`
**Params:** `reason` (string, e.g. "Spamming the AI")
**Description:** Instantly revokes their access to the entire platform and injects a strict `blocked` flag into the backend's high-speed Redis cache, freezing their bot immediately.

#### 3. Unban a User
**Endpoint:** `POST /admin/users/{user_id}/unban`
**Description:** Reinstates their account and flushes the Redis flag.

---

## 5. UI/UX Recommendations for the Frontend Developer
1. **The Navigation Sidebar**: Hide/Show tabs based on the logged-in admin's `permissions` array (decoded from the JWT payload or a `/me` endpoint). If they lack `view_stats`, hide the Analytics dashboard tab entirely!
2. **Data Tables**: Use a high-quality data grid library (like TanStack Table or MUI DataGrid) to handle the `/admin/users` pagination gracefully.
3. **Multi-Select Dropdowns**: For the "Invite Admin" screen, build a crisp multi-select dropdown for the `permissions` field so the Superadmin can easily check multiple boxes. 
4. **401 Unauthorized**: If an Axios response returns a `401`, immediately wipe the `admin_token` from `localStorage` and redirect the browser back to `/login` smoothly.
