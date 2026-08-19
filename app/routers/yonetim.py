from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/yonetim")
async def yonetim_ekrani():
    raise HTTPException(status_code=404, detail="Bu sayfa gecici olarak devre disi.")
