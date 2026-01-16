from controllers.auth_controller import *
from models.user_model import *
from routes.upload_routes import *

router = APIRouter(prefix="/api/auth", tags=["Auth"])

router.post("/register")(register_user)
router.post("/login")(login_user)
router.post("/upload-image")(upload_image)
router.get("/profile")(get_profile)
router.put("/profile")(update_profile)
router.post("/forgot-password")(forgot_password)
router.post("/verify-reset-otp")(verify_reset_otp)
router.post("/reset-password")(reset_password)
router.post("/verify-admin-token")(verify_admin_token)