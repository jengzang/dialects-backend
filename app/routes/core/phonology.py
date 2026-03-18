# routes/phonology.py
"""
[PKG] 璺敱妯″锛氳檿鐞?/api/phonology 闊抽熁鍒嗘瀽璜嬫眰銆?涓嶆敼鍕曞師閭忚集锛屽皣鍘熶締 app.py 涓皪鎳夋帴鍙ｇЩ鍑恒€?"""

import asyncio
import json
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.sql.db_selector import get_dialects_db, get_query_db
# from app.auth.dependencies import get_current_user
# from app.logging.dependencies.limiter import ApiLimiter
# from app.auth.models import User
from app.schemas import AnalysisPayload, FeatureStatsRequest

from app.service.core.feature_stats import get_feature_counts, get_feature_statistics, generate_cache_key
from app.service.core.phonology2status import pho2sta
from app.service.core.status_arrange_pho import sta2pho
from app.common.path import QUERY_DB_USER, DIALECTS_DB_ADMIN, DIALECTS_DB_USER
from app.redis_client import redis_client

router = APIRouter()


@router.post("/phonology")
async def api_run_phonology_analysis(
        payload: AnalysisPayload,
        dialects_db: str = Depends(get_dialects_db),
        query_db: str = Depends(get_query_db)
):
    """
     - 鐢ㄤ簬 /api/phonology 璺敱鐨勮几鍏ョ壒寰碉紝鍒嗘瀽鑱查熁銆?    :param payload: - mode: p2s-鏌ヨ闊充綅鏌ヨ鐨勪腑鍙や締婧?s2p-鎸変腑鍙ゅ湴浣嶆煡瑭㈤煶鍊?    - locations: 杓稿叆鍦伴粸锛堝彲澶氬€嬶級
    - regions: 杓稿叆鍒嗗崁锛堟煇涓€绱氬垎鍗€锛屼緥濡傚逗鍗楋紝鍙鍊嬶級
    - features: 瑕佹煡瑭㈢殑鐗瑰镜锛堣伈姣?闊绘瘝/鑱茶锛夊繀闋堝畬鍏ㄥ尮閰嶏紝鐢ㄧ箒楂斿瓧
    - status_inputs: 瑕佹煡瑭㈢殑涓彜鍦颁綅锛屽彲甯堕鍚嶏紙渚嬪鑾婄祫锛夛紝涔熷彲涓嶅付锛堜緥濡備締锛夛紱
                   涓︿笖鏀寔-鍏ㄥ尮閰嶏紙渚嬪瀹?绛夛紝鏈冭嚜鍕曞尮閰嶅畷涓€銆佸畷涓夛級锛涘緦绔渻閫茶绨＄箒杞夋彌锛屽彲杓稿叆绨￠珨
                   s2p妯″紡闇€瑕佺殑杓稿叆锛岃嫢鐣欑┖锛屽墖闊绘瘝鏌ユ墍鏈夋敐锛岃伈姣嶆煡涓夊崄鍏瘝锛岃伈瑾挎煡娓呮縼+瑾?    - group_inputs: 鍒嗙祫鐗瑰镜锛岃几鍏ヤ腑鍙ょ殑椤炲悕锛堜緥濡傛敐锛屽墖鎸夐熁鏀濇暣鐞嗘煇鍊嬮煶浣嶏級
                  鍙几鍏ョ啊楂旓紝鏀寔绨￠珨杞夌箒楂?                   p2s妯″紡闇€瑕佺殑杓稿叆锛岃嫢涓嶅～锛屽墖闊绘瘝鎸夋敐鍒嗛锛岃伈姣嶆寜鑱插垎椤烇紝鑱茶鎸夋竻婵?瑾垮垎椤炪€?    - pho_values: 瑕佹煡瑭㈢殑鍏烽珨闊冲€硷紝p2s妯″紡涓嬬殑杓稿叆锛岃嫢鐣欑┖锛屽墖鏌ユ墍鏈夐煶鍊?    :param user: 寰岀鏍￠寰楀埌鐨勭敤鎴惰韩浠?    :return: - 鑻ョ偤s2p,杩斿洖涓€鍊嬪付鏈夊湴榛炪€佺壒寰碉紙鑱查熁瑾匡級銆佸垎椤炲€硷紙涓彜鍦颁綅锛夈€佸€硷紙鍏烽珨闊冲€硷級銆佸皪鎳夊瓧锛堟墍鏈夋煡鍒扮殑瀛楋級銆?            瀛楁暩銆佷綌姣旓紙鍦ㄦ墍鏈夋煡寰楃殑鍊间腑浣旀瘮锛夈€佸闊冲瓧 鐨勬暩绲勩€俻2s涔熸槸椤炰技
    """
    # 闄愭祦鍜屾棩蹇楄褰曞凡鐢变腑闂翠欢鍜屼緷璧栨敞鍏ヨ嚜鍔ㄥ鐞?
    # start = time.time()
    try:
        # 鏁版嵁搴撹矾寰勫凡閫氳繃渚濊禆娉ㄥ叆鑷姩閫夋嫨
        result = await asyncio.to_thread(run_phonology_analysis, **payload.dict(), dialects_db=dialects_db, query_db=query_db)
        if not result:
            raise HTTPException(status_code=400, detail="[X] 杓稿叆鐨勪腑鍙ゅ湴浣嶄笉瀛樺湪")
        if isinstance(result, pd.DataFrame):
            return {"success": True, "results": result.to_dict(orient="records")}
        if isinstance(result, list) and all(isinstance(df, pd.DataFrame) for df in result):
            merged = pd.concat(result, ignore_index=True)
            return {"success": True, "results": merged.to_dict(orient="records")}
        raise HTTPException(status_code=500, detail="未识别的分析结果格式")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        print("api_run_phonology_analysis")
        # duration = time.time() - start
        # path = request.url.path
        # ip = request.client.host
        # agent = request.headers.get("user-agent", "")
        # referer = request.headers.get("referer", "")
        # user_id = user.id if user else None

        # 鍘熸湁瀵叆 JSON 鏃ヨ獙
        # log_detailed_api(path, duration, status, ip, agent, referer)

        # 鏂板瀵叆璩囨枡搴?        # log_detailed_api_to_db(db, path, duration, status, ip, agent, referer, user_id, CLEAR_2HOUR)


