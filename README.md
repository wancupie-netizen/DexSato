# DexSato Founder MVP

DexSato is an AI-assisted crypto market intelligence engine.

Founder MVP demonstrates how DexSato analyses multiple markets, produces trading intelligence, displays the results in a web dashboard and sends the same intelligence to Telegram.

---

# Features

- Multi-coin dashboard
- Production trading engine
- Shared dashboard JSON API
- Telegram alerts
- Adaptive historical intelligence
- Clean Founder MVP architecture

Current supported markets:

- BTC
- ETH
- SOL
- XRP
- SUI

---

# Requirements

Python 3.14+

---

# Installation

Clone the repository.

```bash
git clone https://github.com/wancupie-netizen/DexSato.git
```

Enter the project.

```bash
cd DexSato
```

Install dependencies.

```bash
pip install -r requirements.txt
```

---

# Telegram Setup

Create a Telegram Bot using BotFather.

Set the environment variables before starting DexSato.

Windows PowerShell

```powershell
$env:TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
$env:TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
```

Linux / macOS

```bash
export TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
export TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
```

---

# Run

Start DexSato.

```bash
python main.py
```

Open the browser.

```
http://127.0.0.1:8000
```

---

# Dashboard API

```
GET /api/dashboard
```

Example

```text
http://127.0.0.1:8000/api/dashboard
```

---

# Telegram Alert

Send the current dashboard snapshot.

```
POST /telegram/send
```

PowerShell

```powershell
Invoke-RestMethod `
    -Method Post `
    -Uri http://127.0.0.1:8000/telegram/send
```

---

# Health Check

```
GET /health
```

Example

```
http://127.0.0.1:8000/health
```

---

# Founder Workflow

```
git clone

↓

pip install -r requirements.txt

↓

python main.py

↓

Browser Dashboard

↓

BTC
ETH
SOL
XRP
SUI

↓

Telegram Alert
```

---

# Current Founder MVP Scope

Included

- Production engine
- Multi-coin dashboard
- Shared dashboard API
- Telegram integration
- Historical intelligence

Not included

- Login
- User accounts
- Scheduler
- Background workers
- Auto scan
- Portfolio
- Push notifications
- Cloud deployment

---

# Project Structure

```
app/

application/

adaptive/

presentation/

scanner/

tests/
```

---

# Testing

Run the Founder MVP tests.

```bash
python -m pytest
```

---

# License

Founder MVP

Internal evaluation build.