# Pikraft — 이미지 큐레이션 사이트

Unsplash API를 활용한 이미지 큐레이션 웹사이트입니다.
애드센스 광고 자리가 포함되어 있어 패시브 인컴 구축에 활용할 수 있습니다.

## 프로젝트 구조

```
pikraft/
├── main.py              # FastAPI 앱 (API 엔드포인트)
├── requirements.txt     # 의존성 목록
├── .env.example         # 환경변수 예시
├── templates/
│   └── index.html       # 메인 페이지 (Jinja2 템플릿)
└── static/
    ├── css/style.css    # 스타일시트
    └── js/app.js        # 프론트엔드 로직
```

## 빠른 시작

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. Unsplash API 키 발급

1. https://unsplash.com/developers 접속
2. "New Application" 생성
3. Access Key 복사

### 3. 환경변수 설정

```bash
cp .env.example .env
# .env 파일에 UNSPLASH_ACCESS_KEY 입력
```

### 4. 서버 실행

```bash
uvicorn main:app --reload
```

브라우저에서 http://localhost:8000 접속

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 메인 페이지 |
| GET | `/api/photos?query=nature&page=1` | 이미지 검색 |
| GET | `/api/trending` | 인기 이미지 |

## 광고 수익화

`templates/index.html` 안에 광고 자리 3곳이 준비되어 있습니다.

1. **상단 배너** (728×90) — `.ad-top` 섹션
2. **사이드바 대형** (300×250) — 첫 번째 `.ad-box`
3. **사이드바 소형** (300×120) — 두 번째 `.ad-box`

각 주석 처리된 `<ins class="adsbygoogle">` 태그의 주석을 해제하고
`ca-pub-XXXXXXX`와 `data-ad-slot` 값을 본인 애드센스 ID로 교체하세요.

## 배포 (Vercel / Railway)

```bash
# Railway
railway init
railway up

# 환경변수 설정
railway variables set UNSPLASH_ACCESS_KEY=your_key_here
```

## 주의사항

- Unsplash API 무료 플랜: 시간당 50건 요청 제한
- 트래픽이 늘면 Unsplash Production 승인 신청 필요 (무제한)
- 이미지 클릭 시 반드시 Unsplash 원본으로 연결 (라이선스 준수)
