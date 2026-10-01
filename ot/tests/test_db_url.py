from app.db import _url_con_pooler

DIRECTO = "postgresql+psycopg://u:p@ep-cool-name-123456.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"


def test_neon_directo_pasa_al_host_pooled():
    assert "@ep-cool-name-123456-pooler.c-5.us-east-2.aws.neon.tech/" in _url_con_pooler(DIRECTO)


def test_neon_ya_pooled_no_se_toca():
    pooled = DIRECTO.replace("123456.", "123456-pooler.")
    assert _url_con_pooler(pooled) == pooled


def test_hosts_que_no_son_neon_no_se_tocan():
    for url in ("postgresql://u:p@localhost/db", "sqlite:///:memory:"):
        assert _url_con_pooler(url) == url
