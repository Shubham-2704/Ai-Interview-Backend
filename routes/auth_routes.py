from controllers.auth_controller import *
from models.user_model import *
from routes.upload_routes import *

router = APIRouter(prefix="/api/auth", tags=["Auth"])

router.post("/register")(register_user)
router.post("/login")(login_user)
router.post("/upload-image")(upload_image)
router.get("/profile")(get_profile)