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


def get_alias(path, alias):
    if 'common_guide' in path:
        return
    for item in os.listdir(path):
        if 'json' in item:
            continue
        name = item.replace('.jpg', '').replace('.png', '')
        if name not in alias['角色'] and 'role' in path:
            alias['角色'][name] = []
        if name not in alias['武器'] and 'weapon' in path:
            alias['武器'][name] = [name]


genshin = os.listdir('genshin')
path_ = Path(f'genshin/alias.json')
alias = json.load(path_.open('r', encoding='utf-8'))
for item in genshin:
    if os.path.isdir('genshin/' + item):
        get_alias('genshin/' + item, alias)
        get_hash('genshin/' + item)
json.dump(alias, path_.open('w', encoding='utf-8'), ensure_ascii=False, indent=2)

starrail = os.listdir('starrail')
# path_ = Path(f'starrail/alias.json')
# alias = json.load(path_.open('r', encoding='utf-8'))
for item in starrail:
    if os.path.isdir('starrail/' + item):
        # get_alias('starrail/' + item, alias)
        get_hash('starrail/' + item)
# json.dump(alias, path_.open('w', encoding='utf-8'), ensure_ascii=False, indent=2)
