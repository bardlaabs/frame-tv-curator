"""Shuffle-bag random picker with exclude / favorite / show-more weights."""
import random
from . import library

def eligible(ids):
    out = []
    for i in ids:
        sc = library.load_sidecar(i)
        fl = sc.get("flags") or {}
        if fl.get("exclude"):
            continue
        w = 1 + (2 if fl.get("favorite") else 0) + (1 if fl.get("show_more") else 0)
        out += [i] * w
    return out

def source_ids(src):
    if src.get("mode") == "images":
        import os
        return [i for i in (src.get("images") or []) if os.path.exists(library.abspath(i))]
    if src.get("mode") == "album":
        from . import albums
        return albums.images(src.get("album") or "")
    if src.get("mode") == "mix":
        ids = []
        for f in (src.get("mix") or {}):
            ids += library.images(f)
        return ids
    return library.images(src.get("folder", "Art"))

def source_key(src):
    if src.get("mode") == "images":
        return "images:" + str(src.get("rule"))
    if src.get("mode") == "album":
        return "album:" + str(src.get("album"))
    if src.get("mode") == "mix":
        return "mix:" + ",".join(sorted((src.get("mix") or {}).keys()))
    return "folder:" + src.get("folder", "Art")

def next_id(src, state_data, avoid=None):
    """Returns (image_id, bags_dict). Mix mode picks a folder by weight, then draws from that folder's bag."""
    bags = state_data.setdefault("bags", {})
    if src.get("mode") == "mix":
        mix = {f: w for f, w in (src.get("mix") or {}).items() if w > 0}
        if not mix:
            return None
        f = random.choices(list(mix), weights=list(mix.values()))[0]
        src = {"mode": "folder", "folder": f}
    key = source_key(src)
    bag = bags.get(key) or []
    # drop ids that no longer exist / are now excluded
    valid = set(eligible(source_ids(src)))
    bag = [i for i in bag if i in valid]
    if not bag:
        bag = eligible(source_ids(src))
        random.shuffle(bag)
        if not bag:
            return None
        # avoid an immediate repeat across the refill boundary
        if avoid and bag[-1] == avoid and len(set(bag)) > 1:
            bag.insert(0, bag.pop())
    pick = bag.pop()
    # remove remaining duplicates of weighted pick only after it's drawn: weighting means repeats are allowed in a cycle
    bags[key] = bag
    return pick
