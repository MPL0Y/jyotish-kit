from jyotish_kit import Jyotish, BirthData
from jyotish_kit.models import SIGNS


def test_jyotish_create():
    j = Jyotish.create(
        dt_local="2001-10-11T05:57:30",
        lat=29.681312,
        lon=77.010063,
        tz_name="Asia/Kolkata",
        place_name="Karnal, Haryana, India",
    )
    assert j.chart is not None
    assert j.chart.bodies["Sun"].deg > 0
    assert SIGNS[j.chart.bodies["Lagna"].sign] == "Virgo"


def test_jyotish_planets():
    j = Jyotish.create(
        dt_local="2001-10-11T05:57:30",
        lat=29.681312,
        lon=77.010063,
        tz_name="Asia/Kolkata",
    )
    planets = j.get_planets()
    assert "Sun" in planets
    assert "Moon" in planets
    assert planets["Moon"]["sign"] == "Cancer"
    assert planets["Moon"]["house"] == 11
    assert planets["Mercury"]["sign"] == "Libra"
    assert planets["Mercury"]["house"] == 2


def test_jyotish_vargas():
    j = Jyotish.create(
        dt_local="2001-10-11T05:57:30",
        lat=29.681312,
        lon=77.010063,
        tz_name="Asia/Kolkata",
    )
    vargas = j.get_vargas(["D1", "D9", "D10"])
    assert "D1" in vargas
    assert "D9" in vargas
    assert "D10" in vargas
    assert vargas["D9"]["Mars"] == "Scorpio"
    assert vargas["D10"]["Mars"] == "Leo"


def test_jyotish_dashas():
    j = Jyotish.create(
        dt_local="2001-10-11T05:57:30",
        lat=29.681312,
        lon=77.010063,
        tz_name="Asia/Kolkata",
    )
    dashas = j.get_dashas("vimshottari", depth=2)
    assert len(dashas) > 0
    assert dashas[0]["system"] == "vimshottari"
    assert dashas[0]["level"] == 1


def test_jyotish_llm_context():
    j = Jyotish.create(
        dt_local="2001-10-11T05:57:30",
        lat=29.681312,
        lon=77.010063,
        tz_name="Asia/Kolkata",
    )
    ctx = j.to_llm_context(["career"])
    assert "planets" in ctx
    assert "ashtakavarga" in ctx
    assert "judgments" in ctx
    assert "career" in ctx["judgments"]
