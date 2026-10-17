# 우사기 Playground

우사기 랭귀지 v1.1.0의 브라우저 편집기와 실행기입니다. `dist/`를 정적 호스팅하면 됩니다.

## 사용

코드 작성 → **Run** 또는 **Ctrl+Enter** → 입력 요청 시 터미널에 입력하고 **Enter**.
출력과 입력 기록이 하나의 터미널에 순서대로 쌓입니다. 여러 줄 붙여넣기, Shift+Enter 줄바꿈,
EOF 버튼/Ctrl+D 입력 종료, 중지를 지원합니다. 입력을 기다리는 시간은 10초 제한에서 제외합니다.
예제 입력 버튼은 입력 예시를 터미널 입력창에 붙여넣으며 Enter로 제출합니다.
코드는 현재 브라우저의 localStorage에 저장됩니다. 서버로 코드를 제출하지 않습니다.
페이지를 열면 jsDelivr에서 고정 버전 Pyodide 314.0.7을 미리 준비하므로 인터넷 연결이 필요합니다.
첫 방문의 다운로드 시간은 연결 속도에 따라 달라집니다. 준비 후에는 같은 실행기를 재사용합니다.

## 구현

원본 [Usagi v1.1.0](../usagi-compiler)의
`compiler.py`, `numbers.py`, `__init__.py`를 `dist/runtime/usagi/`에 그대로 포함합니다.
원본 lexer/parser/analyzer로 검사하고, `interpreter.py`가 타입이 결정된 AST를 실행합니다.
웹에서는 C 실행 파일을 생성하지 않습니다. 사용자 Python, 셸, C 코드를 실행하지 않습니다.
모듈 Web Worker에서 실행하며 중지·시간 초과 시 Worker를 종료합니다.
중지 후에는 다음 실행에 사용할 Worker를 백그라운드에서 다시 준비합니다.
런타임 소스는 `runtime/bundle.json` 한 요청으로 Python 로딩과 병렬로 받습니다.
대량 출력은 Worker에서 묶어서 보내고 화면은 프레임 단위로 갱신합니다.
입력 요청·완료·오류 앞에는 버퍼를 비워 터미널의 출력 순서를 유지합니다.

언어 표준과 별개인 웹 환경 한도: 연산 시간 10초 (입력 대기 제외), AST 실행 단계 20,000,000회,
코드 256 KiB, 입력 전체 1 MiB, 출력 64 KiB, 동시에 살아 있는 정수 배열 원소 합계 1,000,000개.
문자열·입력 한 줄 4095 UTF-8 바이트, 부호 있는 64비트 정수 등 언어 한도는 그대로 적용합니다.
브라우저 입력란의 줄바꿈은 LF로 정규화되며 Windows 콘솔의 CR 처리 차이는 없습니다.
실수는 IEEE 754 binary64 및 출력 15자리 유효숫자를 사용합니다. 드문 마지막 자릿수/입력 underflow 판정은 호스트 C 라이브러리와 차이가 있을 수 있습니다.

## 로컬 확인

```sh
python -m unittest discover -s tests -v
python -m http.server 4173 --bind 127.0.0.1 --directory dist
```

브라우저에서 `http://127.0.0.1:4173`을 엽니다. `file://`로 열면 Worker와 fetch가 동작하지 않습니다.
원본 변경을 반영하려면 `python build.py <usagi-compiler 경로> <케빈 예제 경로>`를 실행합니다.
기존 언어 표준/컴파일러 버전과 웹 실행기의 한도를 구분해서 유지하세요.
`dist/runtime/`의 Python 파일을 수정했다면 `python build.py --runtime-only`로
브라우저 번들도 갱신해야 합니다. 테스트에서 번들과 실제 소스가 같은지 확인합니다.

## Vercel 배포

이 폴더를 프로젝트 루트로 배포합니다. `vercel.json`은 별도 빌드 없이 `dist/`를 정적 호스팅하도록 설정합니다.

```sh
npx vercel login
npx vercel --prod
```

대시보드에서 GitHub 프로젝트를 연결한다면 Root Directory는 `usagi-web`, Framework Preset은 Other, Output Directory는 `dist`입니다.
