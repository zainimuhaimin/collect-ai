from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get(
    "/test",
    summary="Health check",
    description="Penanda service backend hidup dan bisa dijangkau. Tidak menyentuh database atau layer lain sama sekali.",
    response_description="Pesan konfirmasi sederhana.",
)
def test_service():
    return {"message": "Hello from backend"}
