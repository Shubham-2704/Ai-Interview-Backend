from fastapi.responses import JSONResponse
from bson import ObjectId

def success_response(message: str, data=None, status_code: int = 200):
    return JSONResponse(
        status_code=status_code,
        content={
            "message": message,
            "data": data
        }
    )

def error_response(status_code: int, message: str):
    return JSONResponse(
        status_code=status_code,
        content={"message": message}
    )

def serialize_doc(doc: dict):
    if not doc:
        return doc

    # convert ObjectId → string (keep `_id`)
    if isinstance(doc.get("_id"), ObjectId):
        doc["_id"] = str(doc["_id"])
        doc["id"] = str(doc["_id"])

    # convert other ObjectIds in document
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)

        if isinstance(value, list):
            doc[key] = [
                str(v) if isinstance(v, ObjectId) else v
                for v in value
            ]

    return doc


async def serialize_cursor(cursor):
    docs = []
    async for doc in cursor:
        docs.append(serialize_doc(doc))
    return docs
