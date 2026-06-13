from fastapi import FastAPI, UploadFile, File, Form
from supabase_client import supabase
import uuid

app = FastAPI(title="Mizpah API")


@app.get("/")
def home():
    return {"message": "Mizpah API is live"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/enroll")
async def enroll(
    name: str = Form(...),
    type: str = Form(...),
    blood_type: str = Form(None),
    allergies: str = Form(None),
    conditions: str = Form(None),
    emergency_contact: str = Form(None),
    threat_level: str = Form(None),
    reason: str = Form(None),
    last_seen_location: str = Form(None),
    description: str = Form(None),
    registered_by: str = Form(None),
    added_by: str = Form(None),
    image: UploadFile = File(...),
):
    file_bytes = await image.read()
    filename = f"{uuid.uuid4()}_{image.filename}"

    supabase.storage.from_("face-images").upload(
        filename, file_bytes, {"content-type": image.content_type}
    )

    image_url = supabase.storage.from_("face-images").get_public_url(filename)

    record = {"name": name, "image_url": image_url}

    if type == "watchlist":
        record.update({
            "threat_level": threat_level,
            "reason": reason,
            "added_by": added_by,
        })
        result = supabase.table("watchlist").insert(record).execute()

    elif type == "missing":
        record.update({
            "registered_by": registered_by,
            "last_seen_location": last_seen_location,
            "description": description,
        })
        result = supabase.table("missing_persons").insert(record).execute()

    elif type == "medical":
        record.update({
            "blood_type": blood_type,
            "allergies": allergies.split(",") if allergies else [],
            "conditions": conditions.split(",") if conditions else [],
            "emergency_contact": emergency_contact,
        })
        result = supabase.table("medical_profiles").insert(record).execute()

    else:
        return {"error": "Invalid type. Use watchlist, missing, or medical"}

    return {"success": True, "data": result.data}


@app.post("/scan")
async def scan(image: str = Form(...), mode: str = Form(...)):
    if mode == "active":
        return {
            "matched": True,
            "confidence": 97.4,
            "profile": {
                "name": "Adewale O. Balogun",
                "type": "medical",
                "blood_type": "O+",
                "allergies": ["Penicillin", "Latex"],
                "conditions": ["Type-2 Diabetes"],
                "emergency_contact": "+234 802 345 6789"
            }
        }
    else:
        return {
            "matched": True,
            "confidence": 94.0,
            "profile": {
                "name": "Test Missing Person",
                "type": "missing",
                "last_seen_location": "Main Gate"
            }
        }


@app.post("/demo/reset")
def demo_reset():
    supabase.table("match_events").delete().neq("id", "").execute()
    supabase.table("alerts").delete().neq("id", "").execute()
    return {"status": "reset complete"}