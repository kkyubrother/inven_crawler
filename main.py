from inven_crawler_v2 import InvenCrawler

targets = [{
    "board_type": "maple",
    "board_id": 2300,
    "filename": "inven.maple.질문과_답변.json",
    "max_idx": True,
    # "min_idx": 0,
}, ]

for t in targets:
    print("crawling: ", t["board_type"], t["board_id"], t["filename"])
    
    # sampling=False >>> 샘플링
    InvenCrawler(t["board_type"], t["board_id"], t["filename"])\
        .crawling(sampling=False, max_idx=t.get("max_idx"), min_idx=t.get("min_idx"))
