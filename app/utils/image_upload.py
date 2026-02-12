from app.core.cloudinary_config import cloudinary
import cloudinary.uploader

def upload_ngo_image(file):
    result = cloudinary.uploader.upload(
        file,
        folder="ngo_profiles",
        resource_type="image"
    )
    return result["secure_url"]
