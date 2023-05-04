import hashlib
import json
import os
from pathlib import Path


def get_hash(path):
    hash_list = {}
    data = os.listdir(path)
    for item in data:
        if item != 'md5':
            with open(f'{path}/{item}', 'rb') as img:
                hash_list[item.replace('.jpg', '').replace('.png', '')] = hashlib.md5(img.read()).hexdigest()
    path_ = Path(f'{path}/md5')
    json.dump(hash_list, path_.open('w', encoding='utf-8'), ensure_ascii=False, indent=4)


get_hash('genshin/common_guide')
get_hash('genshin/role_info')
get_hash('genshin/role_break')
get_hash('genshin/role_guide')
get_hash('genshin/weapon_info')
#get_hash('starrail/common_guide')
#get_hash('starrail/role_info')
#get_hash('starrail/role_break')
get_hash('starrail/role_guide')
get_hash('starrail/weapon_info')
