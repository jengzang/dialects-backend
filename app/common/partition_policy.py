"""Default partition visibility and ordering; preferences never restrict new roots."""

EXCLUDED_ROOTS = frozenset({"待处理", "歷史音", "戲劇", "域外方音", "現代標準漢語"})

ROOT_ORDER = {
    "yindian": (
        "華北", "西北", "藍青", "中上江", "下江", "兩浙", "浙南", "湘贛", "嶺東", "廣中",
        "嶺南", "嶺西", "閩", "湘南", "道州", "鄕話", "白語", "蔡家話", "民語漢字音",
    ),
    "map": (
        "東北官話", "北京官話", "冀魯官話", "蘭銀官話", "膠遼官話", "中原官話", "江淮官話",
        "西南官話", "晉語", "贛語", "客家話", "吳語", "徽語", "粵語", "閩語", "湘語",
        "平話和土話", "鄕話", "民族語",
    ),
}

PARTITION_COLUMNS = {"yindian": "音典分區", "map": "地圖集二分區"}


def valid_partition_path(path):
    return isinstance(path, str) and all(part and part == part.strip() for part in path.split("-"))
