from fastapi import APIRouter, UploadFile, File

async def upload_image(image: UploadFile = File(...)):
    save_path = f"uploads/{image.filename}"

    with open(save_path, "wb") as f:
        f.write(await image.read())

    image_url = f"http://localhost:8000/{save_path}"
    return {"imageUrl": image_url}
