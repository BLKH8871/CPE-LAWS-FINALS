# Data Privacy Compliance Management System: Demo Script & Architecture Overview

This document provides a step-by-step script for demonstrating the application's features for each user role, followed by a high-level overview of the system architecture and technologies used.

---
## Part 0: How to Run the Project (Manual Setup)

These instructions are for running the project from the source code without an AI assistant.

**Prerequisites:**
*   Python 3.x installed on your system.
*   A command-line terminal (like Command Prompt, PowerShell, or Terminal).

**Step-by-Step Instructions:**

1.  **Navigate to the Project Directory:**
    *   Open your terminal and navigate to the project folder.
    *   `cd path/to/CPE LAWS 1`

2.  **Create a Virtual Environment:**
    *   It's a best practice to create a virtual environment to keep project dependencies isolated.
    *   `python -m venv venv`

3.  **Activate the Virtual Environment:**
    *   **On Windows:** `venv\Scripts\activate`
    *   **On macOS/Linux:** `source venv/bin/activate`
    *   Your terminal prompt should now show `(venv)` at the beginning.

4.  **Install Dependencies:**
    *   Install all the required Python libraries from the `requirements.txt` file.
    *   `pip install -r requirements.txt`

5.  **Initialize the Database:**
    *   This step creates the `compliance_system.db` file and populates it with the necessary tables and mock data for the demo.
    *   `python init_db.py`

6.  **Run the Web Server:**
    *   Now, you can start the Flask development server.
    *   `flask run`
    *   The terminal will show that the server is running and listening on `http://127.0.0.1:5000`.

7.  **Access the Application:**
    *   Open your web browser and navigate to `http://127.0.0.1:5000`.
    *   You can now proceed with the demonstration script below.

---

## Part 1: Live Demonstration Script

To begin, navigate to the application's login page in your web browser.

### Scene 1: The Regular User Experience

This demonstrates the system from the perspective of a standard employee or customer.

**Login Credentials:**
*   **Email:** `user@example.com`
*   **Password:** `user`

**Demonstration Steps:**

1.  **Login:**
    *   "First, we'll log in as a regular user, John Doe. After entering his credentials, he is taken directly to his personal dashboard."

2.  **User Dashboard:**
    *   "The dashboard gives the user a quick summary of their privacy status, including a count of their active consents and any open data privacy requests they have submitted."

3.  **My Data:**
    *   Click **"My Data"** in the sidebar.
    *   "The 'My Data' page provides transparency. Here, John can see exactly what personal data the company stores about him, such as his contact information and purchase history. This is a key requirement for data privacy laws."

4.  **Data Subject Request (DSR) Form:**
    *   Click **"DSR"** in the sidebar.
    *   "Under regulations like GDPR, users have the right to request access to or deletion of their data. This form empowers them to do just that."
    *   Select **"Right of Access"** from the dropdown and click **Submit**.
    *   "After submitting, the request appears in the 'My Requests' list below with a 'Pending' status. This provides a clear audit trail for the user."

5.  **My Consents:**
    *   Click **"My Consents"** in the sidebar.
    *   "This page gives users granular control over their consent. Instead of complicated forms, we use simple toggle switches. For example, John can easily revoke his consent for 'Marketing SMS'."
    *   Toggle one of the consents off. Click to another page and then return to show that the choice was saved.

6.  **Access Control:**
    *   "A regular user should not be able to access sensitive areas. If we try to go to the admin-only 'User Management' page, the system correctly denies access." (You can demonstrate this by trying to navigate to an admin URL).

---

### Scene 2: The Data Protection Officer (DPO) Experience

This demonstrates the system from the perspective of a user responsible for managing compliance.

**Login Credentials:**
*   **Email:** `dpo@example.com`
*   **Password:** `dpo`

**Demonstration Steps:**

1.  **Logout and Login as DPO:**
    *   "Now, let's log in as the Data Protection Officer. The DPO has a much more comprehensive view of the system."

