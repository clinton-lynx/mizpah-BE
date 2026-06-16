import os
import httpx
TERMII_API_KEY = os.getenv("TLJvqirmObbuWlobNPwpTLBaolrCSUNqoKcZWIWXYUGevcrHNVvKiLXXqTvFAK")
TERMII_SENDER_ID = os.getenv("TERMII_SENDER_ID", "mizpah")

async def send_sms(phone: str, message: str):
    url = "https://api.ng.termii.com/api/sms/send"
    payload = {
        "to": phone,
        "from": TERMII_SENDER_ID,
        "sms": message,
        "type": "plain",
        "channel": "generic",
        "api_key": TERMII_API_KEY,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        return response.json()