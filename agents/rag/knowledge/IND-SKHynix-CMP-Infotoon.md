# IND-SKHynix-CMP-Infotoon - SK하이닉스 CMP 공정 인포툰

## CMP 공정의 의미

CMP(Chemical Mechanical Polishing)는 반도체 제조 과정에서 웨이퍼 표면을 평탄화하는 필수 공정입니다. 화학적·기계적 요소를 통해 박막 표면의 요철·굴곡을 제거합니다.

## 공정 필요성

반도체 미세화·다층화로 인해 한 웨이퍼 위에 수십~수백 층의 박막을 쌓아 올리며, 각 층마다 다음 공정(특히 포토)의 정밀도 확보를 위해 평탄화가 필요합니다.

평탄화가 부족하면:
- 노광 시 초점심도(DoF) 부족 → CD 산포 증가
- 후속 식각·증착에서 uniformity 저하
- 다층 적층 시 누적 오차 증가

## 핵심 운영 포인트

- **MRR (Material Removal Rate)**: 단위 시간 재료 제거량 - 너무 빠르면 over-polish, 너무 느리면 throughput 손실
- **uniformity**: 웨이퍼 전체 평탄도 - 슬러리 분포·패드 wear·압력 분포가 결정
- **defect**: scratch, embedded particle - 슬러리 입자·패드 거칠기 원인
- **pad lifetime**: dressing 횟수에 비례해 마모, 주기적 교체 필요

## 출처
- [SK하이닉스 뉴스룸: 반도체 WHAT 인포툰 CMP 공정](https://news.skhynix.co.kr/post/infotoon-cmp)
- 본 문서는 SK하이닉스 뉴스룸 자료를 발췌·요약한 것으로, 시연용 RAG 학습 자료입니다