def run_phonology_analysis(
        mode: str,
        locations: list,
        regions: list,
        features: list,
        status_inputs: list = None,
        group_inputs: list = None,
        pho_values: list = None,
        dialects_db=DIALECTS_DB_USER,
        region_mode='yindian',
        query_db=QUERY_DB_USER
):
    """
    绲变竴浠嬮潰鍑芥暩锛氭牴鎿?mode ('s2p' 鎴?'p2s') 鍩疯 sta2pho 鎴?pho2sta銆?
    鍙冩暩锛?        mode: 's2p' = 瑾為煶姊濅欢 鉃?绲辫▓锛?p2s' = 鐗瑰镜鍊?鉃?绲辫▓
        locations: 鏂硅█榛炲悕绋?        features: 瑾為煶鐗瑰镜娆勪綅
        status_inputs: 瑾為煶姊濅欢瀛椾覆锛堝 '鐭ョ祫涓?锛夛紝鍍呴檺 's2p'
        group_inputs: 瑕佸垎绲勭殑娆勪綅锛堝 '绲勮伈'锛夛紝鍍呴檺 'p2s'
        pho_values: 闊冲€兼浠讹紙濡?['l', 'm', 'an']锛夛紝鍍呴檺 'p2s'

    鍥炲偝锛?        List[pd.DataFrame]
    """

    if mode == 's2p':
        # if not status_inputs:
        #     raise ValueError("馃敶 mode='s2p' 鏅傦紝璜嬫彁渚?status_inputs銆?)
        return sta2pho(locations, regions, features, status_inputs, db_path_dialect=dialects_db,
                       region_mode=region_mode, db_path_query=query_db)

    elif mode == 'p2s':
        # if not group_inputs :
        #     raise ValueError("馃敶 mode='p2s' 鏅傦紝璜嬫彁渚?group_inputs ")
        return pho2sta(locations, regions, features, group_inputs, pho_values,
                       dialect_db_path=dialects_db, region_mode=region_mode, query_db_path=query_db)


    else:
        raise ValueError("馃敶 mode 蹇呴爤鐐?'s2p' 鎴?'p2s'")



