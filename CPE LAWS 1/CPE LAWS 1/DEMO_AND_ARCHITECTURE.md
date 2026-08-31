# Data Privacy Compliance Management System: Demo and Architecture

This document provides a comprehensive overview of the Data Privacy Compliance Management System, including its architecture, setup instructions, and a detailed demonstration of its features.

## 1. Project Overview

This web application is a robust tool designed to help organizations manage their data privacy compliance obligations. It provides a centralized platform for Data Protection Officers (DPOs), System Administrators, and regular users to interact with and manage data privacy-related tasks.

The system is built on a modern web stack and is designed to be both secure and user-friendly. It incorporates role-based access control to ensure that users only have access to the features and data relevant to their roles.

## 2. System Architecture

The application follows a monolithic architecture, with a Python Flask backend and a dynamic, single-page application (SPA) frontend.

### 2.1 Backend Architecture

*   **Framework:** The backend is built using **Flask**, a lightweight and flexible Python web framework.
*   **Database:** The system uses **SQLite** as its database, which is a serverless, self-contained, and transactional SQL database engine. The database schema is designed to store user data, audit logs, consent records, data subject requests (DSRs), and other compliance-related information.
*   **Authentication:** User authentication is handled using password hashing (via `werkzeug.security`) and session management.
*   **Role-Based Access Control (RBAC):** The application implements a clear RBAC model with three distinct roles:
    *   **User:** Standard users who can manage their own consents and data.
    *   **DPO (Data Protection Officer):** Responsible for overseeing the organization's data protection strategy and implementation.
    *   **Admin:** System administrators responsible for user management and system configuration.
*   **API Endpoints:** The backend exposes a series of RESTful API endpoints that the frontend consumes to fetch and manipulate data.

### 2.2 Frontend Architecture

*   **Structure:** The frontend is a **Single-Page Application (SPA)**, where content is dynamically loaded without requiring full page reloads. This provides a fast and responsive user experience.
*   **Styling:** The UI is styled using **Tailwind CSS**, a utility-first CSS framework that allows for rapid and consistent styling.
*   **JavaScript:** The frontend logic is written in vanilla JavaScript, which handles API calls, DOM manipulation, and dynamic content rendering.
*   **Charting:** The DPO and Admin dashboards feature data visualizations powered by **Chart.js**, a popular JavaScript charting library.

## 3. How to Run the Application

To run the application locally, follow these steps:

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url>
    cd <project-directory>
    ```

2.  **Set Up the Virtual Environment:**
    *It is recommended to use a virtual environment to manage project dependencies.*
    ```bash
    # Create the virtual environment
    python -m venv test_venv

    # Activate the virtual environment
    # On Windows:
    .\\test_venv\\Scripts\\activate
    # On macOS/Linux:
    source test_venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Initialize the Database:**
    *This will create the `compliance_system.db` file and populate it with the necessary tables and seed data.*
    ```bash
    python init_db.py
    ```

5.  **Run the Application:**
    ```bash
    flask run
    ```
    The application will be available at `http://127.0.0.1:5000`.

## 4. Demo: Features by User Role

The application provides different features based on the user's role. Here are the default credentials for each role:

*   **Admin:** `admin@example.com` / `password`
*   **DPO:** `dpo@example.com` / `password`
*   **User:** `user@example.com` / `password`

### 4.1 User Role

**Dashboard:**
*   A personalized dashboard that provides a quick overview of active consents and open DSRs.

**Consent Management:**
*   Users can view a list of their consents and their current status (e.g., "Active," "Revoked").
*   They can grant or revoke consent for different data processing activities.

**My Data:**
*   This section is intended to show users the personal data that the organization processes about them. *(Note: The UI for this page needs improvement, as it currently displays a raw JSON output.)*

**DSR:**
*   Users can submit Data Subject Requests (DSRs), such as the right to access, rectify, or erase their data.

### 4.2 DPO Role

**Dashboard:**
*   A comprehensive dashboard with key compliance metrics, including consent statistics, recent DSR activity, and an overall compliance score.

**Data Processing Registry:**
*   DPOs can manage a registry of all data processing activities within the organization. This includes adding, editing, and deleting entries.

**Privacy Notices:**
*   This module allows DPOs to create, edit, and publish privacy notices.

**DSR Management:**
*   DPOs can view and manage all DSRs submitted by users. They can update the status of requests and add resolution notes.

**Reporting:**
*   This section is intended to provide reporting and export capabilities for compliance documentation. *(Note: This feature is not yet implemented.)*

### 4.3 Admin Role

**Dashboard:**
*   The Admin dashboard provides an overview of system-level metrics, such as the total number of users, the distribution of user roles, and recent security-related audit events.

**User Management:**
*   Admins have full control over user accounts. They can add, edit, and delete users, as well as assign roles.

**System Audit Logs:**
*   Admins can view a filtered list of security-critical audit logs, such as login attempts, user creation, and deletions. *(Note: There appears to be a bug in the filtering logic for this feature.)*

This document provides a solid starting point for understanding and working with the Data Privacy Compliance Management System. The next steps will involve addressing the identified bugs and areas for improvement to further enhance the application's functionality and user experience.
