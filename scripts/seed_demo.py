import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db import SessionLocal
from app.models import Location, Part


def get_or_create(session, model, defaults=None, **kwargs):
    inst = session.query(model).filter_by(**kwargs).first()
    if inst:
        return inst, False
    params = dict(kwargs)
    if defaults:
        params.update(defaults)
    inst = model(**params)
    session.add(inst)
    session.commit()
    session.refresh(inst)
    return inst, True


def main():
    with SessionLocal() as s:
        # Ubicaciones
        get_or_create(
            s, Location, code="WH-A01", defaults={"name": "Almacén A - Estante 01"}
        )
        get_or_create(
            s, Location, code="LINE-01", defaults={"name": "Línea de producción 01"}
        )

        # Parte simple
        get_or_create(
            s,
            Part,
            ipn="100001-00",
            defaults=dict(
                description="Resistor 10k 1% 0603",
                manufacturer="Yageo",
                manufacturer_pn="RC0603FR-0710KL",
                is_compound=False,
                uom="pcs",
                part_type_id=None,
            ),
        )


if __name__ == "__main__":
    main()
