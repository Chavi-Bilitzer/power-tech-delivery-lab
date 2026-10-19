from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()

deliveries_db = {}
next_id = 1

VALID_STATUSES = ["created", "in_transit", "delivered"]

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid payload format or missing required fields"}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/deliveries", status_code=201)
async def create_delivery(request: Request):
    global next_id
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    if not isinstance(data, dict):
        return JSONResponse(status_code=400, content={"error": "Body must be a JSON object"})

    recipient = data.get("recipient")
    address = data.get("address")

    if not isinstance(recipient, str) or not recipient.strip():
        return JSONResponse(status_code=400, content={"error": "Recipient must be a non-empty string"})
    
    if not isinstance(address, str) or not address.strip():
        return JSONResponse(status_code=400, content={"error": "Address must be a non-empty string"})

    delivery = {
        "id": next_id,
        "recipient": recipient,
        "address": address,
        "status": "created"
    }
    deliveries_db[next_id] = delivery
    next_id += 1

    return delivery

@app.get("/deliveries")
def list_deliveries(status: Optional[str] = None):
    if status is not None:
        if status not in VALID_STATUSES:
            return JSONResponse(status_code=400, content={"error": "Invalid status filter"})
        return [d for d in deliveries_db.values() if d["status"] == status]
    return list(deliveries_db.values())

@app.get("/deliveries/{delivery_id}")
def get_delivery(delivery_id: int):
    if delivery_id not in deliveries_db:
        return JSONResponse(status_code=404, content={"error": "Delivery not found"})
    return deliveries_db[delivery_id]

@app.patch("/deliveries/{delivery_id}/status")
async def update_status(delivery_id: int, request: Request):
    if delivery_id not in deliveries_db:
        return JSONResponse(status_code=404, content={"error": "Delivery not found"})

    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    if not isinstance(data, dict) or "status" not in data:
        return JSONResponse(status_code=400, content={"error": "Missing status field"})

    new_status = data["status"]
    if new_status not in VALID_STATUSES:
        return JSONResponse(status_code=400, content={"error": "Unknown status"})

    current_status = deliveries_db[delivery_id]["status"]

    if current_status == "created" and new_status == "in_transit":
        deliveries_db[delivery_id]["status"] = new_status
    elif current_status == "in_transit" and new_status == "delivered":
        deliveries_db[delivery_id]["status"] = new_status
    else:
        return JSONResponse(status_code=409, content={"error": "Invalid status transition"})

    return deliveries_db[delivery_id]

@app.delete("/deliveries/{delivery_id}")
def delete_delivery(delivery_id: int):
    if delivery_id not in deliveries_db:
        return JSONResponse(status_code=404, content={"error": "Delivery not found"})

    if deliveries_db[delivery_id]["status"] != "created":
        return JSONResponse(
            status_code=409, 
            content={"error": "Only deliveries with 'created' status can be deleted"}
        )

    del deliveries_db[delivery_id]
    return Response(status_code=204)
