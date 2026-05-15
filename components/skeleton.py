"""로딩 스켈레톤 (개발 가이드 12장)

tier_num별 스켈레톤 레이아웃을 HTML 문자열로 반환
tiers.py가 tier-body 안에 그대로 삽입
"""


def skeleton_html(tier_num: int) -> str:
    if tier_num in (1, 3):
        return """
            <div class="t1-grid">
              <div class="skel skel-block" style="height: 148px;"></div>
              <div class="skel-row">
                <div class="skel" style="height: 18px; width: 40%;"></div>
                <div class="skel" style="height: 24px;"></div>
                <div class="skel" style="height: 24px; width: 85%;"></div>
                <div class="skel" style="height: 24px; width: 60%;"></div>
              </div>
            </div>
        """
    rows = 3 if tier_num == 2 else 4
    h = 88 if tier_num == 2 else 48
    blocks = "".join(
        f'<div class="skel" style="height: {h}px; border-radius: 8px; opacity: {1 - i*0.18:.2f};"></div>'
        for i in range(rows)
    )
    return f'<div class="skel-row">{blocks}</div>'
