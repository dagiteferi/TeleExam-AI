import asyncio
import httpx
import uuid

async def main():
    base_url = "http://127.0.0.1:8000"
    
    # 1. First, create the inviter
    inviter_id = 999111
    inviter_payload = {
        "telegram_id": inviter_id,
        "first_name": "InviterUser"
    }
    
    async with httpx.AsyncClient(base_url=base_url) as client:
        # Create inviter
        resp1 = await client.post("/api/users/upsert", json=inviter_payload, headers={
            "X-Telegram-Secret": "telexam_2026_super_secret_change_me_in_production",
            "X-Telegram-Id": str(inviter_id)
        })
        if resp1.status_code != 200:
            print("Failed to create inviter:", resp1.text)
            return
            
        inviter_data = resp1.json()
        invite_code = inviter_data["invite_code"]
        print("Inviter created with code:", invite_code)
        print("Initial invite_count:", inviter_data["invite_count"])
        
        # 2. Emulate AutoUpsertMiddleware for a exact NEW user using the ref_code
        invitee_id = 999222
        invitee_payload = {
            "telegram_id": invitee_id,
            "first_name": "InviteeUser",
            "ref_code": invite_code
        }
        
        resp2 = await client.post("/api/users/upsert", json=invitee_payload, headers={
            "X-Telegram-Secret": "telexam_2026_super_secret_change_me_in_production",
            "X-Telegram-Id": str(invitee_id)
        })
        if resp2.status_code != 200:
            print("Failed to create invitee:", resp2.text)
            return
            
        invitee_data = resp2.json()
        print("Invitee created.")
        
        # 3. Check inviter's invite_count again
        resp3 = await client.post("/api/users/upsert", json={"telegram_id": inviter_id}, headers={
            "X-Telegram-Secret": "telexam_2026_super_secret_change_me_in_production",
            "X-Telegram-Id": str(inviter_id)
        })
        
        inviter_updated = resp3.json()
        print("Updated inviter count:", inviter_updated["invite_count"])

if __name__ == "__main__":
    asyncio.run(main())
