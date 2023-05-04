import hashlib
import json
import os
from pathlib import Path


def get_hash(path):
    hash_list = {}
    data = os.listdir(path)
    for item in data:
        if item != 'md5.json':
            with open(f'{path}/{item}', 'rb') as img:
                hash_list[item.replace('.jpg', '').replace('.png', '')] = hashlib.md5(img.read()).hexdigest()
    path_ = Path(f'{path}/md5.json')
    json.dump(hash_list, path_.open('w', encoding='utf-8'), ensure_ascii=False, indent=4)


genshin = os.listdir('genshin')
for item in genshin:
    if os.path.isdir('genshin/' + item):
        get_hash('genshin/' + item)
starrail = os.listdir('starrail')
for item in starrail:
    if os.path.isdir('starrail/' + item):
        get_hash('starrail/' + item)
