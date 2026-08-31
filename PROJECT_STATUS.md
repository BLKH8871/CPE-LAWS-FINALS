# Project Status: Web-Based Data Privacy Compliance Management System

**Last Updated:** 2026-07-22

## 1. Project Overview

This is a web-based system for managing data privacy compliance, created for a Computer Engineering (CpE) Laws course project. It is designed to help organizations track and manage their data privacy obligations under regulations like GDPR or the Data Privacy Act.

## 2. System Architecture

*   **Backend:** Flask (Python)
*   **Frontend:** Single Page Application (SPA) model. The entire user interface is rendered within `templates/index.html`. JavaScript is used to dynamically fetch data from the Flask backend API and update the content of the page without full page reloads.
*   **Database:** SQLite (`compliance_system.db`)
*   **Styling:** Tailwind CSS (via CDN)
*   **JavaScript Libraries:**
    *   **Chart.js:** For data visualizations (e.g., compliance score doughnut chart).
    *   **Quill.js:** For the rich text editor used in the Privacy Notice module.
*   **Authentication:** Custom Role-Based Access Control (RBAC) implemented via a `@login_required` decorator in Flask. Passwords are hashed using `werkzeug`.
*   **Environment:** Uses `python-dotenv` to manage environment variables (e.g., `SECRET_KEY`) from a `.env` file.

## 3. Implemented Features & Modules

The following features are implemented, at least for viewing data:

*   **Dashboard:** Shows a general compliance overview, including a compliance score chart.
*   **User Profile:** Allows users to see their own information.
*   **Consent Management:** A page to view user consent records.
*   **System Audit Logs:** Displays a log of actions performed within the system, captured via a custom `@audit_log` decorator.
*   **Data Subject Requests (DSR):** A module for viewing and managing requests from data subjects (e.g., access, deletion).
*   **Privacy Notices:** A section to create and manage privacy notices using a rich text editor.
*   **Processing Activities Registry:** A registry for documenting data processing activities.
*   **Reporting Module:** A placeholder for generating compliance reports.

## 4. Recent Changes & Fixes

*   **Fixed "Stuck Page" Bug (July 2026):**
    *   **Problem:** Navigating to "Consent Management", "System Audit Logs", and "DSR Requests" would change the page title but the main content area would remain stuck on the previously viewed page.
    *   **Root Cause:** The JavaScript functions responsible for loading these pages (`loadMyConsents`, `loadAuditLogs`, `loadDsrRequests`) did not have a "loading" state. If a fetch request failed for any reason, the function would error out before updating the content, leaving the old content visible.
    *   **Solution:** Modified the functions in `templates/index.html` to immediately set the content to a "Loading..." message, and wrapped the fetch logic in `try...catch` blocks to display an error message if the data fails to load.

*   **Fixed Favicon Errors (July 2026):** Added a route for `/favicon.ico` in `app.py` to prevent browsers from generating 404/500 errors in the application logs on every page load.

## 5. Key Files

*   `app.py`: The core Flask application. Contains all API routes, database interaction logic, and business logic.
*   `templates/index.html`: The single HTML file for the entire frontend. It contains the navigation structure and the JavaScript code for dynamically loading all modules.
*   `compliance_system.db`: The SQLite database file.
*   `.env`: Stores confidential configuration like the Flask `SECRET_KEY`.
*   `requirements.txt`: Lists the required Python packages for the project.

## 6. How to Use This Document

In future sessions, you can ask me to read this file (`PROJECT_STATUS.md`) to quickly get me up to speed on the project's status, architecture, and recent history.
