from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas import FeatureQueryParams, QueryParams
from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.models import User
from app.service.geo.match_input_tip import match_custom_feature
from app.service.user.core.database import get_db as get_db_custom
from app.service.user.submission.get_custom import get_from_submission

router = APIRouter()


@router.get("/get_custom")
async def query_location_data(
    locations: List[str] = Query(..., description="Target locations"),
    regions: List[str] = Query(..., description="Target regions"),
    need_features: str = Query(..., description="Feature filters, comma-separated"),
    phonology: Optional[str] = Query(
        None,
        description="Optional 聲韻調 filters (聲母/韻母/聲調), comma-separated",
    ),
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(get_current_user),
):
    """
    Query custom records by location/region + 特徵, with optional 聲韻調 filter.
    Backward compatible:
    - If `phonology` is not provided, behavior is unchanged.
    - If `phonology` is provided, apply extra filter on Information.聲韻調.
    """
    features_list = [f.strip() for f in need_features.split(",") if f.strip()]
    phonology_list = [p.strip() for p in phonology.split(",") if p.strip()] if phonology else None

    query_params = QueryParams(
        locations=locations,
        regions=regions,
        need_features=features_list,
    )
    try:
        result = get_from_submission(
            query_params.locations,
            query_params.regions,
            query_params.need_features,
            user,
            db,
            phonology_list,
        )
        return result if result else []
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        print("query_location_data")


@router.get("/get_custom_feature")
async def get_custom_feature(
    locations: List[str] = Query(..., description="Target locations"),
    regions: List[str] = Query(..., description="Target regions"),
    word: str = Query(..., description="Input keyword for feature matching"),
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(get_current_user),
):
    """
    Match custom features for the current user by input keyword.
    """
    query_params = FeatureQueryParams(locations=locations, regions=regions, word=word)
    try:
        result = match_custom_feature(
            query_params.locations,
            query_params.regions,
            query_params.word,
            user,
            db,
        )
        return result if result else []
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        print("get_custom_feature")
