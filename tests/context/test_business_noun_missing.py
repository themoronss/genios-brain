import json
import pytest
from sqlalchemy import text

from tests.test_business_noun_contract import FIELDS
from .test_business_noun_authority import business_store, business_fact, commit
from .test_business_fact_store import fact_store


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", [None, "", " UNKNOWN "])
@pytest.mark.parametrize("typed", [True, False])
def test_unknown_business_values_never_satisfy_a_missing_field(business_store,field,value,typed):
    fact = business_fact(field,"Jane",value)
    fact["business_fact"] = typed
    commit(business_store,[fact])
    with business_store.engine.connect() as c:
        assert c.execute(text("select count(*) from graph_facts where field=:f and status='active'"),dict(f=field)).scalar_one() == 0


def test_an_unknown_extraction_does_not_erase_a_legitimate_held_business_fact(business_store):
    commit(business_store,[business_fact("party.role","Jane","investor")])
    commit(business_store,[business_fact("party.role","Jane","unknown")])
    with business_store.engine.connect() as c:
        row = c.execute(text("select value from graph_facts where field='party.role' and status='active'")).one()
        assert json.loads(row.value) == "investor"
