
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def verify_admin_audit_log():
    """
    Logs in as an Admin, navigates to the audit log, and prints the log table.
    """
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    wait = WebDriverWait(driver, 10)

    try:
        # 1. Navigate to the login page
        driver.get("http://127.0.0.1:5000/login")

        # 2. Log in as Admin
        wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys("admin@example.com")
        driver.find_element(By.NAME, "password").send_keys("admin")
        driver.find_element(By.TAG_NAME, "button").click()

        # 3. Navigate to Audit Logs
        wait.until(EC.element_to_be_clickable((By.ID, "link-audit-logs"))).click()

        # Wait for the table to be loaded
        log_table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".data-table tbody")))

        # Allow some time for content to render
        time.sleep(2)

        # 4. Print table content
        print("--- Audit Log Table Content ---")
        header = [th.text for th in driver.find_elements(By.CSS_SELECTOR, ".data-table thead th")]
        print("\t".join(header))
        rows = log_table.find_elements(By.TAG_NAME, "tr")
        if not rows or "No audit logs found" in rows[0].text:
            print("No audit logs found or table is empty.")
        else:
            for row in rows:
                cells = [cell.text for cell in row.find_elements(By.TAG_NAME, "td")]
                print("\t".join(cells))
        print("-----------------------------")

        # 5. Take screenshot
        screenshot_path = "admin_audit_logs_after_fix.png"
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    verify_admin_audit_log()
