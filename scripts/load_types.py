import os
import sys
from pathlib import Path
from typing import Any, Optional, Tuple

import yaml
from sqlalchemy.orm import Session

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db import SessionLocal
from app.models import PartType


def parse_code_label(text: str) -> Tuple[str, str]:
    """
    Input: 'ANLG[Analog]' -> ('ANLG', 'Analog')
           'MISC[Miscellaneous]' -> ('MISC', 'Miscellaneous')
           'RES[Resistors]:' (if it has ':' at the end) -> identically
           'ANLG' (without label) -> ('ANLG', 'ANLG')
    """
    s = (text or "").strip().rstrip(":")
    if "[" in s and s.endswith("]"):
        code = s[: s.index("[")].strip()
        label = s[s.index("[") + 1 : -1].strip()
        code = code or label
        label = label or code
        return code, label
    return s, s


def find_or_create(
    session: Session, *, code: str, label: str, parent_id: Optional[int]
):
    inst = (
        session.query(PartType)
        .filter(
            PartType.code == code,
            (
                PartType.parent_id.is_(parent_id)
                if parent_id is None
                else PartType.parent_id == parent_id
            ),
        )
        .first()
    )
    if inst:
        # If tag changes, update it (useful if we refine names)
        if inst.label != label:
            inst.label = label
            session.flush()
        return inst
    inst = PartType(code=code, label=label, parent_id=parent_id)
    session.add(inst)
    session.flush()
    return inst


def insert_recursive(session: Session, node: Any, parent_id: Optional[int] = None):
    """
    It supports:
      - dict: { "SEMI[Semiconductors]": {...}, "PASS[Passive]": {...} }
      - dict with key 'ANLG[Analog]': list[str|dict]  -> create parent and leaves
      - list[str] with 'OPA[Operational Amplifier]'     -> create leaves
    """
    if isinstance(node, dict):
        for raw_key, raw_val in node.items():
            code, label = parse_code_label(str(raw_key))
            parent = find_or_create(
                session, code=code, label=label, parent_id=parent_id
            )

            if isinstance(raw_val, dict):
                # Subtree
                insert_recursive(session, raw_val, parent.id)

            elif isinstance(raw_val, list):
                # List of leaves or subtrees
                for item in raw_val:
                    if isinstance(item, str):
                        c, l = parse_code_label(item)
                        # Avoid duplicating a child identical to the parent (e.g. MISC -> [MISC])
                        if not (c == code):
                            find_or_create(
                                session, code=c, label=l, parent_id=parent.id
                            )
                    elif isinstance(item, dict):
                        # Elements of list with subtree ({ "SUB[Label]": [...] })
                        for k2, v2 in item.items():
                            c, l = parse_code_label(str(k2))
                            child = find_or_create(
                                session, code=c, label=l, parent_id=parent.id
                            )
                            insert_recursive(session, v2, child.id)
                    else:
                        # Ignore unexpected types
                        continue

            elif raw_val is None:
                # Leaf node without explicit children -> already created as 'parent'
                pass

            else:
                # If it comes as a string value, treat it as an alternative label
                # We do not create additional children in this case.
                pass

    elif isinstance(node, list):
        # List at root (we do not expect it, but we support it)
        for item in node:
            if isinstance(item, str):
                c, l = parse_code_label(item)
                find_or_create(session, code=c, label=l, parent_id=parent_id)
            elif isinstance(item, dict):
                insert_recursive(session, item, parent_id)
    else:
        # Nothing to do
        return


def main(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    with SessionLocal() as session:
        insert_recursive(session, data, None)
        session.commit()


if __name__ == "__main__":
    yaml_path = os.environ.get("TYPES_YAML", "app/config/types.yaml")
    main(yaml_path)