@router.get("/feature_counts")
async def feature_counts(
    locations: List[str] = Query(...),
    dialects_db: str = Depends(get_dialects_db)
):
    try:
        # 鏁版嵁搴撹矾寰勫凡閫氳繃渚濊禆娉ㄥ叆鑷姩閫夋嫨
        result = get_feature_counts(locations, dialects_db)
        # 濡傛灉缁撴灉涓虹┖锛屽彲浠ユ姏鍑?HTTP 404 閿欒
        if not result:
            raise HTTPException(status_code=404, detail="No data found for the given locations.")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.post("/feature_stats")
async def feature_stats(
    payload: FeatureStatsRequest,
    dialects_db: str = Depends(get_dialects_db)
):
    """
    鐛插彇鎸囧畾鍦伴粸鐨勯煶闊荤壒寰电当瑷堟暩鎿氾紙绱㈠紩鍎寲鏍煎紡锛?
    鏀寔鍔熻兘锛?    1. 婕㈠瓧绡╅伕锛坈hars 鍙冩暩锛?    2. 鐗瑰镜鍊肩閬革紙filters 鍙冩暩锛?    3. 瑷堢畻姣忓€嬬壒寰靛€肩殑鏁搁噺鍜屽崰姣?    4. 杩斿洖绱㈠紩鍎寲鏍煎紡锛堟笡灏戞暩鎿氶噸瑜囷級
    5. Redis 绶╁瓨锛?灏忔檪 TTL锛?
    Request Body:
    {
        "locations": ["寤ｅ窞", "鏉辫帪"],           // 蹇呴渶
        "chars": ["鏉?, "瑗?],                   // 鍙伕
        "features": ["鑱叉瘝", "闊绘瘝", "鑱茶"],    // 鍙伕锛岄粯瑾嶅叏閮?        "filters": {                             // 鍙伕
            "鑱叉瘝": ["p", "b"],
            "闊绘瘝": ["a", "蓯"]
        }
    }

    Response:
    {
        "chars_map": ["鍏?, "鎶?, "鐧?, ...],   // 鍏ㄥ眬瀛楃瀛楀吀
        "data": {
            "寤ｅ窞": {
                "total_chars": 3000,
                "鑱叉瘝": {
                    "p": {
                        "count": 150,
                        "ratio": 0.05,
                        "char_indices": [0, 1, 2, ...]
                    },
                    ...
                }
            }
        },
        "meta": {
            "query_chars_count": 2,
            "locations_count": 2,
            "has_filters": false
        }
    }
    """
    # 闄愭祦鍜屾棩蹇楄褰曞凡鐢变腑闂翠欢鍜屼緷璧栨敞鍏ヨ嚜鍔ㄥ鐞?
    try:
        # 鏁版嵁搴撹矾寰勫凡閫氳繃渚濊禆娉ㄥ叆鑷姩閫夋嫨
        # 鏍规嵁鏁版嵁搴撹矾寰勫垽鏂被鍨嬶紙鐢ㄤ簬缂撳瓨閿級
        db_type = "admin" if dialects_db == DIALECTS_DB_ADMIN else "user"

        # 鐢熸垚绶╁瓨閸?        cache_key = generate_cache_key(
        cache_key = generate_cache_key(
            db_type=db_type,
            locations=payload.locations,
            chars=payload.chars,
            features=payload.features,
            filters=payload.filters
        )

        # 鍢楄│寰?Redis 鐛插彇绶╁瓨
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            print(f"[CACHE HIT] {cache_key}")
            return json.loads(cached_data)

        print(f"[CACHE MISS] {cache_key} - querying db")

        # 寰炴暩鎿氬韩鏌ヨ
        result = await asyncio.to_thread(
            get_feature_statistics,
            locations=payload.locations,
            chars=payload.chars,
            features=payload.features,
            filters=payload.filters,
            db_path=dialects_db
        )

        if not result or not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="No data found for the specified locations"
            )

        # 瀛樺叆 Redis 绶╁瓨锛?灏忔檪閬庢湡锛?        await redis_client.setex(
        await redis_client.setex(
            cache_key,
            3600,  # 1灏忔檪
            json.dumps(result, ensure_ascii=False)
        )
        print(f"[CACHE SET] {cache_key}")

        return result

    except HTTPException:
        raise
    except ValueError as e:
        # 鎹曡幏楠岃瘉閿欒锛堟潵鑷?get_feature_statistics锛?        print(f"[VALIDATION ERROR] {str(e)}")
        print(f"[VALIDATION ERROR] {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )



