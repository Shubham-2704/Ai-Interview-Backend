from fastapi.responses import JSONResponse

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