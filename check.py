import os
import smtplib
from email.message import EmailMessage

import requests
from playwright.sync_api import sync_playwright

URL = "https://broneering.mfa.ee/en/"
KEYWORD = "Long-stay visa"


def env(name, default=""):
    return (os.getenv(name) or default).strip()


def send_ntfy(msg):
    topic = env("NTFY_TOPIC")
    if not topic:
        return
    requests.post(
        f"https://ntfy.sh/{topic}",
        data=msg.encode("utf-8"),
        headers={"Title": "D-visa slot OPEN", "Priority": "urgent",
                 "Tags": "rotating_light", "Click": URL},
        timeout=15,
    )


def send_email(msg):
    user, pwd = env("SMTP_USER"), env("SMTP_PASS")
    if not (user and pwd):
        return
    m = EmailMessage()
    m["From"], m["To"] = user, env("EMAIL_TO", user)
    m["Subject"] = "D-visa slot OPEN - Estonia Embassy New Delhi"
    m.set_content(msg)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pwd)
        s.send_message(m)


def send_whatsapp(msg):
    sid, token, to = env("TWILIO_SID"), env("TWILIO_TOKEN"), env("WA_TO")
    if not (sid and token and to):
        return
    r = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        auth=(sid, token),
        data={"From": env("TWILIO_WA_FROM", "whatsapp:+14155238886"),
              "To": to, "Body": msg},
        timeout=20,
    )
    r.raise_for_status()


def alert(msg):
    for fn in (send_ntfy, send_email, send_whatsapp):
        try:
            fn(msg)
            print(f"{fn.__name__}: done")
        except Exception as e:
            print(f"{fn.__name__} FAILED: {e}")


if env("TEST_ALERT") == "true":
    alert(f"TEST alert from your Estonia slot watcher. Booking site: {URL}")
    raise SystemExit(0)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(URL, timeout=45000)

    first = page.locator("select").first
    first.wait_for(timeout=20000)
    target = next((o for o in first.locator("option").all_inner_texts()
                   if "New Delhi" in o), None)
    if not target:
        raise SystemExit("New Delhi option not found - site layout changed?")
    first.select_option(label=target)

    found = False
    for _ in range(12):
        page.wait_for_timeout(1000)
        selects = page.locator("select")
        for i in range(1, selects.count()):
            texts = selects.nth(i).locator("option").all_inner_texts()
            if any(KEYWORD.lower() in t.lower() for t in texts):
                found = True
        if found:
            break

    print("SLOT OPEN" if found else "no slot")
    if found:
        alert(f"Estonia Embassy New Delhi: '{KEYWORD}' is selectable NOW! Book: {URL}")
    browser.close()
