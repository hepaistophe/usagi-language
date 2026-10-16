# 우사기 랭귀지 · Usagi Language

우사기 같은 말투로 코드를 쓰는 한국어 난해한 프로그래밍 언어입니다. 자체 문법 분석기와 C11 변환 컴파일러, VS Code 확장을 함께 제공합니다.

현재 컴파일러·확장 버전은 **0.5.0**, 문법 표준은 **0.10.0 초안**입니다. Windows x64에서 설치와 실행을 검증했습니다.

## VS Code에 설치하기

1. [v0.5.0 Releases](https://github.com/hepaistophe/usagi-language/releases/tag/v0.5.0)에서 **usagi-language-0.5.0.vsix**를 다운로드합니다.
2. Windows용 VS Code에서 **Ctrl+Shift+X**로 확장 화면을 엽니다.
3. 확장 패널의 **… → VSIX에서 설치… / Install from VSIX…**를 선택합니다.
4. 다운로드한 VSIX를 선택합니다. 게시자 확인 창이 나오면 이 프로젝트의 식별자 `usagi-local`인지 확인합니다.
5. 다시 로드를 요청하면 누릅니다.
6. 코드를 저장할 폴더를 열고, 직접 만든 폴더를 신뢰합니다.
7. **Ctrl+Shift+P → 우사기: 새 프로그램 만들기**를 선택한 뒤 `main.usagi`로 저장합니다.
8. 오른쪽 위 **▶** 또는 **우사기: 현재 파일 실행**으로 실행합니다. 결과와 입력은 터미널에서 확인합니다.

검사에는 **Python 3.12 이상**, 실행·실행 파일 빌드에는 **Clang, 링커, Windows SDK**가 필요합니다. Visual Studio Build Tools의 C++ 빌드 도구·Windows SDK·Windows용 C++ Clang 도구 설치를 자동 탐색합니다. Python·Clang 실행 파일은 VSIX에 포함하지 않습니다.

Python을 찾지 못하면 **Ctrl+, → Usagi: Python Path**에 `python.exe`의 전체 경로를 지정합니다. Clang 경로는 **Usagi: Clang Path**에서 지정할 수 있습니다. Python용 VS Code 확장은 필수가 아닙니다.

VSIX에는 우사기 컴파일러가 포함됩니다. 구문 강조, 코드 조각, 키워드 설명, 저장 전 오류 검사, 터미널 실행, C 생성과 실행 파일 빌드를 지원합니다. 현재 배포 경로는 GitHub Releases입니다.

## 첫 프로그램

```usagi
우사기!
    우~라~ 하치! 우사기랭 설치 성공! 와레! 야하!
!우사기
```

출력:

```text
우사기랭 설치 성공!
```

## 냠!으로 함수에 인자 먹이기

```usagi
우나! 하치와레: 더하기
    냠! 얏! 야
    냠! 얏! 야야
우~나! 야 하! 야야

우사기!
    우~라~ 하치와레: 더하기 냠! 뿌르르 냠! 뿌르르르 꿀꺽! 야하!
!우사기
```

출력은 `5`입니다. 선언에서는 `냠! 자료형 이름`, 호출에서는 `냠! 값`을 하나씩 적고 `꿀꺽!`으로 끝냅니다. 정수·실수·문자열 인자, 반환형 추론, 값 복사와 왼쪽부터 평가를 지원합니다.

메인은 `우사기! … !우사기`, 일반 함수는 `우나! … 우~나! 반환값`, 문장 끝은 `야하!`입니다. 사용자 이름에는 `하치와레:`를 붙이며 `야`, `야야`처럼 `야`만 반복한 변수는 접두사를 생략할 수 있습니다. 분기와 반복도 전용 문법을 사용합니다.

자세한 규칙은 [언어 표준](USAGI_LANGUAGE_SPEC.md), 실행 예제는 [examples](usagi-compiler/examples), 확장 명령은 [확장 사용법](usagi-vscode/README.md)에 있습니다. 재귀, 배열, 문자형 실행과 문자열 산술·연결은 아직 지원하지 않습니다.

## 터미널에서 실행하기

저장소를 내려받은 뒤 `usagi-compiler` 폴더에서 실행합니다.

```powershell
cd usagi-compiler
py -m usagi run examples/feeding_arguments.usagi
```

Python 3.12 이상과 네이티브 빌드 도구가 필요합니다. 추가 Python 패키지는 필요하지 않습니다. `py` 대신 `python`을 사용하는 환경에서는 명령을 바꾸면 됩니다. 자세한 명령은 [컴파일러 README](usagi-compiler/README.md)를 참고하세요.

## 개발과 검증

컴파일러 테스트는 `usagi-compiler`에서 실행합니다.

```powershell
py -m unittest discover -s tests -v
```

확장 개발에는 Node.js와 npm이 필요합니다(검증 환경: Node.js 24.15.0 / npm 11.12.1). `usagi-vscode`에서 실행합니다. 생성 단계가 컴파일러, 표준 문서와 구문 강조 파일을 모읍니다.

```powershell
npm ci
npm run prepare-bundle
npm test
npm run package
```

VSIX는 저장소 최상위에 생성됩니다. 소스 저장소에는 의존성·캐시·빌드 결과를 넣지 않습니다. 검증한 배포 파일은 [GitHub Releases](https://github.com/hepaistophe/usagi-language/releases)에서 제공합니다.

0.5.0 검증: 컴파일러 106개, 확장 Node/TextMate 9개 테스트 통과. 실제 VS Code 확장 호스트에서 설치, 저장 전 오류 검사, C 생성, 실행 파일 빌드와 터미널 실행을 확인했습니다. 환경과 검증 범위는 [배포 기록](USAGI_VSCODE_RELEASE.md)에 있습니다.
