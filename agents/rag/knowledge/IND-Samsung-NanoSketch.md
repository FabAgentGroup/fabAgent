# IND-Samsung-NanoSketch - 나노 스케일 회로 형성과 EUV

## 포토공정의 기본 원리

포토공정(노광공정)은 반도체 제조의 핵심 기술입니다. 이 공정은 조각이나 재단을 위해 미리 밑그림을 그려 놓는 것과 같은 방식으로 작동합니다. 마스크를 통해 빛을 선택적으로 투과시켜 감광액(PR, Photo Resist)에 회로 패턴을 현상합니다.

## 포토공정이 직면한 과제

포토공정의 주요 장애물은 **빛의 회절과 간섭 현상**입니다. 파장이 길어지거나 틈의 폭이 좁아질수록 회절 현상이 더 크게 일어나 파장이 더 넓게 퍼지게 되어, 미세한 패턴을 정확하게 그리기 어려워집니다.

## 기술적 해결 방안

산업은 두 가지 주요 접근법을 활용합니다:

### 1. 다중 패터닝(Multi Patterning Technology)
한 번에 그리기 어려운 좁은 간격의 패턴을 여러 번에 나누어 공정합니다.

### 2. OPC(광학근접보정, Optical Proximity Correction)
오차를 고려하여 마스크 형상을 미리 조정하는 기술입니다.

## 근본적 해결책

궁극적으로는 파장을 줄이는 방법이 빛의 성질로 인한 문제의 근본적 해결책이며, 이것이 EUV 기술 발전으로 이어집니다.

- **193nm (DUV/ArF)**: 기존 immersion 노광으로 10nm급까지 multi-patterning으로 구현
- **13.5nm (EUV)**: 단일 노광으로 7nm 이하 가능, 5nm/3nm 노드의 표준

## 출처
- [삼성반도체 테크블로그: nm 회로 part 1](https://semiconductor.samsung.com/kr/news-events/tech-blog/a-nano-scale-sketch-on-a-millimeter-scale-wafer-part-1/)
- 본 문서는 삼성반도체 공식 자료를 발췌·요약한 것으로, 시연용 RAG 학습 자료입니다
