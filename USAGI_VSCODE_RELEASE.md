# 우사기 VS Code 확장 0.5.0

작성일: 2026-10-16 (한국 시간)

설치 파일: [usagi-language-0.5.0.vsix](https://github.com/hepaistophe/usagi-language/releases/download/v0.5.0/usagi-language-0.5.0.vsix). 공개 소스: [hepaistophe/usagi-language](https://github.com/hepaistophe/usagi-language).

## 설치와 실행

1. VS Code의 확장 화면에서 `…` → **VSIX에서 설치**를 선택합니다.
2. 위 설치 파일을 고릅니다. 필요하면 VS Code 창을 다시 로드합니다.
3. `.usagi` 파일을 열고 오른쪽 위 ▶로 실행합니다. 터미널 입력을 지원합니다.

Python 3.12 이상과 Clang·링커·Windows SDK가 필요합니다. 컴파일러 소스는 포함되어 있어 별도로 복사하지 않아도 됩니다. 검사·실행은 신뢰한 작업 영역에서 사용합니다. Python 자동 탐색이 안 되면 설정의 **Usagi: Python Path**에 실행 파일 경로를 지정합니다.

## 새 인자 문법

```text
우나! 하치와레: 더하기
    냠! 얏! 야
    냠! 얏! 야야
우~나! 야 하! 야야

우사기!
    우~라~ 하치와레: 더하기 냠! 뿌르르 냠! 뿌르르르 꿀꺽! 야하!
!우사기
```

출력은 `5`입니다. 정수·실수·문자열 인자, 왼쪽부터 평가, 매개변수형 변환과 값 복사를 지원합니다. 인자 없는 함수는 기존 빈 괄호 호출을 사용합니다.

## 검증

- 컴파일러 테스트 106개 통과, 건너뛴 테스트 없음.
- 확장 Node/TextMate 테스트 9개 통과. 업로드할 파일만 추출한 깨끗한 소스에서도 의존성 설치·컴파일러 테스트·확장 테스트·VSIX 패키징을 다시 검증했습니다.
- Windows x64 / VS Code 1.141.1에 VSIX 실제 설치 성공.
- 별도 VS Code 복사본·프로필의 실제 확장 호스트에서 파일 인식, 도움말, 저장 전 오류 진단과 수정 후 해제, C 생성, 실행 파일 빌드, 터미널 실행, 새 파일 생성을 확인했습니다.
- 빌드된 인자 예제의 표준 출력은 `5`, `우사기!`, 종료 코드는 0입니다.
- 최종 VSIX의 실행 코드·컴파일러·구문 강조·코드 조각은 실제 호스트 테스트에 사용한 설치본과 줄바꿈을 제외한 내용이 일치합니다. GitHub 저장소 정보와 설치 문서만 갱신했습니다.
- 실제 색상 테마의 시각 확인과 키보드로 하는 한글 입력은 자동화 검증 범위에 포함하지 않았습니다.

패키지 크기: 42,808바이트. SHA-256:

```text
4e50dc6a1733c3fbe3bb30fb908203d62e1cac4748f69ca2d4826323ee658d44
```

사용법: [확장 README](usagi-vscode/README.md). 표준: [우사기 문법](USAGI_LANGUAGE_SPEC.md). 예제: [먹이기 인자](usagi-compiler/examples/feeding_arguments.usagi).

현재 배포물은 GitHub Releases에서 다운로드하는 VSIX 직접 설치용이며 게시자 ID `usagi-local`은 로컬 미리보기 식별자입니다. Marketplace 공개 게시를 위한 계정·라이선스 결정은 별도 단계입니다.
