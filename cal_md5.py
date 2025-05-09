import hashlib
import json
from pathlib import Path
from typing import Dict, Any


def compute_file_hash(directory: Path) -> None:
    """计算目录下所有图片文件的 MD5 哈希，并保存到 md5.json"""
    hash_map = {}
    # 遍历目录下所有文件，排除 md5.json 自身
    for file_path in sorted(directory.glob("*")):
        if file_path.is_file() and file_path.name != "md5.json":
            # 使用文件 stem (无后缀) 作为键名
            with file_path.open("rb") as f:
                hash_map[file_path.stem] = hashlib.md5(f.read()).hexdigest()
    
    # 写入哈希数据
    hash_file = directory / "md5.json"
    hash_file.write_text(json.dumps(hash_map, ensure_ascii=False, indent=4), encoding="utf-8")


def update_alias_data(directory: Path, alias_data: Dict[str, Any]) -> None:
    """更新角色/武器别名数据"""
    if "common_guide" in directory.parts:
        return
    
    # 通过父目录名称确定类型
    category = directory.name
    if category == "role":
        target = "角色"
    elif category == "weapon":
        target = "武器"
    else:
        return  # 跳过其他类型目录

    # 遍历目录下所有非JSON文件
    for file_path in sorted(directory.glob("*")):
        if file_path.is_file() and file_path.suffix not in (".json",):
            name = file_path.stem
            if name not in alias_data[target]:
                alias_data[target][name] = [] if target == "角色" else [name]


def process_game_data(game_root: str, update_alias: bool = True) -> None:
    """处理游戏数据"""
    root_path = Path(game_root)
    alias_path = root_path / "alias.json"
    
    # 初始化别名数据 (仅genshin需要)
    alias = {"角色": {}, "武器": {}}
    if update_alias and alias_path.exists():
        alias = json.loads(alias_path.read_text(encoding="utf-8"))
    
    # 遍历游戏目录
    for sub_dir in root_path.iterdir():
        if sub_dir.is_dir():
            if update_alias:
                update_alias_data(sub_dir, alias)
            compute_file_hash(sub_dir)
    
    # 保存别名数据 (仅genshin需要)
    if update_alias:
        alias_path.write_text(
            json.dumps(alias, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


if __name__ == "__main__":
    # 处理原神数据 (需要更新别名)
    process_game_data("genshin", update_alias=True)
    # 处理星穹数据 (仅生成哈希)
    process_game_data("starrail", update_alias=False)