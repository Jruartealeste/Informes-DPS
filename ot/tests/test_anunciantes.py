from app.anunciantes import corresponde


def test_cliente_corresponde_a_sus_anunciantes_de_advertys():
    assert corresponde("ALUAR", "ALUAR ALUMINIO ARGENTINO SOCIEDAD ANONIM")
    assert corresponde("FATE", "FATE - MARKETING")
    assert corresponde("FATE", "FATE S.A.I.C.I.")
    assert corresponde("Nordelta", "NORDELTA S.A.")
    assert corresponde("INFA", "Infa S.A.")
    # FAA = Fundación Aurora Austral (por siglas), con o sin tilde
    assert corresponde("FAA", "FUNDACIÓN AURORA AUSTRAL")
    assert corresponde("Fundación Aurora Austral", "FUNDACION AURORA AUSTRAL")


def test_cliente_no_corresponde_a_anunciantes_ajenos():
    assert not corresponde("Nordelta", "Asociación Vecinal Nordelta S.A. - AVN")
    assert not corresponde("ALUAR", "FATE - MARKETING")
    assert not corresponde("FAA", "FARMACIA GRAMA SOCIEDAD EN COMANDITA SIM")
    assert not corresponde("INCAA", "INFA S.A.")
