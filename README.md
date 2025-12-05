# 🎯 Picky - 개인 맞춤형 뉴스 & 지식 추천 서비스

<div align="center">

<img src="./picky_logo.png" width="100" />

**사용자의 브라우징 패턴을 실시간으로 분석하여 관심사에 맞는 뉴스와 지식을 똑똑하게 추천하는 AI 기반 개인화 플랫폼**

[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.5.5-brightgreen)](https://spring.io/projects/spring-boot)
[![React](https://img.shields.io/badge/React-19.1.1-blue)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688)](https://fastapi.tiangolo.com/)

</div>

## 🚀 프로젝트 개요

**Picky**는 사용자의 웹 브라우징 로그를 실시간으로 수집하고 분석하여 개인의 관심사와 선호도를 파악한 후, 이에 맞는 뉴스 기사와 지식 퀴즈를 맞춤형으로 제공하는 AI 기반 추천 시스템입니다.

### ✨ 핵심 가치
- **🎯 개인화**: Chrome Extension을 통한 자연스러운 브라우징 패턴 학습
- **🧠 지능형 분석**: GMS API 기반 1536차원 벡터 임베딩 및 유사도 분석
- **⚡ 실시간**: 30초 배치 처리로 즉시 반영되는 동적 추천
- **🔒 프라이버시**: 200+ 민감 도메인 자동 필터링 및 사용자 제어

### 🔍 차별화 포인트
- **콜드 스타트 해결**: 최근 30일 브라우저 히스토리 분석으로 즉시 개인화
- **고품질 콘텐츠 추출**: Offscreen Document + Readability.js (98% 성공률)
- **증분 벡터 업데이트**: 전체 재계산 없이 실시간 프로필 갱신
- **확장 가능 아키텍처**: MongoDB 샤딩 및 Qdrant 벡터 DB로 대용량 처리

## 🎨 주요 기능

### 📊 스마트 브라우징 분석
- **자동 데이터 수집**: 체류시간, 스크롤 깊이, 방문 패턴 등 행동 데이터
- **콘텐츠 정제**: Mozilla Readability 알고리즘으로 본문만 추출
- **가중치 시스템**: 체류시간(최대 +2.0), 스크롤 깊이(+0.5), 직접 타이핑(+0.5)
- **실시간 카테고리 분석**: 17개 카테고리 자동 분류 및 키워드 추출

### 📰 맞춤형 뉴스 추천
- **AI 기반 큐레이션**: 개인 벡터와 뉴스 벡터 코사인 유사도 매칭
- **KoBART 요약**: 동적 길이 조정 (200자 미만: 1/2, 이상: 1/3 요약)
- **중복 방지**: 최근 30일 추천 이력과 비교하여 새로운 콘텐츠만 제공
- **카테고리별 필터링**: 관심 분야 집중 추천 및 차단 도메인 설정

### 🧩 지식 퀴즈 제공
- **관심사 기반 문제**: 개인 벡터와 유사한 주제의 지식 퀴즈
- **벡터화된 퀴즈 DB**: 1000개 단위 배치 처리로 효율적 매칭
- **학습 진도 추적**: 정답률 및 관심 분야별 성과 분석
- **게임화된 경험**: 연속 정답, 스트릭 등 동기부여 요소

### ⚙️ 개인화 설정
- **수집 범위 제어**: 토글 기능으로 실시간 수집 On/Off
- **관심 카테고리 조정**: 17개 카테고리별 가중치 수동 설정
- **프라이버시 보호**: 개인별 차단 도메인 추가 설정
- **알림 및 빈도**: 추천 주기 및 알림 방식 개인화

## 🏗️ 시스템 아키텍처

<div align="center">

![Architecture](./picky_architecture.png)

</div>

### 🔧 기술 스택

| 영역 | 기술 | 용도 |
|------|------|------|
| **Frontend** | React 19, TailwindCSS, Zustand, Vite | 웹 애플리케이션 UI/UX |
| **Extension** | Chrome Extension API, Manifest V3, Radix UI, Offscreen Document | 브라우저 데이터 수집 |
| **Backend** | Spring Boot 3.5, Java 17, Spring Security, OAuth2 | 메인 API 서버, 인증 |
| **ML Engine** | FastAPI, Python, AsyncIO, Transformers | 데이터 처리, 벡터화, 추천 |
| **Database** | MySQL, MongoDB (5-Shard), Redis, Qdrant Vector DB | 다목적 데이터 저장 |
| **AI/ML** | GMS API, KoBART, text-embedding-3-small | 1536차원 임베딩, 텍스트 요약 |
| **DevOps** | Docker, Docker Compose, Gradle, npm | 컨테이너화, 빌드 자동화 |

## 🚀 빠른 시작

### 📋 사전 요구사항
- Java 17+
- Node.js 18+
- Python 3.9+
- Docker & Docker Compose
- MySQL, MongoDB, Redis (또는 Docker로 실행)

### 🛠️ 설치 및 실행
-> /exec 폴더 내 빌드 및 배포 폴더 참고

## 📁 프로젝트 구조

```
picky/
├── 📱 extension/           # Chrome 브라우저 확장 프로그램
│   ├── src/
│   │   ├── background.js        # 메인 오케스트레이션, 세션 관리
│   │   ├── content.jsx          # 페이지별 데이터 수집, UI 주입
│   │   ├── modules/
│   │   │   ├── DataCollector.js # 실시간 브라우징 데이터 수집
│   │   │   ├── DataSender.js    # 30초 배치 전송, 재시도 로직
│   │   │   └── HistoryCollector.js # Chrome History API 수집
│   │   ├── popup/              # React 기반 설정 UI
│   │   └── Overlay.jsx         # 페이지 오버레이 캐릭터
│   └── manifest.json
│
├── 💻 picky-fe/           # React 웹 애플리케이션
│   ├── src/
│   │   ├── components/    # 재사용 가능한 컴포넌트
│   │   ├── pages/         # 페이지 컴포넌트
│   │   ├── stores/        # Zustand 상태 관리
│   │   └── services/      # API 통신
│   └── package.json
│
├── ⚙️ picky-be/           # Spring Boot 백엔드 API
│   ├── src/main/java/com/c102/picky/
│   │   ├── domain/        # 비즈니스 도메인
│   │   │   ├── auth/      # Google OAuth2 인증/인가
│   │   │   ├── users/     # 사용자 관리
│   │   │   ├── news/      # 뉴스 콘텐츠 관리
│   │   │   ├── quiz/      # 퀴즈 콘텐츠 관리
│   │   │   └── recommendation/ # 추천 시스템 중계
│   │   └── global/        # 공통 설정 (Security, CORS, 예외처리)
│   └── build.gradle
│
└── 🤖 data-engine/        # FastAPI ML 추천 엔진
    ├── app/
    │   ├── main.py              # FastAPI 메인 앱
    │   ├── user_logs/           # 브라우징 로그 처리 & 프로필 관리
    │   ├── vectorization/       # GMS API 임베딩 & Qdrant 클라이언트
    │   ├── news/               # 뉴스 크롤링 & KoBART 요약
    │   └── quiz/               # 퀴즈 벡터화 & 추천
    └── requirements.txt
```

## ⚡ 핵심 데이터 플로우

### 1️⃣ 초기 프로필 구축 (콜드 스타트 해결)
```
확장프로그램 설치 → Google OAuth 로그인 → 최근 30일 히스토리 수집 (500개)
                                    ↓
민감 도메인 필터링 → Offscreen Document 콘텐츠 추출 (98% 성공률)
                                    ↓
Data Engine 전송 → MongoDB 샤드 저장 → GMS API 임베딩 → 초기 벡터 프로필 생성
```

### 2️⃣ 실시간 학습 플로우
```
웹페이지 방문 → Content Script 주입 → 행동 데이터 수집 (체류시간/스크롤)
                                    ↓
Readability.js 콘텐츠 정제 → 30초 배치 전송 → Data Engine 처리
                                    ↓
MongoDB 저장 → 증분 벡터 업데이트 → 실시간 프로필 갱신
```

### 3️⃣ 추천 생성 플로우
```
사용자 요청 → Spring Boot → Python 추천 엔진 → Qdrant 벡터 검색
                ↑                              ↓
          추천 결과 반환 ←────── 코사인 유사도 계산 → 콘텐츠 매칭 (유사도 0.4+)
```

## 🧠 핵심 알고리즘

### 가중치 시스템
```python
# 브라우징 행동 기반 가중치 계산
base_weight = 1.0

# 체류시간 보너스 (30초 이상, 최대 +2.0)
if time_spent > 30:
    base_weight += min((time_spent - 30) / 60, 2.0)

# 스크롤 깊이 보너스 (50% 이상, 최대 +0.5)
if scroll_depth > 50:
    base_weight += (scroll_depth - 50) / 100

# 직접 타이핑 URL 보너스 (+0.5)
if typing_ratio > 0.3:
    base_weight += 0.5
```

### 증분 벡터 업데이트
```python
# 실시간 프로필 업데이트 공식 (O(1) 복잡도)
new_vector = (old_vector * old_weight + new_vector * new_weight) / (old_weight + new_weight)
```

### 콘텐츠 정제 파이프라인
- **1단계**: Readability.js로 본문 추출
- **2단계**: 정규식으로 기자명, 광고, 관련기사 제거
- **3단계**: KoBART 동적 요약 (원문 길이 기반 압축률 조정)

## 🔐 개인정보 보호 시스템

### 수집 제외 도메인 (200+ 자동 필터링)
- **인증 관련**: OAuth, 로그인 페이지, 2FA 사이트
- **금융 관련**: 은행, 카드회사, 결제 시스템, 투자 플랫폼
- **업무 관련**: 이메일, 협업 도구, 사내 시스템, VPN
- **민감 사이트**: 성인, 도박, 불법 사이트, 다크웹
- **정부/의료**: .go.kr, .gov.kr, 병원, 의료진 사이트

### 보안 및 제어
- **사용자 완전 제어**: 실시간 토글로 수집 On/Off
- **개인별 차단 목록**: 추가 도메인 차단 설정 가능
- **데이터 최소화**: 필요 최소한 정보만 수집 (URL, 제목, 체류시간)
- **암호화 전송**: HTTPS 통신 및 JWT 토큰 인증

## 🔄 사용자 플로우

### 1️⃣ 사용자 등록 & 초기 설정
1. **Google OAuth 인증**: 간편한 소셜 로그인
2. **Chrome Extension 설치**: 원클릭 설치 및 권한 승인
3. **초기 프로필 생성**: 최근 30일 히스토리 자동 분석 (콜드 스타트 해결)
4. **관심 카테고리 설정**: 17개 카테고리별 선호도 조정

### 2️⃣ 자동 데이터 학습
1. **자연스러운 브라우징**: 평소처럼 웹서핑하며 자동 데이터 수집
2. **실시간 분석**: 30초마다 배치 처리로 즉시 프로필 업데이트
3. **지능형 가중치**: 체류시간, 스크롤 패턴 등으로 관심도 자동 측정
4. **지속 학습**: 시간이 지날수록 더욱 정확한 개인화

### 3️⃣ 맞춤형 콘텐츠 소비
1. **개인화된 뉴스 피드**: AI가 선별한 관심사 기반 뉴스
2. **지식 퀴즈 도전**: 학습한 분야의 맞춤형 O/X 퀴즈
3. **피드백 학습**: 클릭, 스크랩, 공유 등으로 추천 품질 지속 개선
4. **활동 분석**: 개인 대시보드에서 관심사 변화 추이 확인

## 👥 팀 정보

| 역할 | 이름 | 담당 영역 |
|------|------|-----------|
| **팀장 & Data Engineer** | 김희주 | 프로젝트 매니징, ML 추천 시스템, 데이터 파이프라인 |
| **Frontend** | 최지웅, 윤지훈 | React 웹앱, Chrome 확장 프로그램, UI/UX |
| **Backend** | 정해빈, 임규리, 박서진 | Spring Boot API, 인증/인가, 데이터베이스 |
| **DevOps** | 박서진 | 인프라 구축, CI/CD, 배포 자동화 |

## 📈 개발 진행 상황

- [x] **기본 아키텍처 설계** - 마이크로서비스 아키텍처 완성
- [x] **사용자 인증/인가 시스템** - Google OAuth2 + JWT 토큰
- [x] **Chrome 확장 프로그램 개발** - Manifest V3 + 실시간 데이터 수집
- [x] **ML 기반 추천 시스템** - GMS API + Qdrant 벡터 DB
- [x] **뉴스 크롤링 & 큐레이션** - KoBART 요약 + 자동 분류
- [x] **웹 애플리케이션 UI/UX** - React 19 + TailwindCSS
- [x] **배포 환경 구축** - Docker 컨테이너화 + 프로덕션 배포
- [ ] **성능 최적화** - 캐싱 전략 및 로드밸런싱
- [ ] **테스트 코드 작성** - 단위/통합 테스트 자동화

## 🎯 기술적 혁신 요소

### 1. **Offscreen Document 활용**
- Chrome 109+ 최신 기능으로 CORS 제약 극복
- 크로스 오리진 콘텐츠 추출 98% 성공률 달성

### 2. **MongoDB 샤딩 시스템**
- 사용자 ID 해시 기반 5개 샤드 자동 분산
- 대용량 로그 데이터 효율적 처리

### 3. **증분 벡터 업데이트**
- 전체 재계산 없이 O(1) 복잡도로 실시간 갱신
- 메모리 효율적 대규모 사용자 처리

### 4. **동적 콘텐츠 처리**
- 원문 길이별 KoBART 요약 파라미터 자동 조정
- 빔서치 vs 그리디 알고리즘 성능 최적화

---

<div align="center">

**Made with ❤️ by SSAFY 13기 특화 프로젝트 C102팀 PICKY-J**

</div>