2.  **DPO Dashboard:**
    *   "The DPO's dashboard shows organization-wide statistics, including consent statuses across all users and a list of recent DSRs that need attention."

3.  **Review and Fulfill a DSR:**
    *   Click **"DSR"** in the sidebar.
    *   "Here, the DPO can see the 'Right of Access' request that John Doe just submitted. The DPO can review the request and, once fulfilled, update its status."
    *   Find the request and change its status from "Pending" to **"Completed"**.

4.  **Processing Registry:**
    *   Click **"Processing Registry"**.
    *   "This is a critical tool for the DPO. It's a central log of all activities within the company that process personal data, like the HR system or the marketing CRM. The DPO can add, edit, or remove entries to keep this registry up to date."

5.  **Audit Logs:**
    *   Click **"System Audit Logs"**.
    *   "For accountability, every important action is recorded in the audit log. Here, we can see a timestamped record of John Doe submitting his DSR and the DPO completing it just a moment ago."

---

### Scene 3: The Administrator Experience

This demonstrates the system from the perspective of a superuser with full system control.

**Login Credentials:**
*   **Email:** `admin@example.com`
*   **Password:** `admin`

**Demonstration Steps:**

1.  **Logout and Login as Admin:**
    *   "Finally, let's log in as the System Administrator. The Admin has all the powers of a DPO, plus the ability to manage user accounts."

2.  **User Management:**
    *   Click **"User Management"** in the sidebar.
    *   "From this panel, the Admin can create, edit, and delete user accounts and assign roles. Let's quickly add a new user."
    *   Demonstrate adding a new user. Point out that the system requires a strong password.
    *   "We can just as easily edit their role or delete them."

3.  **Security Guardrails:**
    *   "To prevent accidental lock-outs, the system has security checks built-in. An admin cannot delete their own account. Furthermore, if we try to delete the last remaining admin user, the system will prevent it, ensuring an administrator can always access the system."

---

## Part 2: System Architecture & Technology

This section provides a high-level overview of how the system is built.

### How It Works: The Big Picture

The application is built using a modern web architecture that separates the **frontend** (what you see in the browser) from the **backend** (the server-side logic).

1.  **The Frontend (The "Face" of the Application):**
    *   When you visit the website, your browser loads a single HTML file (`index.html`). This file acts as the main "stage."
    *   This stage is brought to life by **JavaScript**, which acts as the "stage crew." When you click a link in the sidebar, the JavaScript code makes a request to the backend to get the necessary data, without needing to reload the entire page.

2.  **The Backend (The "Brain" of the Application):**
    *   The backend is a **Python** application built using the **Flask** framework. It's the "brain" that handles all the logic and data processing.
    *   When it receives a request from the frontend, it communicates with the database to fetch or store information.

3.  **The Database (The "Memory" of the Application):**
    *   The database is a **SQLite** file. This is where all the application's data is stored—user accounts, consents, audit logs, etc.

4.  **Putting It All Together:**
    *   The backend gets data from the database, formats it into a universal format called **JSON**, and sends it back to the frontend.
    *   The JavaScript "stage crew" then takes this data and uses it to build the HTML content (tables, forms, charts) that you see on the page.

This model is known as a **Single Page Application (SPA)**, and it provides a fast and smooth user experience.

### Technologies Used

*   **Backend:**
    *   **Python:** The core programming language.
    *   **Flask:** A lightweight web framework for building the backend API.
    *   **SQLite:** A simple, file-based database.
    *   **Flask-WTF:** A security library used to prevent Cross-Site Request Forgery (CSRF) attacks.
    *   **Werkzeug:** A library used for securely hashing passwords.

*   **Frontend:**
    *   **HTML:** The standard language for structuring the web page.
    *   **JavaScript:** The language that makes the application interactive and dynamic.
    *   **Tailwind CSS:** A modern CSS framework used for styling the user interface.
    *   **Chart.js:** A JavaScript library used to create the interactive charts on the dashboard.
