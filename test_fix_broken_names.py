from unittest.mock import MagicMock
from fix_broken_names import fetch_name_from_fnguide


def test_shouldReturnNameWhenFnguideSnapshotPageResponds():
    # API 레벨: FnGuide 신버전 Snapshot 페이지의 #giName 에서 종목명을 가져온다
    session = MagicMock()

    def fake_get(url, params=None, timeout=None):
        if url == "https://wcomp.fnguide.com/CompanyInfo/Snapshot" and params == {"cmp_cd": "000660"}:
            return MagicMock(text='<h1 id="giName">SK하이닉스</h1>')
        return MagicMock(text="<td>페이지가 없습니다.</td>")

    session.get.side_effect = fake_get

    assert fetch_name_from_fnguide("000660", session) == "SK하이닉스"
