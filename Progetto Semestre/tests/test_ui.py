import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Test UI con Selenium: simulano un utente vero su Chrome (headless).
# Se Chrome non è disponibile i test vengono saltati (vedi conftest.py).


def _wait(driver, timeout=15):
    return WebDriverWait(driver, timeout)


def _type(driver, name, text):
    # Aspetta che il campo sia pronto, poi scrive
    field = _wait(driver).until(
        EC.element_to_be_clickable((By.NAME, name)))
    field.clear()
    field.send_keys(text)


def _click(driver, by, value):
    # Aspetta che l'elemento sia cliccabile prima di cliccare
    _wait(driver).until(EC.element_to_be_clickable((by, value))).click()


def test_register_login_dashboard_flow(driver, live_server):
    # Flusso completo: registrazione -> login -> ricarica -> genera key
    username = f"ui_{int(time.time())}"
    driver.get(live_server)

    # Registrazione
    _click(driver, By.LINK_TEXT, "Registrati")
    _wait(driver).until(EC.url_contains("/register"))
    _type(driver, "username", username)
    _type(driver, "password", "pw123456")
    _click(driver, By.CSS_SELECTOR, "button[type=submit]")
    _wait(driver).until(EC.url_contains("/login"))

    # Login
    _type(driver, "username", username)
    _type(driver, "password", "pw123456")
    _click(driver, By.CSS_SELECTOR, "button[type=submit]")
    _wait(driver).until(EC.url_contains("/dashboard"))

    # Dashboard: la label è renderizzata in maiuscolo via CSS
    _wait(driver).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "SALDO VIRTUALE"))

    # Ricarica saldo di 10 CHF e verifica l'aggiornamento in pagina
    _type(driver, "amount", "10")
    _click(driver, By.XPATH, "//button[contains(., 'Aggiungi CHF')]")
    _wait(driver).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "CHF 10.00"))

    # Generazione API key: appare il messaggio con la chiave
    _click(driver, By.XPATH, "//button[contains(., 'Genera nuova key')]")
    _wait(driver).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "API key generata"))


def test_protected_page_redirects_to_login(driver, live_server):
    # Un utente non loggato che apre /dashboard viene mandato al login
    driver.get(f"{live_server}/dashboard")
    _wait(driver).until(EC.url_contains("/login"))
    _wait(driver).until(EC.presence_of_element_located((By.NAME, "username")))
