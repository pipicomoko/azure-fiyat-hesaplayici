from starlette.datastructures import FormData

from app.form_yardimcilari import (
    bos_degerleri_temizle,
    boolean_alanlarini_normallestir,
    coklu_kalem_formunu_ayir,
)


def test_coklu_kalem_formunu_ayir_kalemleri_ve_genel_alanlari_ayirir():
    form = FormData(
        [
            ("para_birimi", "USD"),
            ("abc123.urun_tipi", "managed_disks"),
            ("abc123.bolge", "eastus"),
            ("abc123.disk.kademe", "standardhdd"),
            ("def456.urun_tipi", "virtual_machines"),
            ("def456.bolge", "westeurope"),
        ]
    )

    genel, kalemler = coklu_kalem_formunu_ayir(form)

    assert genel == {"para_birimi": "USD"}
    assert kalemler["abc123"] == {
        "urun_tipi": "managed_disks", "bolge": "eastus", "disk": {"kademe": "standardhdd"}
    }
    assert kalemler["def456"] == {"urun_tipi": "virtual_machines", "bolge": "westeurope"}


def test_coklu_kalem_formunu_ayir_checkbox_hidden_ikilisinde_son_deger_kazanir():
    # Checkbox isaretli degil: sadece gizli "false" gelir
    form_isaretsiz = FormData([("k1.anlik_goruntu", "false")])
    _, kalemler = coklu_kalem_formunu_ayir(form_isaretsiz)
    assert kalemler["k1"]["anlik_goruntu"] == "false"

    # Checkbox isaretli: gizli "false" + checkbox "true" DOM sirasiyla gelir, son deger kazanir
    form_isaretli = FormData([("k1.anlik_goruntu", "false"), ("k1.anlik_goruntu", "true")])
    _, kalemler = coklu_kalem_formunu_ayir(form_isaretli)
    assert kalemler["k1"]["anlik_goruntu"] == "true"


def test_bos_degerleri_temizle_ic_ice_calisir():
    veri = {"adet": "", "bolge": "eastus", "disk": {"sku": "", "kademe": "standardhdd"}}
    bos_degerleri_temizle(veri)
    assert veri == {"bolge": "eastus", "disk": {"kademe": "standardhdd"}}


def test_boolean_alanlarini_normallestir_string_false_gercek_false_olur():
    veri = {"anlik_goruntu": "false", "gizli_sifreleme": "true", "disk": {"patlama_etkin": "false"}}
    boolean_alanlarini_normallestir(veri)
    assert veri["anlik_goruntu"] is False
    assert veri["gizli_sifreleme"] is True
    assert veri["disk"]["patlama_etkin"] is False
