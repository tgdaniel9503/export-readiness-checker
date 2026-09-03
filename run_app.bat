@echo off
REM 수출 준비도 점검 어시스턴트 실행 스크립트 (Windows)

if not exist venv (
    echo 가상환경을 생성합니다...
    python -m venv venv
)

call venv\Scripts\activate

echo 패키지를 설치합니다...
pip install -r requirements.txt

echo 앱을 실행합니다...
streamlit run app.py

pause
