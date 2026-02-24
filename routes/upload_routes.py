from typing import Dict
from fastapi import APIRouter, UploadFile, File, HTTPException
from datetime import datetime
import os
import os
import cloudinary
import cloudinary.uploader  
import traceback

# async def upload_image(image: UploadFile = File(...)):
#     save_path = f"uploads/{image.filename}"

#     with open(save_path, "wb") as f:
#         f.write(await image.read())

#     image_url = f"{os.getenv("PHOTO_URL")}/{save_path}"
#     return {"imageUrl": image_url}

# Configure Cloudinary
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Configure Cloudinary SDK
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True  # Use HTTPS
)

async def upload_image(image: UploadFile = File(...)) -> Dict:
    """
    Upload image to Cloudinary and return the URL
    """
    try:
        # Validate credentials
        if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
            raise HTTPException(
                status_code=500, 
                detail="Cloudinary credentials not configured"
            )
        
        # Validate file exists
        if not image:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Read file
        image_data = await image.read()
        
        # Check empty file
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Check file size (Cloudinary free limit is 100MB for upload_large, 10MB for normal upload)
        file_size_mb = len(image_data) / (1024 * 1024)
        if file_size_mb > 100:
            raise HTTPException(status_code=400, detail=f"File too large: {file_size_mb:.2f}MB (max 100MB)")
        
        # Check file type
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
        if image.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {image.content_type}")
        
        # Generate a unique public ID
        timestamp = int(datetime.now().timestamp())
        public_id = f"profile_{timestamp}"
        
        # Upload to Cloudinary
        # For files under 10MB, use upload
        # For larger files (up to 100MB), use upload_large
        upload_method = cloudinary.uploader.upload_large if file_size_mb > 10 else cloudinary.uploader.upload
        
        upload_result = upload_method(
            image_data,
            public_id=public_id,
            folder="profile_photos",
            overwrite=True,
            resource_type="image",
            transformation=[
                {"width": 300, "height": 300, "crop": "fill", "gravity": "face"},  # Auto-crop to face
                {"quality": "auto:good", "fetch_format": "auto"}  # Auto-optimize
            ]
        )
        
        # Get the secure URL (HTTPS)
        image_url = upload_result['secure_url']
        
        # Optional: Get delete token for future deletion
        delete_token = upload_result.get('delete_token')
        
        print(f"✅ Upload successful: {image_url}")
        
        return {
            "success": True,
            "imageUrl": image_url,
            "public_id": upload_result['public_id'],
            "delete_token": delete_token,
            "service": "cloudinary",
            "size_kb": len(image_data) / 1024
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        await image.close()