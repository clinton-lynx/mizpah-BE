from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from supabase_client import supabase
import uuid
import httpx
import base64
app = FastAPI(title="Mizpah API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateReportRequest(BaseModel):
    person_id: str
    report_type: str  # "watchlist" or "missing"
    threat_level: Optional[str] = None
    reason: Optional[str] = None
    last_seen_location: Optional[str] = None
    description: Optional[str] = None
    flagged_by: Optional[str] = None


class UpdateReportRequest(BaseModel):
    status: Optional[str] = None
    threat_level: Optional[str] = None
    reason: Optional[str] = None


class ScanRequest(BaseModel):
    image: str
    mode: str


async def enroll_face_embedding(image_bytes: bytes, enrolled_id, profile_type: str):
    if not enrolled_id:
        return

    try:
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        async with httpx.AsyncClient(timeout=60) as client:
            ml_response = await client.post(
                "https://mizpah-ml.onrender.com/enroll",
                json={
                    "image": image_b64,
                    "person_id": str(enrolled_id),
                    "type": profile_type,
                },
            )
            print("ML enroll response:", ml_response.json())
    except Exception as ml_error:
        print("ML enroll failed:", str(ml_error))


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
    try:
        file_bytes = await image.read()
        filename = f"{uuid.uuid4()}_{image.filename}"

        upload_result = supabase.storage.from_("face-images").upload(
            filename, file_bytes, {"content-type": image.content_type}
        )
        print("Upload result:", upload_result)

        image_url = supabase.storage.from_("face-images").get_public_url(filename)
        print("Image URL:", image_url)

        record = {"name": name, "image_url": image_url}

        if type == "watchlist":
            record.update({
                "threat_level": threat_level,
                "reason": reason,
                "added_by": added_by,
            })
            result = supabase.table("watchlist").insert(record).execute()
            enrolled_id = result.data[0]["id"] if result.data else None
            await enroll_face_embedding(file_bytes, enrolled_id, type)
        elif type == "missing":
            record.update({
                "registered_by": registered_by,
                "last_seen_location": last_seen_location,
                "description": description,
            })
            result = supabase.table("missing_persons").insert(record).execute()
            enrolled_id = result.data[0]["id"] if result.data else None
            await enroll_face_embedding(file_bytes, enrolled_id, type)
        elif type == "medical":
            record.update({
                "blood_type": blood_type,
                "allergies": allergies.split(",") if allergies else [],
                "conditions": conditions.split(",") if conditions else [],
                "emergency_contact": emergency_contact,
            })
            result = supabase.table("medical_profiles").insert(record).execute()
            enrolled_id = result.data[0]["id"] if result.data else None
            await enroll_face_embedding(file_bytes, enrolled_id, type)
        else:
            return {"error": "Invalid type. Use watchlist, missing, or medical"}

        return {"success": True, "data": result.data}

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("ENROLL ERROR:", error_detail)
        return {"success": False, "error": str(e), "traceback": error_detail}


@app.get("/profiles")
def get_profiles():
    try:
        watchlist = supabase.table("watchlist").select("*").execute()
        missing = supabase.table("missing_persons").select("*").execute()
        medical = supabase.table("medical_profiles").select("*").execute()

        profiles = []
        for p in watchlist.data:
            p["type"] = "watchlist"
            profiles.append(p)
        for p in missing.data:
            p["type"] = "missing"
            profiles.append(p)
        for p in medical.data:
            p["type"] = "medical"
            profiles.append(p)

        return {"profiles": profiles}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.post("/scan")
async def scan(req: ScanRequest):
    image = req.image
    mode = req.mode
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://mizpah-ml.onrender.com/scan",
                json={"image": image, "mode": mode}
            )
            result = response.json()
            print(result)

            # Log match event if matched
            if result.get("matched"):
                matched_profile = result.get("profile") or result.get("matched_profile") or {}
                matched_person_id = (
                    matched_profile.get("person_id")
                    if isinstance(matched_profile, dict)
                    else None
                ) or result.get("person_id")

                if matched_person_id:
                    profile_result = (
                        supabase.table("medical_profiles")
                        .select("*")
                        .eq("id", matched_person_id)
                        .execute()
                    )
                    full_profile = profile_result.data[0] if profile_result.data else result.get("profile")

                    reports_result = (
                        supabase.table("reports")
                        .select("*")
                        .eq("person_id", matched_person_id)
                        .eq("status", "active")
                        .execute()
                    )
                    reports = reports_result.data if reports_result.data else []

                    result["profile"] = full_profile
                    result["reports"] = reports

                supabase.table("match_events").insert({
                    "person_id": None,
                    "confidence": result.get("confidence"),
                    "use_case_type": mode,
                    "location": "camera-feed",
                }).execute()

            return result
    except Exception as e:
        return {"error": str(e), "matched": False}

@app.post("/demo/reset")
def demo_reset():
    supabase.table("match_events").delete().neq("id", "").execute()
    supabase.table("alerts").delete().neq("id", "").execute()
    return {"status": "reset complete"}
from termii import send_sms

@app.post("/alert/confirm")
async def confirm_alert(
    match_event_id: str = Form(...),
    person_name: str = Form(...),
    emergency_contact: str = Form(...),
    location: str = Form(...),
    actioned_by: str = Form(...),
):
    try:
        alert = supabase.table("alerts").insert({
            "match_event_id": match_event_id,
            "channel": "SMS",
            "recipient": emergency_contact,
            "status": "sent",
        }).execute()

        message = (
            f"MIZPAH ALERT: {person_name} has been located at {location}. "
            f"Please contact {actioned_by} immediately."
        )
        sms_result = await send_sms(emergency_contact, message)

        return {
            "success": True,
            "alert": alert.data,
            "sms": sms_result
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
@app.post("/demo/reset")
def demo_reset():
    supabase.table("match_events").delete().neq("id", "").execute()
    supabase.table("alerts").delete().neq("id", "").execute()
    return {"status": "reset complete"}


# ADD THIS BELOW ↓
@app.get("/cases")
def get_cases():
    watchlist = supabase.table("watchlist").select("*").execute()
    missing = supabase.table("missing_persons").select("*").execute()
    medical = supabase.table("medical_profiles").select("*").execute()
    return {
        "watchlist": watchlist.data,
        "missing_persons": missing.data,
        "medical_profiles": medical.data
    }


@app.post("/reports")
def create_report(req: CreateReportRequest):
    record = {
        "person_id": req.person_id,
        "report_type": req.report_type,
        "threat_level": req.threat_level,
        "reason": req.reason,
        "last_seen_location": req.last_seen_location,
        "description": req.description,
        "flagged_by": req.flagged_by,
    }
    result = supabase.table("reports").insert(record).execute()
    return {"success": True, "data": result.data}


@app.get("/reports")
def get_reports(person_id: Optional[str] = None):
    query = supabase.table("reports").select("*")
    if person_id:
        query = query.eq("person_id", person_id)
    result = query.execute()
    return {"reports": result.data}


@app.patch("/reports/{report_id}")
def update_report(report_id: str, req: UpdateReportRequest):
    update_data = {k: v for k, v in req.dict().items() if v is not None}
    result = supabase.table("reports").update(update_data).eq("id", report_id).execute()
    return {"success": True, "data": result.data}


@app.get("/match-events")
def get_match_events():
    result = (
        supabase.table("match_events")
        .select("*")
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return {"match_events": result.data}
    
