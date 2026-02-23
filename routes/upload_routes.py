from fastapi import APIRouter, UploadFile, File, HTTPException
from datetime import datetime
import os
import os
import httpx  
import traceback
import base64

# async def upload_image(image: UploadFile = File(...)):
#     save_path = f"uploads/{image.filename}"

#     with open(save_path, "wb") as f:
#         f.write(await image.read())

#     image_url = f"{os.getenv("PHOTO_URL")}/{save_path}"
#     return {"imageUrl": image_url}

IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")  
IMGBB_UPLOAD_URL = os.getenv("IMGBB_UPLOAD_URL")

async def upload_image(image: UploadFile = File(...)):
    try:
        # Validate API key
        if not IMGBB_API_KEY:
            raise HTTPException(status_code=500, detail="IMGBB_API_KEY not configured")
        
        # Validate file exists
        if not image:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Read file
        image_data = await image.read()
        
        # Check empty file
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Check file size (32MB max)
        file_size_mb = len(image_data) / (1024 * 1024)
        if file_size_mb > 32:
            raise HTTPException(status_code=400, detail=f"File too large: {file_size_mb:.2f}MB (max 32MB)")
        
        # Check file type
        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"]
        if image.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {image.content_type}")
        
        # Convert to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Prepare payload
        payload = {
            'key': IMGBB_API_KEY,
            'image': image_base64,
            'name': f"profile_{datetime.now().timestamp()}",
            'expiration': 0
        }
        
        # Upload to ImgBB
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(IMGBB_UPLOAD_URL, data=payload)
            
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail=f"ImgBB error: {response.status_code}")
            
            imgbb_response = response.json()
            
            if not imgbb_response.get('success'):
                raise HTTPException(status_code=502, detail="ImgBB upload failed")
            
            return {
                "success": True,
                "imageUrl": imgbb_response['data']['url'],
                "delete_url": imgbb_response['data']['delete_url']
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        await image.close()