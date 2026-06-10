from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    # PROCURADURIA
    page.goto("https://www.procuraduria.gov.co/Pages/Generacion-de-antecedentes.aspx")
    page.wait_for_timeout(5000)
    page.goto("https://apps.procuraduria.gov.co/WEBCERT/Certificado.aspx")
    page.wait_for_timeout(3000)
    selects = page.eval_on_selector_all("select", "els => els.map(e => e.id + '|' + e.name)")
    inputs = page.eval_on_selector_all("input[type='text']", "els => els.map(e => e.id + '|' + e.name)")
    print("PROCURADURIA selects:", selects)
    print("PROCURADURIA inputs:", inputs)

    # POLICIA
    page.goto("https://antecedentes.policia.gov.co:7005/WebJudicial/index.xhtml")
    page.wait_for_timeout(3000)
    radios = page.eval_on_selector_all("input[type='radio']", "els => els.map(e => e.id + '|' + e.value + '|' + e.name)")
    buttons = page.eval_on_selector_all("button, input[type='submit'], input[type='button']", "els => els.map(e => e.id + '|' + e.value + '|' + e.textContent)")
    print("POLICIA radios:", radios)
    print("POLICIA buttons:", buttons)

    # FISCAL
    page.goto("https://www.contraloria.gov.co/web/guest/persona-natural")
    page.wait_for_timeout(5000)
    selects2 = page.eval_on_selector_all("select", "els => els.map(e => e.id + '|' + e.name)")
    print("FISCAL selects:", selects2)

    input("Presiona Enter para cerrar...")
    browser.close()
